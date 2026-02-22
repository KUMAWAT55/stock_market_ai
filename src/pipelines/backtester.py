from __future__ import annotations

from datetime import date
from time import perf_counter

import numpy as np
import pandas as pd
from loguru import logger
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.linear_model import SGDRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.pipelines.predictor import FEATURE_COLUMNS, _build_features


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def _direction(x: np.ndarray) -> np.ndarray:
    return np.where(x > 0.001, 1, np.where(x < -0.001, -1, 0))


def _score_predictions(
    symbol: str,
    model_name: str,
    y_true: list[float],
    y_pred: list[float],
) -> dict | None:
    if not y_true or not y_pred:
        return None

    y_true_arr = np.array(y_true, dtype=float)
    y_pred_arr = np.array(y_pred, dtype=float)
    n = int(len(y_true_arr))

    direction_true = _direction(y_true_arr)
    direction_pred = _direction(y_pred_arr)
    directional_accuracy = float((direction_true == direction_pred).mean())

    mae = float(np.mean(np.abs(y_true_arr - y_pred_arr)))
    rmse = _rmse(y_true_arr, y_pred_arr)

    market_curve = np.cumprod(1.0 + y_true_arr)
    strategy_curve = np.cumprod(1.0 + (np.sign(y_pred_arr) * y_true_arr))

    cumulative_return = float(market_curve[-1] - 1.0)
    strategy_return = float(strategy_curve[-1] - 1.0)

    return {
        "symbol": symbol,
        "model_name": model_name,
        "run_date": date.today(),
        "sample_count": n,
        "directional_accuracy": directional_accuracy,
        "mae": mae,
        "rmse": rmse,
        "avg_true_return": float(np.mean(y_true_arr)),
        "avg_pred_return": float(np.mean(y_pred_arr)),
        "cumulative_return": cumulative_return,
        "strategy_return": strategy_return,
    }


def run_backtest_models(
    symbol: str,
    price_df: pd.DataFrame,
    news_df: pd.DataFrame,
    min_train_rows: int = 100,
    step: int = 4,
    train_window: int = 260,
    max_eval_points: int = 80,
) -> list[dict]:
    start_ts = perf_counter()
    if price_df is None or price_df.empty:
        return []

    data = _build_features(price_df, news_df)
    data = data.dropna(subset=FEATURE_COLUMNS + ["target_return"]).copy()
    data = data[np.isfinite(data[FEATURE_COLUMNS + ["target_return"]]).all(axis=1)].copy()

    if len(data) < (min_train_rows + 15):
        logger.warning(f"Backtest skipped for {symbol}: insufficient rows ({len(data)})")
        return []

    x = data[FEATURE_COLUMNS].astype(float)
    y = data["target_return"].astype(float)

    has_xgb = False
    XGBRegressor = None
    try:
        from xgboost import XGBRegressor as _XGBRegressor

        has_xgb = True
        XGBRegressor = _XGBRegressor
    except Exception as e:
        logger.warning(f"XGBoost backtest disabled for {symbol}: {e}")

    model_order = [
        "sgd_regression_v1",
        "random_forest_v1",
        "extra_trees_v1",
    ]
    if has_xgb and XGBRegressor is not None:
        model_order.append("xgboost_v1")

    model_predictions: dict[str, dict[int, float]] = {
        model_name: {} for model_name in model_order
    }
    true_by_index: dict[int, float] = {}

    eval_indices = list(range(min_train_rows, len(data), max(1, step)))
    if max_eval_points > 0 and len(eval_indices) > max_eval_points:
        eval_indices = eval_indices[-max_eval_points:]

    for i in eval_indices:
        train_start = max(0, i - train_window) if train_window and train_window > 0 else 0
        x_train = x.iloc[train_start:i]
        y_train = y.iloc[train_start:i]
        x_test = x.iloc[i : i + 1]
        y_actual = float(y.iloc[i])
        true_by_index[i] = y_actual

        try:
            sgd_model = make_pipeline(
                StandardScaler(),
                SGDRegressor(
                    loss="huber",
                    penalty="elasticnet",
                    alpha=0.0005,
                    l1_ratio=0.15,
                    max_iter=1400,
                    tol=1e-4,
                    random_state=42,
                ),
            )
            sgd_model.fit(x_train, y_train)
            model_predictions["sgd_regression_v1"][i] = float(sgd_model.predict(x_test)[0])
        except Exception as e:
            logger.debug(f"Backtest SGD failure for {symbol} at index {i}: {e}")

        try:
            rf_model = RandomForestRegressor(
                n_estimators=120,
                max_depth=6,
                min_samples_leaf=3,
                random_state=42,
            )
            rf_model.fit(x_train, y_train)
            model_predictions["random_forest_v1"][i] = float(rf_model.predict(x_test)[0])
        except Exception as e:
            logger.debug(f"Backtest RF failure for {symbol} at index {i}: {e}")

        try:
            et_model = ExtraTreesRegressor(
                n_estimators=180,
                max_depth=7,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=1,
            )
            et_model.fit(x_train, y_train)
            model_predictions["extra_trees_v1"][i] = float(et_model.predict(x_test)[0])
        except Exception as e:
            logger.debug(f"Backtest ET failure for {symbol} at index {i}: {e}")

        if has_xgb and XGBRegressor is not None:
            try:
                xgb_model = XGBRegressor(
                    n_estimators=120,
                    max_depth=4,
                    learning_rate=0.05,
                    subsample=0.9,
                    colsample_bytree=0.8,
                    objective="reg:squarederror",
                    random_state=42,
                    n_jobs=1,
                )
                xgb_model.fit(x_train, y_train)
                model_predictions["xgboost_v1"][i] = float(xgb_model.predict(x_test)[0])
            except Exception as e:
                logger.debug(f"Backtest XGB failure for {symbol} at index {i}: {e}")

    common_eval_indices = set(eval_indices)
    for model_name in model_order:
        common_eval_indices &= set(model_predictions[model_name].keys())
    common_eval_indices = sorted(common_eval_indices)

    if not common_eval_indices:
        logger.warning(
            f"Backtest skipped for {symbol}: no common evaluation points across models"
        )
        return []

    dropped_eval_points = len(eval_indices) - len(common_eval_indices)
    if dropped_eval_points > 0:
        logger.warning(
            f"Backtest aligned for {symbol}: dropped {dropped_eval_points} eval points to keep a shared sample set"
        )

    y_true_common = [true_by_index[i] for i in common_eval_indices]

    results: list[dict] = []
    for model_name in model_order:
        y_pred_common = [model_predictions[model_name][i] for i in common_eval_indices]
        row = _score_predictions(symbol, model_name, y_true_common, y_pred_common)
        if row is not None:
            results.append(row)

    if results:
        ensemble_pred = (
            np.array(
                [
                    [model_predictions[model_name][i] for i in common_eval_indices]
                    for model_name in model_order
                ],
                dtype=float,
            )
            .mean(axis=0)
            .tolist()
        )
        ensemble_row = _score_predictions(
            symbol,
            "ensemble_v1",
            y_true_common,
            ensemble_pred,
        )
        if ensemble_row is not None:
            results.append(ensemble_row)

    elapsed = perf_counter() - start_ts
    logger.info(
        f"Backtest finished for {symbol}: {len(common_eval_indices)} common eval points in {elapsed:.2f}s"
    )

    return results
