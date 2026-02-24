from __future__ import annotations

import argparse
import pickle
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from loguru import logger
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from config.config import get_settings
from data.kite_client import KiteHistoricalClient
from database.db_manager import DatabaseManager
from features.feature_pipeline import FEATURE_COLUMNS, build_training_frame
from models.model_registry import ModelRegistry

try:
    from xgboost import XGBClassifier
except Exception:  # pragma: no cover
    XGBClassifier = None


@dataclass(slots=True)
class TrainOutput:
    artifact_path: Path
    model_name: str
    version: str
    metrics: dict[str, float]


def _default_min_rows(timeframe: str) -> int:
    # Daily models naturally have fewer samples than intraday models.
    return 40 if timeframe == "1d" else 200


def _make_model(seed: int = 42) -> tuple[str, Any]:
    if XGBClassifier is not None:
        model = XGBClassifier(
            n_estimators=300,
            max_depth=5,
            learning_rate=0.04,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_lambda=1.5,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=seed,
            n_jobs=4,
        )
        return "xgboost_direction", model

    model = RandomForestClassifier(
        n_estimators=350,
        max_depth=8,
        min_samples_leaf=3,
        random_state=seed,
        n_jobs=4,
        class_weight="balanced_subsample",
    )
    return "random_forest_direction", model


def _evaluate(y_true: np.ndarray, y_pred: np.ndarray, prob_up: np.ndarray) -> dict[str, float]:
    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
    }
    if len(np.unique(y_true)) > 1:
        metrics["roc_auc"] = float(roc_auc_score(y_true, prob_up))
    return metrics


def walk_forward_validation(
    x: pd.DataFrame,
    y: pd.Series,
    model_factory: Callable[[], Any],
    min_train_rows: int = 160,
    step: int = 5,
) -> dict[str, float]:
    if len(x) <= min_train_rows + 1:
        return {"wf_points": 0.0, "wf_accuracy": 0.0}

    preds: list[int] = []
    truths: list[int] = []

    for idx in range(min_train_rows, len(x) - 1, step):
        x_train = x.iloc[:idx]
        y_train = y.iloc[:idx]
        x_test = x.iloc[idx : idx + 1]
        y_test = y.iloc[idx : idx + 1]

        model = model_factory()
        model.fit(x_train, y_train)
        pred = int(model.predict(x_test)[0])

        preds.append(pred)
        truths.append(int(y_test.iloc[0]))

    if not truths:
        return {"wf_points": 0.0, "wf_accuracy": 0.0}

    return {
        "wf_points": float(len(truths)),
        "wf_accuracy": float(accuracy_score(truths, preds)),
    }


def train_from_candles(
    symbol: str,
    timeframe: str,
    candles: pd.DataFrame,
    min_rows: int | None = None,
) -> TrainOutput:
    settings = get_settings()
    db_manager = DatabaseManager()
    registry = ModelRegistry(db_manager)

    frame = build_training_frame(candles, horizon_steps=1)
    required_rows = min_rows if min_rows is not None else _default_min_rows(timeframe)
    if frame.empty or len(frame) < required_rows:
        min_date = frame["candle_start"].min() if not frame.empty and "candle_start" in frame.columns else None
        max_date = frame["candle_start"].max() if not frame.empty and "candle_start" in frame.columns else None
        raise ValueError(
            f"Insufficient rows for training {symbol} {timeframe}: {len(frame)} "
            f"(required={required_rows}, range={min_date} -> {max_date})"
        )

    x = frame[FEATURE_COLUMNS].astype(float)
    y = frame["target_up"].astype(int)

    split_idx = int(len(frame) * 0.8)
    x_train, x_test = x.iloc[:split_idx], x.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    model_name, model = _make_model()
    model.fit(x_train, y_train)

    pred = model.predict(x_test)
    if hasattr(model, "predict_proba"):
        prob_up = model.predict_proba(x_test)[:, 1]
    else:
        raw = model.predict(x_test)
        prob_up = np.asarray(raw, dtype=float)

    metrics = _evaluate(y_test.to_numpy(), np.asarray(pred, dtype=int), prob_up=prob_up)
    wf = walk_forward_validation(
        x=x,
        y=y,
        model_factory=lambda: _make_model()[1],
        min_train_rows=max(120, int(0.4 * len(x))),
        step=5,
    )
    metrics.update(wf)

    version = registry.build_version(model_name=model_name, timeframe=timeframe)
    artifact_path = settings.model_artifact_dir / f"{symbol}_{model_name}_{timeframe}_{version}.pkl"
    with artifact_path.open("wb") as f:
        pickle.dump(model, f)

    registry.register(
        model_name=model_name,
        timeframe=timeframe,
        version=version,
        artifact_path=artifact_path,
        metrics=metrics,
        feature_list=FEATURE_COLUMNS,
    )

    db_manager.insert_backtest_metrics(
        symbol=symbol,
        timeframe=timeframe,
        model_name=model_name,
        model_version=version,
        metrics=metrics,
    )

    logger.info("Training completed for {} {} -> {}", symbol, timeframe, artifact_path)
    return TrainOutput(artifact_path=artifact_path, model_name=model_name, version=version, metrics=metrics)


def train_from_kite(
    symbol: str,
    instrument_token: int,
    timeframe: str,
    lookback_days: int = 180,
    min_rows: int | None = None,
) -> TrainOutput:
    historical = KiteHistoricalClient()
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=lookback_days)
    candles = historical.fetch_candles(
        instrument_token=instrument_token,
        timeframe=timeframe,
        from_dt=start_dt,
        to_dt=end_dt,
    )
    candles["symbol"] = symbol
    return train_from_candles(symbol=symbol, timeframe=timeframe, candles=candles, min_rows=min_rows)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train direction model from Kite historical candles")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--instrument-token", type=int, required=True)
    parser.add_argument("--timeframe", choices=["1m", "5m", "15m", "1h", "1d"], required=True)
    parser.add_argument("--lookback-days", type=int, default=240)
    parser.add_argument(
        "--min-rows",
        type=int,
        default=0,
        help="Minimum training rows required. Default: timeframe-aware (15m=200, 1d=40).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    out = train_from_kite(
        symbol=args.symbol,
        instrument_token=args.instrument_token,
        timeframe=args.timeframe,
        lookback_days=args.lookback_days,
        min_rows=(args.min_rows if args.min_rows > 0 else None),
    )
    logger.info("Saved model {} version {} at {}", out.model_name, out.version, out.artifact_path)


if __name__ == "__main__":
    main()
