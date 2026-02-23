from __future__ import annotations

import pickle
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from config.config import get_settings
from models.model_registry import ModelDescriptor


@dataclass(slots=True)
class PredictionResult:
    signal: str
    confidence: float
    prob_up: float
    prob_down: float
    explainability: dict[str, float]


def _extract_estimator(model: Any) -> Any:
    if hasattr(model, "named_steps") and model.named_steps:
        # Use the last estimator in a sklearn pipeline.
        return list(model.named_steps.values())[-1]
    return model


@lru_cache(maxsize=16)
def load_model(artifact_path: str) -> Any:
    with Path(artifact_path).open("rb") as f:
        return pickle.load(f)


def _predict_proba(model: Any, features: pd.DataFrame) -> tuple[float, float]:
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(features)
        prob_down = float(probs[0][0])
        prob_up = float(probs[0][1]) if probs.shape[1] > 1 else 1.0 - prob_down
        return prob_up, prob_down

    if hasattr(model, "decision_function"):
        decision = float(model.decision_function(features)[0])
        prob_up = 1.0 / (1.0 + np.exp(-decision))
        return prob_up, 1.0 - prob_up

    pred = float(model.predict(features)[0])
    prob_up = float(np.clip(pred, 0.0, 1.0))
    return prob_up, 1.0 - prob_up


def _signal_from_prob(prob_up: float, buy_threshold: float, sell_threshold: float) -> str:
    if prob_up >= buy_threshold:
        return "BUY"
    if prob_up <= sell_threshold:
        return "SELL"
    return "HOLD"


def _explainability(
    model: Any,
    feature_vector: pd.Series,
    feature_columns: list[str],
    top_k: int = 8,
) -> dict[str, float]:
    estimator = _extract_estimator(model)

    if hasattr(estimator, "feature_importances_"):
        importances = np.asarray(estimator.feature_importances_, dtype=float)
        if importances.size == len(feature_columns):
            weights = np.abs(importances)
        else:
            weights = np.ones(len(feature_columns), dtype=float)
    elif hasattr(estimator, "coef_"):
        coef = np.asarray(estimator.coef_).reshape(-1)
        if coef.size == len(feature_columns):
            weights = np.abs(coef)
        else:
            weights = np.ones(len(feature_columns), dtype=float)
    else:
        weights = np.ones(len(feature_columns), dtype=float)

    values = np.abs(feature_vector.to_numpy(dtype=float))
    contributions = weights * values
    total = contributions.sum()
    if total <= 0:
        total = 1.0

    pairs = sorted(
        ((feature_columns[idx], float(contributions[idx] / total)) for idx in range(len(feature_columns))),
        key=lambda item: item[1],
        reverse=True,
    )
    return {name: round(score, 6) for name, score in pairs[:top_k]}


def predict_signal(
    descriptor: ModelDescriptor,
    features_row: dict[str, Any],
    feature_columns: list[str],
) -> PredictionResult:
    settings = get_settings()
    frame = pd.DataFrame([{col: features_row.get(col, 0.0) for col in feature_columns}])
    model = load_model(descriptor.artifact_path)
    prob_up, prob_down = _predict_proba(model, frame)
    signal = _signal_from_prob(prob_up, settings.signal_buy_threshold, settings.signal_sell_threshold)
    confidence = float(max(prob_up, prob_down))
    explain = _explainability(model, frame.iloc[0], feature_columns=feature_columns)
    return PredictionResult(
        signal=signal,
        confidence=round(confidence, 6),
        prob_up=round(prob_up, 6),
        prob_down=round(prob_down, 6),
        explainability=explain,
    )
