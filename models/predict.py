from __future__ import annotations
"""Runtime model loading and signal inference helpers."""

import pickle
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from config.config import get_settings
from models.lstm_proxy import AttentionReadyLSTMProxyClassifier, LSTMProxyClassifier
from models.model_registry import ModelDescriptor


@dataclass(slots=True)
class PredictionResult:
    """Normalized prediction payload consumed by realtime engine."""

    signal: str
    confidence: float
    prob_up: float
    prob_down: float
    explainability: dict[str, float]


def _calibrate_prob(calibrator: dict[str, Any] | None, raw_prob: float) -> float:
    if not calibrator:
        return raw_prob
    method = str(calibrator.get("method", "")).lower()
    model = calibrator.get("model")
    if model is None:
        return raw_prob
    if method == "isotonic":
        return float(np.clip(model.predict([raw_prob])[0], 0.0, 1.0))
    if method == "platt":
        return float(np.clip(model.predict_proba([[raw_prob]])[0][1], 0.0, 1.0))
    return raw_prob


def _extract_estimator(model: Any) -> Any:
    """Extract final estimator from optional sklearn Pipeline wrapper."""
    if hasattr(model, "named_steps") and model.named_steps:
        # Use the last estimator in a sklearn pipeline.
        return list(model.named_steps.values())[-1]
    return model


class _CompatUnpickler(pickle.Unpickler):
    """Backwards-compatible unpickler for legacy artifacts saved from __main__/mp_main."""

    _CLASS_MAP: dict[tuple[str, str], type[Any]] = {
        ("__main__", "LSTMProxyClassifier"): LSTMProxyClassifier,
        ("mp_main", "LSTMProxyClassifier"): LSTMProxyClassifier,
        ("models.train", "LSTMProxyClassifier"): LSTMProxyClassifier,
        ("__main__", "AttentionReadyLSTMProxyClassifier"): AttentionReadyLSTMProxyClassifier,
        ("mp_main", "AttentionReadyLSTMProxyClassifier"): AttentionReadyLSTMProxyClassifier,
        ("models.train", "AttentionReadyLSTMProxyClassifier"): AttentionReadyLSTMProxyClassifier,
    }

    def find_class(self, module: str, name: str) -> Any:
        mapped = self._CLASS_MAP.get((module, name))
        if mapped is not None:
            return mapped
        return super().find_class(module, name)


@lru_cache(maxsize=16)
def load_model(artifact_path: str) -> Any:
    """Load model artifact once and cache in-process."""
    with Path(artifact_path).open("rb") as f:
        return _CompatUnpickler(f).load()


def _predict_proba(model: Any, features: pd.DataFrame) -> tuple[float, float]:
    """Return (prob_up, prob_down) across heterogeneous estimator types."""
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
    """Apply configured probability thresholds to map into BUY/SELL/HOLD."""
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
    """Approximate local feature contribution using coefficient/importance weighting."""
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


def _ensemble_explainability(
    feature_importance: dict[str, float],
    feature_vector: dict[str, Any],
    top_k: int = 10,
) -> dict[str, float]:
    if not feature_importance:
        return {}
    scored: list[tuple[str, float]] = []
    for feature, importance in feature_importance.items():
        value = abs(float(feature_vector.get(feature, 0.0)))
        scored.append((feature, float(importance) * value))
    total = sum(score for _, score in scored) or 1.0
    scored.sort(key=lambda item: item[1], reverse=True)
    return {name: round(score / total, 6) for name, score in scored[:top_k]}


def _predict_from_ensemble_bundle(bundle: dict[str, Any], features_row: dict[str, Any]) -> tuple[float, float, dict[str, float]]:
    feature_columns = list(bundle.get("feature_columns", []))
    if not feature_columns:
        raise ValueError("Ensemble bundle missing feature_columns")

    x = pd.DataFrame([{feature: float(features_row.get(feature, 0.0)) for feature in feature_columns}])
    base_models = dict(bundle.get("base_models", {}))
    base_order = list(bundle.get("base_model_order", base_models.keys()))
    strategy = str(bundle.get("strategy", "stacking"))
    base_probs: list[float] = []

    for name in base_order:
        model = base_models.get(name)
        if model is None:
            continue
        if hasattr(model, "predict_proba"):
            prob = float(model.predict_proba(x)[0][1])
        else:
            pred = float(model.predict(x)[0])
            prob = float(np.clip(pred, 0.0, 1.0))
        base_probs.append(prob)

    if not base_probs:
        raise ValueError("No base models available for ensemble prediction")

    if strategy == "soft_voting":
        raw_prob = float(np.mean(base_probs))
    else:
        meta = bundle.get("meta_model")
        if meta is None:
            raw_prob = float(np.mean(base_probs))
        else:
            meta_frame = pd.DataFrame([dict(zip(base_order, base_probs))])
            raw_prob = float(meta.predict_proba(meta_frame)[0][1])

    prob_up = _calibrate_prob(bundle.get("calibrator"), raw_prob)
    prob_up = float(np.clip(prob_up, 0.0, 1.0))
    prob_down = 1.0 - prob_up
    explain = _ensemble_explainability(
        feature_importance=dict(bundle.get("feature_importance", {})),
        feature_vector=features_row,
    )
    return prob_up, prob_down, explain


def predict_signal(
    descriptor: ModelDescriptor,
    features_row: dict[str, Any],
    feature_columns: list[str],
) -> PredictionResult:
    """Run end-to-end inference and emit probability, signal, and explainability."""
    settings = get_settings()
    model = load_model(descriptor.artifact_path)
    if isinstance(model, dict) and model.get("artifact_type") == "stacking_ensemble_v1":
        prob_up, prob_down, explain = _predict_from_ensemble_bundle(model, features_row)
    else:
        frame = pd.DataFrame([{col: features_row.get(col, 0.0) for col in feature_columns}])
        prob_up, prob_down = _predict_proba(model, frame)
        explain = _explainability(model, frame.iloc[0], feature_columns=feature_columns)

    buy_threshold, sell_threshold = settings.signal_thresholds_for_timeframe(descriptor.timeframe)
    signal = _signal_from_prob(prob_up, buy_threshold, sell_threshold)
    confidence = float(max(prob_up, prob_down))
    return PredictionResult(
        signal=signal,
        confidence=round(confidence, 6),
        prob_up=round(prob_up, 6),
        prob_down=round(prob_down, 6),
        explainability=explain,
    )
