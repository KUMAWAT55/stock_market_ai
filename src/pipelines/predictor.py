from __future__ import annotations

import numpy as np
import pandas as pd
from loguru import logger
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.linear_model import SGDRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


FEATURE_COLUMNS = [
    "ret_1bar",
    "ret_3bar",
    "ret_12bar",
    "hl_spread",
    "oc_change",
    "volume_chg",
    "ma5_ratio",
    "ma20_ratio",
    "volatility_20bar",
    "volume_zscore_20",
    "minute_sin",
    "minute_cos",
    "session_progress",
    "sentiment_6h",
]


def _estimate_session_bounds_minutes(date_series: pd.Series) -> tuple[int, int]:
    dt = pd.to_datetime(date_series, errors="coerce").dropna()
    if dt.empty:
        return 9 * 60 + 15, 15 * 60 + 30

    frame = pd.DataFrame({"date": dt})
    frame["session_day"] = frame["date"].dt.floor("D")
    first_per_day = frame.groupby("session_day")["date"].min()
    last_per_day = frame.groupby("session_day")["date"].max()

    if first_per_day.empty or last_per_day.empty:
        return 9 * 60 + 15, 15 * 60 + 30

    open_minutes = (first_per_day.dt.hour * 60 + first_per_day.dt.minute).astype(int)
    close_minutes = (last_per_day.dt.hour * 60 + last_per_day.dt.minute).astype(int)

    open_min = int(open_minutes.median())
    close_min = int(close_minutes.median())
    if close_min <= open_min:
        return 9 * 60 + 15, 15 * 60 + 30
    return open_min, close_min


def _next_intraday_target_timestamp(date_series: pd.Series, prediction_date: pd.Timestamp) -> pd.Timestamp:
    dt = pd.to_datetime(date_series, errors="coerce").dropna().sort_values()
    if dt.empty:
        return pd.to_datetime(prediction_date) + pd.offsets.BDay(1)

    deltas = dt.diff().dropna()
    positive_deltas = deltas[deltas > pd.Timedelta(0)]
    intraday_deltas = positive_deltas[positive_deltas < pd.Timedelta(hours=4)]
    if intraday_deltas.empty:
        return pd.to_datetime(prediction_date) + pd.offsets.BDay(1)

    bar_delta = intraday_deltas.median()
    open_minute, close_minute = _estimate_session_bounds_minutes(dt)

    prediction_ts = pd.to_datetime(prediction_date)
    candidate = prediction_ts + bar_delta

    def _session_start(ts: pd.Timestamp) -> pd.Timestamp:
        return ts.normalize() + pd.Timedelta(minutes=open_minute)

    candidate_minutes = candidate.hour * 60 + candidate.minute

    if candidate.weekday() >= 5:
        return _session_start(candidate + pd.offsets.BDay(1))
    if candidate_minutes > close_minute:
        return _session_start(candidate + pd.offsets.BDay(1))
    if candidate_minutes < open_minute:
        return _session_start(candidate)
    return candidate


def _next_session_close_timestamp(date_series: pd.Series, prediction_date: pd.Timestamp) -> pd.Timestamp:
    dt = pd.to_datetime(date_series, errors="coerce").dropna().sort_values()
    if dt.empty:
        return pd.to_datetime(prediction_date) + pd.offsets.BDay(1)

    frame = pd.DataFrame({"date": dt})
    frame["session_day"] = frame["date"].dt.floor("D")
    session_closes = frame.groupby("session_day")["date"].max().sort_index()

    prediction_ts = pd.to_datetime(prediction_date)
    future_closes = session_closes[session_closes.index > prediction_ts.normalize()]
    if not future_closes.empty:
        return pd.to_datetime(future_closes.iloc[0])

    _, close_minute = _estimate_session_bounds_minutes(dt)
    next_business_day = prediction_ts + pd.offsets.BDay(1)
    return next_business_day.normalize() + pd.Timedelta(minutes=close_minute)


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

    data["ret_1bar"] = data["close"].pct_change(1)
    data["ret_3bar"] = data["close"].pct_change(3)
    data["ret_12bar"] = data["close"].pct_change(12)
    data["hl_spread"] = (data["high"] - data["low"]) / safe_close
    data["oc_change"] = (data["close"] - data["open"]) / safe_open
    data["volume_chg"] = data["volume"].pct_change(1)
    data["ma5_ratio"] = (data["close"] / data["close"].rolling(5).mean()) - 1.0
    data["ma20_ratio"] = (data["close"] / data["close"].rolling(20).mean()) - 1.0
    data["volatility_20bar"] = data["close"].pct_change().rolling(20).std()

    volume_mean_20 = data["volume"].rolling(20).mean()
    volume_std_20 = data["volume"].rolling(20).std()
    data["volume_zscore_20"] = (data["volume"] - volume_mean_20) / volume_std_20.replace(0, np.nan)

    minute_of_day = (data["date"].dt.hour * 60) + data["date"].dt.minute
    session_start = 9 * 60 + 15
    session_length_mins = 375
    day_phase = ((minute_of_day - session_start) / session_length_mins).clip(0.0, 1.0)
    data["minute_sin"] = np.sin(2.0 * np.pi * day_phase)
    data["minute_cos"] = np.cos(2.0 * np.pi * day_phase)
    data["session_progress"] = day_phase

    news_intraday = pd.DataFrame(columns=["published_at", "sentiment_6h"])
    if news_df is not None and not news_df.empty:
        news_intraday = news_df.copy()
        news_intraday["published_at"] = pd.to_datetime(news_intraday["published_at"], errors="coerce")
        news_intraday["sentiment_score"] = pd.to_numeric(
            news_intraday["sentiment_score"], errors="coerce"
        )
        news_intraday = news_intraday.dropna(subset=["published_at"]).sort_values("published_at")
        news_intraday["sentiment_score"] = news_intraday["sentiment_score"].fillna(0.0)
        news_intraday["sentiment_6h"] = (
            news_intraday
            .rolling("6h", on="published_at")["sentiment_score"]
            .mean()
        )
        news_intraday = news_intraday[["published_at", "sentiment_6h"]].dropna(subset=["published_at"])

    data = data.sort_values("date")
    if not news_intraday.empty:
        data = pd.merge_asof(
            data,
            news_intraday,
            left_on="date",
            right_on="published_at",
            direction="backward",
            tolerance=pd.Timedelta(hours=6),
        )
    if "sentiment_6h" in data.columns:
        data["sentiment_6h"] = pd.to_numeric(data["sentiment_6h"], errors="coerce").fillna(0.0)
    else:
        data["sentiment_6h"] = 0.0

    data["target_return"] = data["close"].shift(-1) / safe_close - 1.0
    data["session_day"] = data["date"].dt.floor("D")
    # Keep intraday bars, but map every bar from day D to the close of day D+1.
    session_close_by_day = data.groupby("session_day")["close"].last().sort_index()
    next_session_close_by_day = session_close_by_day.shift(-1)
    data["next_session_close"] = data["session_day"].map(next_session_close_by_day)
    data["target_next_close_return"] = data["next_session_close"] / safe_close - 1.0
    data = _coerce_numeric(data, FEATURE_COLUMNS + ["target_return"])
    data = _coerce_numeric(data, ["target_next_close_return"])
    data[FEATURE_COLUMNS + ["target_return", "target_next_close_return"]] = data[
        FEATURE_COLUMNS + ["target_return", "target_next_close_return"]
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
    data = _coerce_numeric(data, FEATURE_COLUMNS + ["target_return"])
    train_data = data.dropna(subset=FEATURE_COLUMNS + ["target_return"]).copy()
    train_data = train_data[
        np.isfinite(train_data[FEATURE_COLUMNS + ["target_return"]]).all(axis=1)
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

    predict_pool = data.dropna(subset=FEATURE_COLUMNS).copy()
    predict_pool = predict_pool[np.isfinite(predict_pool[FEATURE_COLUMNS]).all(axis=1)]
    if predict_pool.empty:
        logger.warning(f"Prediction skipped for {symbol}: no finite feature row available")
        return []

    latest_row = predict_pool.iloc[-1]
    latest_x = latest_row[FEATURE_COLUMNS].to_frame().T.astype(float)

    last_close = float(latest_row["close"])
    prediction_date = pd.to_datetime(latest_row["date"])
    deltas = data["date"].diff().dropna()
    if not deltas.empty and deltas.median() < pd.Timedelta(days=1):
        target_date = _next_intraday_target_timestamp(data["date"], prediction_date)
    else:
        target_date = prediction_date + pd.offsets.BDay(1)

    predictions: list[dict] = []

    sgd_model = make_pipeline(
        StandardScaler(),
        SGDRegressor(
            loss="huber",
            penalty="elasticnet",
            alpha=0.0005,
            l1_ratio=0.15,
            max_iter=2500,
            tol=1e-4,
            random_state=42,
        ),
    )
    sgd_model.fit(x_train, y_train)
    sgd_score = None
    if len(x_test) >= 2:
        sgd_score = float(sgd_model.score(x_test, y_test))
    sgd_return = float(sgd_model.predict(latest_x)[0])
    predictions.append({
        "symbol": symbol,
        "prediction_date": prediction_date,
        "target_date": target_date,
        "predicted_return": sgd_return,
        "predicted_close": last_close * (1.0 + sgd_return),
        "direction": _direction_from_return(sgd_return),
        "model_name": "sgd_regression_v1",
        "train_rows": int(len(train_data)),
        "r2_score": sgd_score,
    })

    rf_model = RandomForestRegressor(
        n_estimators=280,
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

    et_model = ExtraTreesRegressor(
        n_estimators=320,
        max_depth=7,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=1,
    )
    et_model.fit(x_train, y_train)
    et_score = None
    if len(x_test) >= 2:
        et_score = float(et_model.score(x_test, y_test))
    et_return = float(et_model.predict(latest_x)[0])
    predictions.append({
        "symbol": symbol,
        "prediction_date": prediction_date,
        "target_date": target_date,
        "predicted_return": et_return,
        "predicted_close": last_close * (1.0 + et_return),
        "direction": _direction_from_return(et_return),
        "model_name": "extra_trees_v1",
        "train_rows": int(len(train_data)),
        "r2_score": et_score,
    })

    try:
        from xgboost import XGBRegressor

        xgb_model = XGBRegressor(
            n_estimators=320,
            max_depth=4,
            learning_rate=0.05,
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

    # Additional horizon: next session close prediction (model-wise + ensemble).
    next_close_target = _next_session_close_timestamp(data["date"], prediction_date)
    next_close_data = data.dropna(subset=FEATURE_COLUMNS + ["target_next_close_return"]).copy()
    next_close_data = next_close_data[
        np.isfinite(next_close_data[FEATURE_COLUMNS + ["target_next_close_return"]]).all(axis=1)
    ].copy()

    if len(next_close_data) >= 60:
        next_split_idx = int(len(next_close_data) * 0.8)
        x_train_nc = next_close_data.iloc[:next_split_idx][FEATURE_COLUMNS].astype(float)
        y_train_nc = next_close_data.iloc[:next_split_idx]["target_next_close_return"].astype(float)
        x_test_nc = next_close_data.iloc[next_split_idx:][FEATURE_COLUMNS].astype(float)
        y_test_nc = next_close_data.iloc[next_split_idx:]["target_next_close_return"].astype(float)

        next_close_predictions: list[dict] = []

        def _append_next_close_prediction(
            model_name: str,
            predicted_return: float,
            model_score: float | None,
        ) -> None:
            next_close_predictions.append(
                {
                    "symbol": symbol,
                    "prediction_date": prediction_date,
                    "target_date": next_close_target,
                    "predicted_return": float(predicted_return),
                    "predicted_close": last_close * (1.0 + float(predicted_return)),
                    "direction": _direction_from_return(float(predicted_return)),
                    "model_name": model_name,
                    "train_rows": int(len(next_close_data)),
                    "r2_score": model_score,
                }
            )

        sgd_nc = make_pipeline(
            StandardScaler(),
            SGDRegressor(
                loss="huber",
                penalty="elasticnet",
                alpha=0.0005,
                l1_ratio=0.15,
                max_iter=2500,
                tol=1e-4,
                random_state=42,
            ),
        )
        sgd_nc.fit(x_train_nc, y_train_nc)
        sgd_nc_score = float(sgd_nc.score(x_test_nc, y_test_nc)) if len(x_test_nc) >= 2 else None
        sgd_nc_return = float(sgd_nc.predict(latest_x)[0])
        _append_next_close_prediction("sgd_next_close_v1", sgd_nc_return, sgd_nc_score)

        rf_nc = RandomForestRegressor(
            n_estimators=280,
            max_depth=6,
            min_samples_leaf=3,
            random_state=42,
        )
        rf_nc.fit(x_train_nc, y_train_nc)
        rf_nc_score = float(rf_nc.score(x_test_nc, y_test_nc)) if len(x_test_nc) >= 2 else None
        rf_nc_return = float(rf_nc.predict(latest_x)[0])
        _append_next_close_prediction("random_forest_next_close_v1", rf_nc_return, rf_nc_score)

        et_nc = ExtraTreesRegressor(
            n_estimators=320,
            max_depth=7,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=1,
        )
        et_nc.fit(x_train_nc, y_train_nc)
        et_nc_score = float(et_nc.score(x_test_nc, y_test_nc)) if len(x_test_nc) >= 2 else None
        et_nc_return = float(et_nc.predict(latest_x)[0])
        _append_next_close_prediction("extra_trees_next_close_v1", et_nc_return, et_nc_score)

        try:
            from xgboost import XGBRegressor

            xgb_nc = XGBRegressor(
                n_estimators=320,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.9,
                colsample_bytree=0.8,
                objective="reg:squarederror",
                random_state=42,
                n_jobs=1,
            )
            xgb_nc.fit(x_train_nc, y_train_nc)
            xgb_nc_score = float(xgb_nc.score(x_test_nc, y_test_nc)) if len(x_test_nc) >= 2 else None
            xgb_nc_return = float(xgb_nc.predict(latest_x)[0])
            _append_next_close_prediction("xgboost_next_close_v1", xgb_nc_return, xgb_nc_score)
        except Exception as e:
            logger.warning(f"XGBoost next-close model skipped for {symbol}: {e}")

        if next_close_predictions:
            next_close_return = float(np.mean([p["predicted_return"] for p in next_close_predictions]))
            next_close_score_values = [p["r2_score"] for p in next_close_predictions if p["r2_score"] is not None]
            next_close_score = float(np.mean(next_close_score_values)) if next_close_score_values else None
            next_close_predictions.append(
                {
                    "symbol": symbol,
                    "prediction_date": prediction_date,
                    "target_date": next_close_target,
                    "predicted_return": next_close_return,
                    "predicted_close": last_close * (1.0 + next_close_return),
                    "direction": _direction_from_return(next_close_return),
                    "model_name": "ensemble_next_close_v1",
                    "train_rows": int(len(next_close_data)),
                    "r2_score": next_close_score,
                }
            )
            predictions.extend(next_close_predictions)

    return predictions
