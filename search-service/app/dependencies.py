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
def _runtime() -> ClipRuntime:
    return ClipRuntime(local_files_only=True)


@lru_cache
def _repository() -> PgVectorRepository:
    return PgVectorRepository(DatabaseConfig.from_environment())


@lru_cache
def get_pipeline():
    from src.multimodal_pipeline import MultimodalSearchPipeline

    return MultimodalSearchPipeline(runtime=_runtime(), repository=_repository())


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
