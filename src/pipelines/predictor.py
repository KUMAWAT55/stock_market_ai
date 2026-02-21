from __future__ import annotations

import numpy as np
import pandas as pd
from loguru import logger
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LogisticRegression


FEATURE_COLUMNS = [
    "ret_1d",
    "ret_3d",
    "hl_spread",
    "oc_change",
    "volume_chg",
    "ma5_ratio",
    "ma10_ratio",
    "volatility_10d",
    "sentiment_score",
]


def _coerce_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _direction_from_return(predicted_return: float) -> str:
    if predicted_return > 0.001:
        return "up"
    if predicted_return < -0.001:
        return "down"
    return "flat"


def _build_features(price_df: pd.DataFrame, news_df: pd.DataFrame) -> pd.DataFrame:
    data = price_df.copy()
    data["date"] = pd.to_datetime(data["date"])
    data = data.sort_values("date")

    numeric_cols = ["open", "high", "low", "close", "volume"]
    for col in numeric_cols:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    safe_close = data["close"].replace(0, np.nan)
    safe_open = data["open"].replace(0, np.nan)

    data["ret_1d"] = data["close"].pct_change(1)
    data["ret_3d"] = data["close"].pct_change(3)
    data["hl_spread"] = (data["high"] - data["low"]) / safe_close
    data["oc_change"] = (data["close"] - data["open"]) / safe_open
    data["volume_chg"] = data["volume"].pct_change(1)
    data["ma5_ratio"] = (data["close"] / data["close"].rolling(5).mean()) - 1.0
    data["ma10_ratio"] = (data["close"] / data["close"].rolling(10).mean()) - 1.0
    data["volatility_10d"] = data["close"].pct_change().rolling(10).std()

    news_daily = pd.DataFrame(columns=["date", "sentiment_score"])
    if news_df is not None and not news_df.empty:
        news_daily = news_df.copy()
        news_daily["published_at"] = pd.to_datetime(news_daily["published_at"], errors="coerce")
        news_daily = (
            news_daily.dropna(subset=["published_at"])
            .assign(date=lambda d: d["published_at"].dt.date)
            .groupby("date", as_index=False)["sentiment_score"]
            .mean()
        )
        news_daily["date"] = pd.to_datetime(news_daily["date"])

    data = data.merge(news_daily, on="date", how="left")
    data["sentiment_score"] = data["sentiment_score"].fillna(0.0)

    data["target_return"] = data["close"].shift(-1) / safe_close - 1.0
    data = _coerce_numeric(data, FEATURE_COLUMNS + ["target_return"])
    data[FEATURE_COLUMNS + ["target_return"]] = data[
        FEATURE_COLUMNS + ["target_return"]
    ].replace([np.inf, -np.inf], np.nan)
    data["target_class"] = (data["target_return"] > 0).astype(float)
    return data


def train_and_predict_next_day(
    symbol: str,
    price_df: pd.DataFrame,
    news_df: pd.DataFrame,
) -> list[dict]:
    if price_df is None or price_df.empty:
        logger.warning(f"Prediction skipped for {symbol}: no price data")
        return []

    data = _build_features(price_df, news_df)
    data = _coerce_numeric(data, FEATURE_COLUMNS + ["target_return", "target_class"])
    train_data = data.dropna(subset=FEATURE_COLUMNS + ["target_return", "target_class"]).copy()
    train_data = train_data[
        np.isfinite(train_data[FEATURE_COLUMNS + ["target_return", "target_class"]]).all(axis=1)
    ].copy()

    # Keep a minimum sample size so the model is meaningful.
    if len(train_data) < 60:
        logger.warning(f"Prediction skipped for {symbol}: insufficient rows ({len(train_data)})")
        return []

    split_idx = int(len(train_data) * 0.8)
    x_train = train_data.iloc[:split_idx][FEATURE_COLUMNS].astype(float)
    y_train = train_data.iloc[:split_idx]["target_return"].astype(float)
    x_test = train_data.iloc[split_idx:][FEATURE_COLUMNS].astype(float)
    y_test = train_data.iloc[split_idx:]["target_return"].astype(float)
    y_train_class = train_data.iloc[:split_idx]["target_class"].astype(int)
    y_test_class = train_data.iloc[split_idx:]["target_class"].astype(int)

    predict_pool = data.dropna(subset=FEATURE_COLUMNS).copy()
    predict_pool = predict_pool[np.isfinite(predict_pool[FEATURE_COLUMNS]).all(axis=1)]
    if predict_pool.empty:
        logger.warning(f"Prediction skipped for {symbol}: no finite feature row available")
        return []

    latest_row = predict_pool.iloc[-1]
    latest_x = latest_row[FEATURE_COLUMNS].to_frame().T.astype(float)

    last_close = float(latest_row["close"])
    prediction_date = pd.to_datetime(latest_row["date"]).date()
    target_date = (pd.Timestamp(prediction_date) + pd.offsets.BDay(1)).date()
    abs_move_scale = float(train_data["target_return"].abs().median())
    abs_move_scale = abs_move_scale if abs_move_scale > 0 else 0.01

    predictions: list[dict] = []

    rf_model = RandomForestRegressor(
        n_estimators=300,
        max_depth=6,
        min_samples_leaf=3,
        random_state=42,
    )
    rf_model.fit(x_train, y_train)

    rf_score = None
    if len(x_test) >= 2:
        rf_score = float(rf_model.score(x_test, y_test))
    rf_return = float(rf_model.predict(latest_x)[0])
    predictions.append({
        "symbol": symbol,
        "prediction_date": prediction_date,
        "target_date": target_date,
        "predicted_return": rf_return,
        "predicted_close": last_close * (1.0 + rf_return),
        "direction": _direction_from_return(rf_return),
        "model_name": "random_forest_v1",
        "train_rows": int(len(train_data)),
        "r2_score": rf_score,
    })

    logistic_accuracy = None
    try:
        log_model = LogisticRegression(max_iter=1000, random_state=42)
        log_model.fit(x_train, y_train_class)
        if len(x_test) >= 2:
            logistic_accuracy = float(log_model.score(x_test, y_test_class))
        prob_up = float(log_model.predict_proba(latest_x)[0][1])
        log_return = (prob_up - 0.5) * 2.0 * abs_move_scale
        predictions.append({
            "symbol": symbol,
            "prediction_date": prediction_date,
            "target_date": target_date,
            "predicted_return": log_return,
            "predicted_close": last_close * (1.0 + log_return),
            "direction": _direction_from_return(log_return),
            "model_name": "logistic_v1",
            "train_rows": int(len(train_data)),
            "r2_score": logistic_accuracy,
        })
    except Exception as e:
        logger.warning(f"Logistic model skipped for {symbol}: {e}")

    try:
        from xgboost import XGBRegressor

        xgb_model = XGBRegressor(
            n_estimators=350,
            max_depth=4,
            learning_rate=0.04,
            subsample=0.9,
            colsample_bytree=0.8,
            objective="reg:squarederror",
            random_state=42,
            n_jobs=1,
        )
        xgb_model.fit(x_train, y_train)
        xgb_score = None
        if len(x_test) >= 2:
            xgb_score = float(xgb_model.score(x_test, y_test))
        xgb_return = float(xgb_model.predict(latest_x)[0])
        predictions.append({
            "symbol": symbol,
            "prediction_date": prediction_date,
            "target_date": target_date,
            "predicted_return": xgb_return,
            "predicted_close": last_close * (1.0 + xgb_return),
            "direction": _direction_from_return(xgb_return),
            "model_name": "xgboost_v1",
            "train_rows": int(len(train_data)),
            "r2_score": xgb_score,
        })
    except Exception as e:
        logger.warning(f"XGBoost model skipped for {symbol}: {e}")

    if not predictions:
        return []

    ensemble_return = float(np.mean([p["predicted_return"] for p in predictions]))
    ensemble_score_values = [p["r2_score"] for p in predictions if p["r2_score"] is not None]
    ensemble_score = float(np.mean(ensemble_score_values)) if ensemble_score_values else None
    predictions.append({
        "symbol": symbol,
        "prediction_date": prediction_date,
        "target_date": target_date,
        "predicted_return": ensemble_return,
        "predicted_close": last_close * (1.0 + ensemble_return),
        "direction": _direction_from_return(ensemble_return),
        "model_name": "ensemble_v1",
        "train_rows": int(len(train_data)),
        "r2_score": ensemble_score,
    })

    return predictions
