from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from config.config import get_settings
from database.db_manager import DatabaseManager


@dataclass(slots=True)
class ModelDescriptor:
    model_name: str
    timeframe: str
    version: str
    artifact_path: str
    metrics: dict[str, Any]
    feature_list: list[str]


class ModelRegistry:
    """Tracks locally saved model artifacts and syncs active versions to PostgreSQL."""

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager
        self.settings = get_settings()
        self.artifact_dir = self.settings.model_artifact_dir
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    def build_version(self, model_name: str, timeframe: str) -> str:
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"{model_name}_{timeframe}_{ts}"

    def register(
        self,
        model_name: str,
        timeframe: str,
        version: str,
        artifact_path: Path,
        metrics: dict[str, Any],
        feature_list: list[str],
    ) -> ModelDescriptor:
        descriptor = ModelDescriptor(
            model_name=model_name,
            timeframe=timeframe,
            version=version,
            artifact_path=str(artifact_path),
            metrics=metrics,
            feature_list=feature_list,
        )
        meta_path = artifact_path.with_suffix(".meta.json")
        meta_path.write_text(
            json.dumps(
                {
                    "model_name": model_name,
                    "timeframe": timeframe,
                    "version": version,
                    "artifact_path": str(artifact_path),
                    "metrics": metrics,
                    "feature_list": feature_list,
                    "created_at": datetime.utcnow().isoformat(),
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        self.db_manager.upsert_model_registry(
            model_name=model_name,
            timeframe=timeframe,
            version=version,
            artifact_path=str(artifact_path),
            metrics=metrics,
            feature_list=feature_list,
        )
        logger.info("Registered model {} {} {}", model_name, timeframe, version)
        return descriptor

    def get_active(self, timeframe: str) -> ModelDescriptor | None:
        row = self.db_manager.get_active_model(timeframe)
        if row:
            return ModelDescriptor(
                model_name=row["model_name"],
                timeframe=row["timeframe"],
                version=row["version"],
                artifact_path=row["artifact_path"],
                metrics=row.get("metrics") or {},
                feature_list=row.get("feature_list") or [],
            )

        fallback = self._find_latest_local_artifact(timeframe)
        if fallback is None:
            return None
        logger.warning("Using local model artifact fallback for timeframe {}", timeframe)
        return fallback

    def _find_latest_local_artifact(self, timeframe: str) -> ModelDescriptor | None:
        candidates = sorted(self.artifact_dir.glob(f"*_direction_{timeframe}_*.pkl"))
        if not candidates:
            candidates = sorted(self.artifact_dir.glob(f"*_{timeframe}_*.pkl"))
        if not candidates:
            return None

        artifact = candidates[-1]
        meta_path = artifact.with_suffix(".meta.json")
        if meta_path.exists():
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
            return ModelDescriptor(
                model_name=str(payload.get("model_name", "direction_model")),
                timeframe=str(payload.get("timeframe", timeframe)),
                version=str(payload.get("version", artifact.stem)),
                artifact_path=str(payload.get("artifact_path", artifact)),
                metrics=dict(payload.get("metrics", {})),
                feature_list=list(payload.get("feature_list", [])),
            )

        return ModelDescriptor(
            model_name="direction_model",
            timeframe=timeframe,
            version=artifact.stem,
            artifact_path=str(artifact),
            metrics={},
            feature_list=[],
        )
