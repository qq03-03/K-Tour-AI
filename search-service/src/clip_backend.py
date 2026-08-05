"""CLIP 재사용과 PostgreSQL/pgvector 검색을 담당하는 실제 검색 백엔드."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
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


MODEL_NAME = "openai/clip-vit-base-patch32"
EXPECTED_DIMENSION = 512
SearchSource = Literal["text", "image"]

# 현재 남이섬 샘플에는 region 필드가 없고 기존 적재 코드가 place_name을
# region 열에 넣었다. 실제 규격에 region이 포함되면 이 보정표는 제거할 수 있다.
_PLACE_REGION_FALLBACKS = {
    "nami_island": "강원",
    "남이섬": "강원",
}
_SEASON_CANONICAL = {
    "spring": "봄",
    "summer": "여름",
    "autumn": "가을",
    "fall": "가을",
    "winter": "겨울",
}
_TIME_CANONICAL = {
    "dawn": "새벽",
    "morning": "아침",
    "day": "낮",
    "daytime": "낮",
    "evening": "해질녘",
    "sunset": "해질녘",
    "dusk": "해질녘",
    "night": "밤",
}


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
        started = perf_counter()
        self._model = CLIPModel.from_pretrained(
            self.model_name,
            local_files_only=self.local_files_only,
        ).to(self.device)
        self._processor = CLIPProcessor.from_pretrained(
            self.model_name,
            local_files_only=self.local_files_only,
        )
        self._model.eval()
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

    def __init__(self, config: DatabaseConfig) -> None:
        self._config = config

    def list_segments(self) -> list[dict[str, Any]]:
        query = """
            SELECT
                vs.segment_id, vs.video_id, vs.start_time, vs.end_time,
                vs.keyframe_path, vs.summary, vs.region, vs.spot_name,
                vs.tags, vs.mood_tags, vs.season_tags, vs.metadata,
                vs.place_id, vs.drama_title,
                representative.keyframe_id,
                representative.keyframe_path,
                representative.description,
                representative.time_of_day,
                representative.mood,
                representative.activity,
                representative.scene_elements,
                representative.metadata
            FROM video_segments AS vs
            JOIN segment_embeddings AS se ON se.segment_id = vs.segment_id
            LEFT JOIN LATERAL (
                SELECT
                    sk.keyframe_id,
                    sk.keyframe_path,
                    sk.description,
                    sk.time_of_day,
                    sk.mood,
                    sk.activity,
                    sk.scene_elements,
                    sk.metadata
                FROM segment_keyframes AS sk
                WHERE sk.segment_id = vs.segment_id
                ORDER BY sk.keyframe_id
                LIMIT 1
            ) AS representative ON TRUE
            ORDER BY vs.segment_id
        """
        with psycopg.connect(self._config.connection_string) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()
        return [self._segment_from_row(row) for row in rows]

    def search(
        self,
        query_vector: np.ndarray,
        source: SearchSource,
        *,
        candidate_ids: Sequence[str],
        top_k: int,
    ) -> list[dict[str, Any]]:
        if source not in {"text", "image"}:
            raise ValueError(f"지원하지 않는 검색 방식입니다: {source}")
        if top_k < 1:
            raise ValueError("top_k는 1 이상이어야 합니다.")
        if not candidate_ids:
            return []

        vector = _normalize_vector(query_vector)
        order_column = sql.Identifier(
            "text_distance" if source == "text" else "image_distance"
        )
        query = sql.SQL(
            """
            SELECT
                vs.segment_id,
                best_keyframe.keyframe_id,
                best_keyframe.keyframe_path,
                vs.place_id,
                vs.region,
                vs.spot_name,
                vs.drama_title,
                best_keyframe.description,
                best_keyframe.time_of_day,
                best_keyframe.mood,
                best_keyframe.activity,
                best_keyframe.scene_elements,
                vs.video_id,
                vs.start_time,
                vs.end_time,
                se.text_embedding <=> %s AS text_distance,
                best_keyframe.image_distance,
                vs.summary
            FROM video_segments AS vs
            JOIN segment_embeddings AS se
                ON se.segment_id = vs.segment_id
            JOIN LATERAL (
                SELECT
                    sk.keyframe_id,
                    sk.keyframe_path,
                    sk.description,
                    sk.time_of_day,
                    sk.mood,
                    sk.activity,
                    sk.scene_elements,
                    ke.image_embedding <=> %s AS image_distance
                FROM segment_keyframes AS sk
                JOIN keyframe_embeddings AS ke
                    ON ke.keyframe_id = sk.keyframe_id
                WHERE sk.segment_id = vs.segment_id
                  AND ke.image_embedding IS NOT NULL
                ORDER BY image_distance, sk.keyframe_id
                LIMIT 1
            ) AS best_keyframe ON TRUE
            WHERE se.text_embedding IS NOT NULL
              AND vs.segment_id = ANY(%s)
            ORDER BY {order_column}, vs.segment_id
            LIMIT %s
            """
        ).format(order_column=order_column)

        with psycopg.connect(self._config.connection_string) as connection:
            register_vector(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (vector, vector, list(candidate_ids), int(top_k)),
                )
                rows = cursor.fetchall()
        return [self._search_result_from_row(row, source) for row in rows]

    @staticmethod
    def _search_result_from_row(
        row: Sequence[Any],
        source: SearchSource,
    ) -> dict[str, Any]:
        text_score = 1.0 - float(row[15])
        image_score = 1.0 - float(row[16])
        source_score = text_score if source == "text" else image_score
        return {
            "segment_id": str(row[0]),
            "keyframe_id": str(row[1]),
            "keyframe_path": str(row[2]),
            "place_id": row[3],
            "region": row[4],
            "place_name": row[5],
            "spot_name": row[5],
            "drama_title": row[6],
            "description": row[7],
            "time_of_day": _canonical_scalar(row[8], _TIME_CANONICAL),
            "mood": list(row[9] or []),
            "activity": list(row[10] or []),
            "scene_elements": list(row[11] or []),
            "landscape": list(row[11] or []),
            "video_id": row[12],
            "start_time": float(row[13]),
            "end_time": float(row[14]),
            "start_sec": float(row[13]),
            "end_sec": float(row[14]),
            "text_score": text_score,
            "image_score": image_score,
            "score": source_score,
            "summary": row[17],
        }

    @staticmethod
    def _segment_from_row(row: Sequence[Any]) -> dict[str, Any]:
        raw_metadata = row[11]
        if isinstance(raw_metadata, list) and raw_metadata:
            segment_metadata = raw_metadata[0] if isinstance(raw_metadata[0], dict) else {}
        else:
            segment_metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
        keyframe_metadata = (
            row[21] if len(row) > 21 and isinstance(row[21], dict) else {}
        )
        metadata = {**segment_metadata, **keyframe_metadata}
        place_name = metadata.get("place_name") or row[7]
        stored_region = row[6]
        if stored_region and str(stored_region).casefold() == str(place_name).casefold():
            stored_region = None
        region = (
            metadata.get("region")
            or stored_region
            or _PLACE_REGION_FALLBACKS.get(str(place_name).casefold())
            or "unknown"
        )
        tags = list(row[8] or [])
        moods = list(
            (row[18] if len(row) > 18 else None)
            or metadata.get("mood")
            or row[9]
            or []
        )
        season_tags = list(row[10] or [])
        season = metadata.get("season")
        if not season and season_tags:
            season = season_tags[0]
        return {
            "segment_id": row[0],
            "video_id": row[1],
            "start_time": float(row[2]),
            "end_time": float(row[3]),
            "start_sec": float(row[2]),
            "end_sec": float(row[3]),
            "keyframe_id": row[14] if len(row) > 14 else metadata.get("keyframe_id"),
            "keyframe_path": (row[15] if len(row) > 15 else None) or row[4],
            "description": (row[16] if len(row) > 16 else None) or metadata.get("description") or row[5],
            "region": region,
            "place_name": place_name,
            "place_id": (row[12] if len(row) > 12 else None) or metadata.get("place_id"),
            "drama_title": (row[13] if len(row) > 13 else None) or metadata.get("drama_title"),
            "city": metadata.get("city"),
            "address": metadata.get("address"),
            "spot_name": metadata.get("spot_name") or row[7],
            "season": _canonical_scalar(season, _SEASON_CANONICAL),
            "time_of_day": _canonical_scalar(
                (row[17] if len(row) > 17 else None) or metadata.get("time_of_day"),
                _TIME_CANONICAL,
            ),
            "mood": moods,
            "activity": list(
                (row[19] if len(row) > 19 else None)
                or metadata.get("activity")
                or []
            ),
            "landscape": list(
                (row[20] if len(row) > 20 else None)
                or metadata.get("scene_elements")
                or tags
            ),
            "scene_elements": list(
                (row[20] if len(row) > 20 else None)
                or metadata.get("scene_elements")
                or tags
            ),
            "category": list(metadata.get("category") or []),
            "metadata": metadata,
        }


def _canonical_scalar(
    value: object,
    aliases: Mapping[str, str],
) -> str:
    if not isinstance(value, str) or not value.strip():
        return "unknown"
    cleaned = value.strip()
    return aliases.get(cleaned.casefold(), cleaned)
