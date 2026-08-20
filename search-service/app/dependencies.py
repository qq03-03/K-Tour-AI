import os
from functools import lru_cache

from src.clip_backend import ClipRuntime, DatabaseConfig, PgVectorRepository
from src.interfaces import QueryParser
from src.llm_query_parser import LLMQueryParser
from src.openai_client import DEFAULT_QUERY_MODEL, OpenAIStructuredClient
from src.query_parser import RuleBasedQueryParser

from app.segments_repository import SegmentsRepository
from app.spots_repository import SpotsRepository


@lru_cache
def get_runtime() -> ClipRuntime:
    return ClipRuntime(local_files_only=True)


class ConfigurationError(RuntimeError):
    """환경변수 등 설정 문제로 서비스를 시작할 수 없을 때 발생한다."""


@lru_cache
def _repository() -> PgVectorRepository:
    try:
        return PgVectorRepository(DatabaseConfig.from_environment())
    except ValueError as exc:
        raise ConfigurationError(str(exc)) from exc


@lru_cache
def get_pipeline():
    from src.multimodal_pipeline import MultimodalSearchPipeline

    return MultimodalSearchPipeline(runtime=get_runtime(), repository=_repository())


def get_query_parser() -> QueryParser:
    if os.getenv("OPENAI_API_KEY"):
        return LLMQueryParser(OpenAIStructuredClient(model=DEFAULT_QUERY_MODEL))
    return RuleBasedQueryParser()


def get_spots_repository() -> SpotsRepository:
    import psycopg

    return SpotsRepository(connection_factory=lambda: psycopg.connect(_repository()._config.connection_string))


def get_segments_repository() -> SegmentsRepository:
    import psycopg

    return SegmentsRepository(connection_factory=lambda: psycopg.connect(_repository()._config.connection_string))


def ping_database() -> None:
    """DB에 가볍게 왕복 요청을 보내 연결 가능 여부를 확인한다 (/health 용)."""
    import psycopg

    with psycopg.connect(_repository()._config.connection_string) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
