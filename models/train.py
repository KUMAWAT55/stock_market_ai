from __future__ import annotations
"""Global multi-symbol ensemble training for all supported timeframes."""

import argparse
import json
import pickle
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from config.config import Settings, get_settings
from data.kite_client import KiteHistoricalClient
from database.db_manager import DatabaseManager
from features.feature_pipeline import (
    build_training_frame,
    feature_columns_for_timeframe,
    filter_correlated_features,
)
from models.lstm_proxy import AttentionReadyLSTMProxyClassifier, LSTMProxyClassifier
from models.model_registry import ModelRegistry

try:
    from xgboost import XGBClassifier
except Exception:  # pragma: no cover
    XGBClassifier = None

try:
    from lightgbm import LGBMClassifier
except Exception:  # pragma: no cover
    LGBMClassifier = None


@dataclass(slots=True)
class TrainOutput:
    """Training result summary with artifact location and evaluation metrics."""

    artifact_path: Path
    model_name: str
    version: str
    metrics: dict[str, float]


@dataclass(slots=True)
class TimeframePlan:
    """Model composition plan for a specific timeframe."""

    base_models: list[str]
    strategy: str
    meta_model: str | None
    calibration: str
    min_rows: int

def _default_model_config() -> dict[str, Any]:
    return {
        "random_seed": 42,
        "correlation_threshold": 0.97,
        "oof_splits": 5,
        "train_fraction": 0.6,
        "calibration_fraction": 0.2,
        "plans": {
            "1m": {
                "base_models": ["lightgbm", "logreg"],
                "strategy": "soft_voting",
                "meta_model": None,
                "calibration": "isotonic",
                "min_rows": 2500,
            },
            "5m": {
                "base_models": ["xgboost", "lightgbm", "logreg"],
                "strategy": "stacking",
                "meta_model": "logreg",
                "calibration": "isotonic",
                "min_rows": 1800,
            },
            "15m": {
                "base_models": ["xgboost", "lightgbm", "lstm"],
                "strategy": "stacking",
                "meta_model": "lightgbm",
                "calibration": "isotonic",
                "min_rows": 1200,
            },
            "1h": {
                "base_models": ["lstm", "xgboost", "lightgbm"],
                "strategy": "stacking",
                "meta_model": "lightgbm",
                "calibration": "platt",
                "min_rows": 700,
            },
            "1d": {
                "base_models": ["lstm_attention", "xgboost", "lightgbm"],
                "strategy": "stacking",
                "meta_model": "lightgbm",
                "calibration": "platt",
                "min_rows": 300,
            },
        },
        "model_params": {
            "logreg": {"max_iter": 2500, "C": 1.0},
            "xgboost": {
                "n_estimators": 450,
                "max_depth": 6,
                "learning_rate": 0.035,
                "subsample": 0.9,
                "colsample_bytree": 0.85,
                "reg_lambda": 1.5,
            },
            "lightgbm": {
                "n_estimators": 450,
                "num_leaves": 64,
                "learning_rate": 0.03,
                "subsample": 0.9,
                "colsample_bytree": 0.85,
            },
            "lstm": {"units": 64},
            "lstm_attention": {"units": 96},
        },
    }


def _load_model_config(settings: Settings, override_path: str | None) -> dict[str, Any]:
    if override_path:
        path = Path(override_path)
    else:
        path = settings.model_hyperparams_file
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    logger.warning("Model config file not found at {}. Using defaults.", path)
    return _default_model_config()


def _resolve_plan(config: dict[str, Any], timeframe: str) -> TimeframePlan:
    plans = config.get("plans", {})
    raw = dict(plans.get(timeframe, {}))
    if not raw:
        raise ValueError(f"No training plan found for timeframe {timeframe}")
    return TimeframePlan(
        base_models=list(raw.get("base_models", [])),
        strategy=str(raw.get("strategy", "stacking")),
        meta_model=raw.get("meta_model"),
        calibration=str(raw.get("calibration", "isotonic")),
        min_rows=int(raw.get("min_rows", 300)),
    )


def _build_model(model_key: str, config: dict[str, Any], seed: int) -> Any:
    params = dict(config.get("model_params", {}).get(model_key, {}))
    if model_key == "logreg":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        max_iter=int(params.get("max_iter", 2500)),
                        C=float(params.get("C", 1.0)),
                        random_state=seed,
                        class_weight="balanced",
                    ),
                ),
            ]
        )

    if model_key == "xgboost":
        if XGBClassifier is None:
            logger.warning("xgboost unavailable; falling back to RandomForest.")
            return RandomForestClassifier(
                n_estimators=350,
                max_depth=8,
                min_samples_leaf=3,
                random_state=seed,
                class_weight="balanced_subsample",
                n_jobs=4,
            )
        return XGBClassifier(
            n_estimators=int(params.get("n_estimators", 450)),
            max_depth=int(params.get("max_depth", 6)),
            learning_rate=float(params.get("learning_rate", 0.035)),
            subsample=float(params.get("subsample", 0.9)),
            colsample_bytree=float(params.get("colsample_bytree", 0.85)),
            reg_lambda=float(params.get("reg_lambda", 1.5)),
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=seed,
            n_jobs=4,
        )

    if model_key == "lightgbm":
        if LGBMClassifier is None:
            logger.warning("lightgbm unavailable; falling back to HistGradientBoosting.")
            return HistGradientBoostingClassifier(
                max_iter=int(params.get("n_estimators", 450)),
                learning_rate=float(params.get("learning_rate", 0.03)),
                max_depth=6,
                random_state=seed,
            )
        return LGBMClassifier(
            n_estimators=int(params.get("n_estimators", 450)),
            num_leaves=int(params.get("num_leaves", 64)),
            learning_rate=float(params.get("learning_rate", 0.03)),
            subsample=float(params.get("subsample", 0.9)),
            colsample_bytree=float(params.get("colsample_bytree", 0.85)),
            random_state=seed,
        )

    if model_key == "lstm":
        units = int(params.get("units", 64))
        return LSTMProxyClassifier(random_state=seed, hidden_units=units)

    if model_key == "lstm_attention":
        units = int(params.get("units", 96))
        return AttentionReadyLSTMProxyClassifier(random_state=seed, hidden_units=units)

    raise ValueError(f"Unsupported model key: {model_key}")


def _predict_proba(model: Any, x: pd.DataFrame) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(x)
        if probs.ndim == 2 and probs.shape[1] > 1:
            return np.asarray(probs[:, 1], dtype=float)
        return np.asarray(probs.reshape(-1), dtype=float)
    pred = np.asarray(model.predict(x), dtype=float)
    return np.clip(pred, 0.0, 1.0)


def _metrics(y_true: np.ndarray, prob_up: np.ndarray, threshold: float = 0.5) -> dict[str, float]:
    pred = (prob_up >= threshold).astype(int)
    out = {
        "accuracy": float(accuracy_score(y_true, pred)),
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
    }
    if len(np.unique(y_true)) > 1:
        out["roc_auc"] = float(roc_auc_score(y_true, prob_up))
    return out


def _time_series_splits(ts: pd.Series, n_splits: int) -> list[tuple[np.ndarray, np.ndarray]]:
    unique_times = np.sort(ts.unique())
    n_times = len(unique_times)
    min_train = max(30, int(n_times * 0.35))
    if n_times <= min_train + 1:
        return []
    step = max(1, (n_times - min_train) // max(1, n_splits))

    splits: list[tuple[np.ndarray, np.ndarray]] = []
    train_end = min_train
    while train_end < n_times - 1 and len(splits) < n_splits:
        val_end = min(n_times, train_end + step)
        tr_times = set(unique_times[:train_end])
        val_times = set(unique_times[train_end:val_end])
        tr_idx = np.flatnonzero(ts.isin(tr_times).to_numpy())
        val_idx = np.flatnonzero(ts.isin(val_times).to_numpy())
        if len(tr_idx) > 0 and len(val_idx) > 0:
            splits.append((tr_idx, val_idx))
        train_end = val_end
    return splits


def _split_train_calib_test(
    frame: pd.DataFrame,
    train_fraction: float,
    calibration_fraction: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    unique_times = np.sort(frame["candle_end"].unique())
    n_times = len(unique_times)
    train_cut = max(1, int(n_times * train_fraction))
    calib_cut = max(train_cut + 1, int(n_times * (train_fraction + calibration_fraction)))
    calib_cut = min(calib_cut, n_times - 1)

    train_times = set(unique_times[:train_cut])
    calib_times = set(unique_times[train_cut:calib_cut])
    test_times = set(unique_times[calib_cut:])
    return (
        frame[frame["candle_end"].isin(train_times)].copy(),
        frame[frame["candle_end"].isin(calib_times)].copy(),
        frame[frame["candle_end"].isin(test_times)].copy(),
    )


def _fit_calibrator(method: str, raw_prob: np.ndarray, y: np.ndarray) -> dict[str, Any] | None:
    if len(raw_prob) == 0:
        return None
    method = method.lower()
    if method == "isotonic":
        calibrator = IsotonicRegression(out_of_bounds="clip")
        calibrator.fit(raw_prob, y)
        return {"method": "isotonic", "model": calibrator}
    if method == "platt":
        calibrator = LogisticRegression(max_iter=1000, random_state=42)
        calibrator.fit(raw_prob.reshape(-1, 1), y)
        return {"method": "platt", "model": calibrator}
    return None


def _apply_calibrator(calibrator: dict[str, Any] | None, raw_prob: np.ndarray) -> np.ndarray:
    if calibrator is None:
        return raw_prob
    method = str(calibrator.get("method", "")).lower()
    model = calibrator.get("model")
    if model is None:
        return raw_prob
    if method == "isotonic":
        return np.clip(np.asarray(model.predict(raw_prob), dtype=float), 0.0, 1.0)
    if method == "platt":
        return np.clip(np.asarray(model.predict_proba(raw_prob.reshape(-1, 1))[:, 1], dtype=float), 0.0, 1.0)
    return raw_prob


def _feature_importance(base_models: dict[str, Any], feature_columns: list[str]) -> dict[str, float]:
    agg = np.zeros(len(feature_columns), dtype=float)
    used = 0
    for model in base_models.values():
        estimator = model
        if hasattr(estimator, "named_steps") and estimator.named_steps:
            estimator = list(estimator.named_steps.values())[-1]
        if hasattr(estimator, "feature_importances_"):
            values = np.asarray(estimator.feature_importances_, dtype=float)
        elif hasattr(estimator, "coef_"):
            values = np.abs(np.asarray(estimator.coef_).reshape(-1))
        else:
            continue
        if values.size != len(feature_columns):
            continue
        total = values.sum() or 1.0
        agg += values / total
        used += 1
    if used == 0:
        return {}
    agg = agg / float(used)
    return {feature_columns[idx]: float(agg[idx]) for idx in range(len(feature_columns))}


def _build_global_dataset(
    timeframe: str,
    lookback_days: int,
    symbols: list[str],
) -> pd.DataFrame:
    settings = get_settings()
    token_map = settings.load_symbol_token_map()
    symbol_to_token = {symbol.upper(): int(token) for token, symbol in token_map.items()}
    resolved_symbols = [symbol.upper() for symbol in symbols if symbol.upper() in symbol_to_token]
    if not resolved_symbols:
        raise ValueError("No valid symbols resolved for training")

    historical = KiteHistoricalClient()
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=max(1, int(lookback_days)))

    chunks: list[pd.DataFrame] = []
    for symbol in resolved_symbols:
        token = symbol_to_token[symbol]
        frame = historical.fetch_candles(
            instrument_token=token,
            timeframe=timeframe,
            from_dt=start_dt,
            to_dt=end_dt,
        )
        if frame.empty:
            logger.warning("No candles received for {} {}", symbol, timeframe)
            continue
        frame["symbol"] = symbol
        frame["timeframe"] = timeframe
        chunks.append(frame)

    if not chunks:
        raise ValueError(f"No historical candles fetched for timeframe {timeframe}")
    return pd.concat(chunks, axis=0, ignore_index=True)


def _build_global_dataset_from_db(
    timeframe: str,
    lookback_days: int,
    symbols: list[str],
) -> pd.DataFrame:
    settings = get_settings()
    db_manager = DatabaseManager()
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=max(1, int(lookback_days)))

    chunks: list[pd.DataFrame] = []
    for symbol in symbols:
        frame = db_manager.get_candles_in_range(
            symbol=symbol.upper(),
            timeframe=timeframe,
            start_dt=start_dt,
            end_dt=end_dt,
        )
        if frame.empty:
            logger.warning("No candles in DB for {} {}", symbol, timeframe)
            continue
        frame["symbol"] = symbol.upper()
        frame["timeframe"] = timeframe
        chunks.append(frame)

    if not chunks:
        raise ValueError(f"No historical candles found in DB for timeframe {timeframe}")
    return pd.concat(chunks, axis=0, ignore_index=True)


def train_global_from_candles(
    timeframe: str,
    candles: pd.DataFrame,
    *,
    settings: Settings | None = None,
    model_config_path: str | None = None,
    min_rows_override: int | None = None,
    target_threshold_override: float | None = None,
) -> TrainOutput:
    """Train a global multi-symbol stacked ensemble for one timeframe."""
    settings = settings or get_settings()
    config = _load_model_config(settings, model_config_path)
    seed = int(config.get("random_seed", 42))
    np.random.seed(seed)
    random.seed(seed)

    db_manager = DatabaseManager()
    registry = ModelRegistry(db_manager)

    plan = _resolve_plan(config, timeframe=timeframe)
    required_rows = int(min_rows_override) if min_rows_override is not None else int(plan.min_rows)
    target_threshold = (
        float(target_threshold_override)
        if target_threshold_override is not None
        else settings.forward_return_threshold(timeframe)
    )
    logger.info(
        "Training global ensemble {} with threshold={} min_rows={}",
        timeframe,
        target_threshold,
        required_rows,
    )

    frame = build_training_frame(
        candles=candles,
        horizon_steps=1,
        timeframe=timeframe,
        target_threshold=target_threshold,
        index_symbol=settings.market_index_symbol.upper(),
        sector_map=settings.load_sector_map(),
    )
    if frame.empty or len(frame) < required_rows:
        raise ValueError(f"Insufficient global rows for {timeframe}: {len(frame)} (required={required_rows})")

    base_features = feature_columns_for_timeframe(timeframe)
    train_frame, calib_frame, test_frame = _split_train_calib_test(
        frame=frame.sort_values(["candle_end", "symbol"]),
        train_fraction=float(config.get("train_fraction", 0.6)),
        calibration_fraction=float(config.get("calibration_fraction", 0.2)),
    )
    if train_frame.empty or test_frame.empty:
        raise ValueError("Time split failed: empty train or test set")

    corr_threshold = float(config.get("correlation_threshold", 0.97))
    selected_features, dropped_features = filter_correlated_features(
        train_frame.dropna(subset=base_features),
        base_features,
        threshold=corr_threshold,
    )
    if not selected_features:
        raise ValueError("Correlation filter removed all features")

    train_clean = train_frame.dropna(subset=selected_features + ["target_up"]).copy()
    calib_clean = calib_frame.dropna(subset=selected_features + ["target_up"]).copy()
    test_clean = test_frame.dropna(subset=selected_features + ["target_up"]).copy()
    if train_clean.empty or test_clean.empty:
        raise ValueError("Not enough clean rows after feature filtering")

    x_train = train_clean[selected_features].astype(float)
    y_train = train_clean["target_up"].astype(int)
    x_calib = calib_clean[selected_features].astype(float)
    y_calib = calib_clean["target_up"].astype(int)
    x_test = test_clean[selected_features].astype(float)
    y_test = test_clean["target_up"].astype(int)

    splits = _time_series_splits(train_clean["candle_end"], n_splits=int(config.get("oof_splits", 5)))
    if not splits:
        raise ValueError("Not enough temporal depth for walk-forward OOF splits")

    base_oof = pd.DataFrame(index=x_train.index)
    fitted_base_models: dict[str, Any] = {}

    for model_key in plan.base_models:
        oof = np.full(len(x_train), np.nan, dtype=float)
        for fold_idx, (tr_idx, val_idx) in enumerate(splits, start=1):
            x_tr = x_train.iloc[tr_idx]
            y_tr = y_train.iloc[tr_idx]
            x_val = x_train.iloc[val_idx]
            model = _build_model(model_key, config=config, seed=seed + fold_idx)
            model.fit(x_tr, y_tr)
            oof[val_idx] = _predict_proba(model, x_val)

        # Fill potential gaps from sparse fold boundaries with robust central tendency.
        if np.isnan(oof).any():
            non_nan = oof[~np.isnan(oof)]
            fill_value = float(np.mean(non_nan)) if len(non_nan) else 0.5
            oof[np.isnan(oof)] = fill_value

        full_model = _build_model(model_key, config=config, seed=seed)
        full_model.fit(x_train, y_train)
        fitted_base_models[model_key] = full_model
        base_oof[model_key] = oof

    if plan.strategy == "soft_voting":
        raw_train_prob = base_oof.mean(axis=1).to_numpy(dtype=float)
        meta_model = None
    else:
        if not plan.meta_model:
            raise ValueError(f"Meta model not configured for stacking timeframe {timeframe}")
        meta_model = _build_model(plan.meta_model, config=config, seed=seed)
        meta_model.fit(base_oof, y_train)
        raw_train_prob = _predict_proba(meta_model, base_oof)

    # Build calibration probabilities using full base models on holdout calibration period.
    calib_base_prob = pd.DataFrame(
        {name: _predict_proba(model, x_calib) for name, model in fitted_base_models.items()},
        index=x_calib.index,
    ) if not x_calib.empty else pd.DataFrame(columns=plan.base_models)

    if plan.strategy == "soft_voting":
        raw_calib_prob = calib_base_prob.mean(axis=1).to_numpy(dtype=float) if not calib_base_prob.empty else np.array([])
    else:
        raw_calib_prob = _predict_proba(meta_model, calib_base_prob) if not calib_base_prob.empty else np.array([])

    calibrator = _fit_calibrator(plan.calibration, raw_calib_prob, y_calib.to_numpy(dtype=int))

    test_base_prob = pd.DataFrame(
        {name: _predict_proba(model, x_test) for name, model in fitted_base_models.items()},
        index=x_test.index,
    )
    if plan.strategy == "soft_voting":
        raw_test_prob = test_base_prob.mean(axis=1).to_numpy(dtype=float)
    else:
        raw_test_prob = _predict_proba(meta_model, test_base_prob)
    final_test_prob = _apply_calibrator(calibrator, raw_test_prob)

    metrics = _metrics(y_test.to_numpy(dtype=int), final_test_prob)
    metrics["rows_total"] = float(len(frame))
    metrics["rows_train"] = float(len(train_clean))
    metrics["rows_calib"] = float(len(calib_clean))
    metrics["rows_test"] = float(len(test_clean))
    metrics["target_threshold"] = float(target_threshold)
    metrics["oof_roc_auc"] = float(roc_auc_score(y_train, raw_train_prob)) if len(np.unique(y_train)) > 1 else 0.0
    metrics["features_initial"] = float(len(base_features))
    metrics["features_selected"] = float(len(selected_features))
    metrics["features_dropped_corr"] = float(len(dropped_features))

    model_name = "global_stacking_ensemble"
    version = registry.build_version(model_name=model_name, timeframe=timeframe)
    artifact_path = settings.model_artifact_dir / f"GLOBAL_{model_name}_{timeframe}_{version}.pkl"

    bundle = {
        "artifact_type": "stacking_ensemble_v1",
        "timeframe": timeframe,
        "strategy": plan.strategy,
        "base_model_order": list(plan.base_models),
        "base_models": fitted_base_models,
        "meta_model": meta_model,
        "calibrator": calibrator,
        "feature_columns": selected_features,
        "feature_importance": _feature_importance(fitted_base_models, selected_features),
        "dropped_correlated_features": dropped_features,
        "target_threshold": target_threshold,
        "index_symbol": settings.market_index_symbol.upper(),
        "trained_symbols": sorted(set(frame["symbol"].astype(str))),
        "created_at": datetime.utcnow().isoformat(),
    }
    with artifact_path.open("wb") as f:
        pickle.dump(bundle, f)

    registry.register(
        model_name=model_name,
        timeframe=timeframe,
        version=version,
        artifact_path=artifact_path,
        metrics=metrics,
        feature_list=selected_features,
    )

    # Keep existing dashboard contract: store latest simulated metrics per symbol.
    symbols_for_metrics = sorted(set(frame["symbol"].astype(str)))
    for symbol in symbols_for_metrics:
        db_manager.insert_backtest_metrics(
            symbol=symbol,
            timeframe=timeframe,
            model_name=model_name,
            model_version=version,
            metrics=metrics,
        )
    db_manager.insert_backtest_metrics(
        symbol="GLOBAL",
        timeframe=timeframe,
        model_name=model_name,
        model_version=version,
        metrics=metrics,
    )

    logger.info(
        "Global ensemble training completed for {} symbols={} timeframe={} artifact={}",
        len(symbols_for_metrics),
        symbols_for_metrics[:8],
        timeframe,
        artifact_path,
    )
    return TrainOutput(artifact_path=artifact_path, model_name=model_name, version=version, metrics=metrics)


def train_global_from_kite(
    timeframe: str,
    lookback_days: int,
    symbols: list[str],
    model_config_path: str | None = None,
    min_rows: int | None = None,
    target_threshold: float | None = None,
) -> TrainOutput:
    """Fetch multi-symbol historical candles and train timeframe ensemble."""
    settings = get_settings()
    candles = _build_global_dataset(
        timeframe=timeframe,
        lookback_days=lookback_days,
        symbols=symbols,
    )
    return train_global_from_candles(
        timeframe=timeframe,
        candles=candles,
        settings=settings,
        model_config_path=model_config_path,
        min_rows_override=min_rows,
        target_threshold_override=target_threshold,
    )


def train_global_from_db(
    timeframe: str,
    lookback_days: int,
    symbols: list[str],
    model_config_path: str | None = None,
    min_rows: int | None = None,
    target_threshold: float | None = None,
) -> TrainOutput:
    """Read multi-symbol candles from DB and train timeframe ensemble."""
    settings = get_settings()
    candles = _build_global_dataset_from_db(
        timeframe=timeframe,
        lookback_days=lookback_days,
        symbols=symbols,
    )
    return train_global_from_candles(
        timeframe=timeframe,
        candles=candles,
        settings=settings,
        model_config_path=model_config_path,
        min_rows_override=min_rows,
        target_threshold_override=target_threshold,
    )


def _resolve_symbols(settings: Settings, symbols_csv: str, all_symbols: bool) -> list[str]:
    available = settings.load_symbol_universe()
    if all_symbols:
        return available
    if symbols_csv.strip():
        requested = [token.strip().upper() for token in symbols_csv.split(",") if token.strip()]
        resolved = [symbol for symbol in requested if symbol in available]
        if resolved:
            return resolved
    return available


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train global multi-symbol ensemble from Kite candles")
    parser.add_argument("--timeframe", choices=["1m", "5m", "15m", "1h", "1d"], required=True)
    parser.add_argument("--lookback-days", type=int, default=240)
    parser.add_argument(
        "--symbols",
        default="",
        help="Comma-separated symbols. If empty, uses all symbols from config/instruments.json.",
    )
    parser.add_argument("--all-symbols", action="store_true", help="Train using all mapped symbols.")
    parser.add_argument("--model-config", default="", help="Optional path to model config JSON.")
    parser.add_argument("--min-rows", type=int, default=0, help="Override minimum rows required.")
    parser.add_argument(
        "--target-threshold",
        type=float,
        default=float("nan"),
        help="Optional override for forward-return target threshold.",
    )
    parser.add_argument(
        "--use-db",
        action="store_true",
        help="Train using ohlcv_candles in the database instead of Kite API.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    settings = get_settings()
    symbols = _resolve_symbols(settings, symbols_csv=args.symbols, all_symbols=bool(args.all_symbols))
    if not symbols:
        raise ValueError("No symbols resolved from configuration")

    train_kwargs = dict(
        timeframe=args.timeframe,
        lookback_days=int(args.lookback_days),
        symbols=symbols,
        model_config_path=(args.model_config or None),
        min_rows=(int(args.min_rows) if int(args.min_rows) > 0 else None),
        target_threshold=(float(args.target_threshold) if not np.isnan(args.target_threshold) else None),
    )
    if args.use_db:
        out = train_global_from_db(**train_kwargs)
    else:
        out = train_global_from_kite(**train_kwargs)
    logger.info(
        "Saved global ensemble {} version {} at {}",
        out.model_name,
        out.version,
        out.artifact_path,
    )


if __name__ == "__main__":
    main()
