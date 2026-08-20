"""CLIP 재사용과 PostgreSQL/pgvector 검색을 담당하는 실제 검색 백엔드."""

from __future__ import annotations

import os
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

import numpy as np
import psycopg
import torch
from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from psycopg import sql
from transformers import CLIPModel, CLIPProcessor

from .segment_row import segment_from_row


MODEL_NAME = "openai/clip-vit-base-patch32"
EXPECTED_DIMENSION = 512
SearchSource = Literal["text", "image"]


def _normalize_vector(vector: Any) -> np.ndarray:
    array = np.asarray(vector, dtype=np.float32)
    if array.ndim != 1 or array.shape[0] != EXPECTED_DIMENSION:
        raise ValueError("CLIP 질의 벡터는 512차원 1차원 배열이어야 합니다.")
    if not np.isfinite(array).all():
        raise ValueError("CLIP 질의 벡터에 NaN 또는 무한대가 있습니다.")
    norm = float(np.linalg.norm(array))
    if norm == 0:
        raise ValueError("CLIP 질의 벡터는 0 벡터일 수 없습니다.")
    return (array / norm).astype(np.float32)


def _extract_features(features: Any, projection: Any) -> Any:
    if not hasattr(features, "pooler_output"):
        return features
    pooled = features.pooler_output
    if pooled.shape[-1] == EXPECTED_DIMENSION:
        return pooled
    if projection is None:
        raise ValueError("CLIP projection 계층이 필요합니다.")
    return projection(pooled)


class ClipRuntime:
    """프로세스 수명 동안 CLIP 모델을 한 번만 지연 로딩해 재사용한다."""

    def __init__(
        self,
        *,
        model_name: str = MODEL_NAME,
        device: str | None = None,
        local_files_only: bool = True,
    ) -> None:
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.local_files_only = local_files_only
        self._model: Any | None = None
        self._processor: Any | None = None
        self._load_lock = threading.Lock()
        self.load_count = 0
        self.load_latency_ms = 0.0

    def warmup(self) -> None:
        """서비스 시작 시 명시적으로 모델을 미리 올릴 수 있다."""

        self._ensure_loaded()

    def encode_text(self, text: str) -> np.ndarray:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("검색 문장은 빈 문자열일 수 없습니다.")
        self._ensure_loaded()
        assert self._model is not None
        assert self._processor is not None

        inputs = self._processor(
            text=[text.strip()],
            return_tensors="pt",
            padding=True,
            truncation=True,
        )
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        with torch.inference_mode():
            features = self._model.get_text_features(**inputs)
            features = _extract_features(
                features,
                getattr(self._model, "text_projection", None),
            )
        return _normalize_vector(features.detach().cpu().numpy()[0])

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            started = perf_counter()
            model = CLIPModel.from_pretrained(
                self.model_name,
                local_files_only=self.local_files_only,
            ).to(self.device)
            processor = CLIPProcessor.from_pretrained(
                self.model_name,
                local_files_only=self.local_files_only,
            )
            model.eval()
            self._processor = processor
            self._model = model
            self.load_count += 1
            self.load_latency_ms = (perf_counter() - started) * 1000.0


@dataclass(frozen=True)
class DatabaseConfig:
    connection_string: str

    @classmethod
    def from_environment(cls, env_path: str | Path | None = None) -> "DatabaseConfig":
        if env_path is not None:
            load_dotenv(Path(env_path), override=False)
        required = (
            "POSTGRES_HOST",
            "POSTGRES_PORT",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_DB",
        )
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise ValueError("DB 환경변수가 없습니다: " + ", ".join(missing))
        return cls(
            " ".join(
                (
                    f"host={os.environ['POSTGRES_HOST']}",
                    f"port={os.environ['POSTGRES_PORT']}",
                    f"user={os.environ['POSTGRES_USER']}",
                    f"password={os.environ['POSTGRES_PASSWORD']}",
                    f"dbname={os.environ['POSTGRES_DB']}",
                )
            )
        )


class PgVectorRepository:
    """구간 메타데이터와 두 임베딩 검색을 같은 DB에서 조회한다."""

    _COLUMNS: dict[SearchSource, str] = {
        "text": "text_embedding",
        "image": "image_embedding",
    }

    def __init__(self, config: DatabaseConfig) -> None:
        self._config = config

    def list_segments(self) -> list[dict[str, Any]]:
        query = """
            SELECT
                vs.segment_id, vs.source_segment_id, vs.video_id,
                vs.place_id, vs.place_name, vs.region, vs.city,
                vs.drama_title, vs.start_time, vs.end_time,
                vs.caption, vs.season, vs.time_of_day, vs.keyframe_path,
                vs.mood_tags, vs.activity_tags, vs.scene_elements,
                vs.k_culture_elements
            FROM video_segments AS vs
            JOIN segment_embeddings AS se ON se.segment_id = vs.segment_id
            ORDER BY vs.segment_id
        """
        with psycopg.connect(self._config.connection_string) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()
        return [segment_from_row(row) for row in rows]

    def search(
        self,
        query_vector: np.ndarray,
        source: SearchSource,
        *,
        candidate_ids: Sequence[str],
        top_k: int,
    ) -> list[dict[str, Any]]:
        if source not in self._COLUMNS:
            raise ValueError(f"지원하지 않는 검색 방식입니다: {source}")
        if top_k < 1:
            raise ValueError("top_k는 1 이상이어야 합니다.")
        if not candidate_ids:
            return []

        vector = _normalize_vector(query_vector)
        column = sql.Identifier(self._COLUMNS[source])
        query = sql.SQL(
            """
            SELECT
                vs.segment_id,
                1 - (se.{column} <=> %s) AS similarity
            FROM segment_embeddings AS se
            JOIN video_segments AS vs ON vs.segment_id = se.segment_id
            WHERE se.{column} IS NOT NULL
              AND vs.segment_id = ANY(%s)
            ORDER BY se.{column} <=> %s, vs.segment_id
            LIMIT %s
            """
        ).format(column=column)

        with psycopg.connect(self._config.connection_string) as connection:
            register_vector(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (vector, list(candidate_ids), vector, int(top_k)),
                )
                rows = cursor.fetchall()
        return [
            {"segment_id": str(segment_id), "score": float(similarity)}
            for segment_id, similarity in rows
        ]
