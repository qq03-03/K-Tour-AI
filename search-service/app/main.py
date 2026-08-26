import logging
import os
from contextlib import asynccontextmanager

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.query_parser import RuleBasedQueryParser

from app.dependencies import (
    ConfigurationError,
    get_pipeline,
    get_query_parser,
    get_runtime,
    get_segments_repository,
    get_spots_repository,
    ping_database,
)
from app.schemas import SearchRequest, SearchResponse
from app.search_response import build_search_results

# Without this, the root logger has no handler attached, so every
# logger.info() call below (and everywhere else in the app) is silently
# dropped instead of reaching stdout -- Uvicorn only configures its own
# uvicorn/uvicorn.access loggers, not the application's or third-party
# libraries'. Railway captures stdout, so this is what actually makes our
# logs (and the openai DEBUG logs below) visible in its log viewer.
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

# The openai SDK only logs retry attempts and HTTP status codes (e.g. 429
# rate limits, 5xx) at DEBUG level via its own logger. Surfacing that here
# is how we tell "the model was just slow" apart from "the SDK retried a
# failed request" when diagnosing a slow /api/search call.
logging.getLogger("openai").setLevel(logging.DEBUG)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # SKIP_CLIP_WARMUP은 테스트 환경에서 설정된다 (tests/app/conftest.py 참고).
    # `with TestClient(app) as client:` 형태는 lifespan을 실제로 발동시키므로,
    # 이 가드가 없으면 무거운 실제 CLIP 모델 로딩이 테스트 중 트리거될 수 있다.
    if not os.getenv("SKIP_CLIP_WARMUP"):
        get_runtime().warmup()
    yield


app = FastAPI(title="K-Tour AI Search API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://qq03-03.github.io", "http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(psycopg.Error)
def handle_db_connection_error(request: Request, exc: psycopg.Error) -> JSONResponse:
    logger.error("DB error handling %s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=503, content={"detail": "데이터베이스에 연결할 수 없어요. 잠시 후 다시 시도해주세요."})


@app.exception_handler(ConfigurationError)
def handle_configuration_error(request: Request, exc: ConfigurationError) -> JSONResponse:
    logger.error("Configuration error handling %s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=503, content={"detail": "서비스 설정에 문제가 있어 요청을 처리할 수 없어요. 잠시 후 다시 시도해주세요."})


@app.get("/health")
def health(_: None = Depends(ping_database)) -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/search", response_model=SearchResponse)
def search(request: SearchRequest, pipeline=Depends(get_pipeline), parser=Depends(get_query_parser)):
    candidate_k = request.candidate_k or max(request.top_k * 5, 50)
    # 값이 없는(None) 필드, 빈 목록, 그리고 공백뿐인 문자열 요소는
    # 필터를 적용하지 않는 것으로 취급한다.
    raw_hard_filters = {
        "place_id": request.place_id,
        "drama_title": request.drama_title,
        "region": request.region,
        "city": request.city,
        "season": request.season,
        "time_of_day": request.time_of_day,
    }
    filter_overrides: dict[str, list[str]] = {}
    for field_name, values in raw_hard_filters.items():
        if not values:
            continue
        cleaned_values = [value for value in values if value and value.strip()]
        if cleaned_values:
            filter_overrides[field_name] = cleaned_values

    # theme is a source_segment_id hard filter, not a video_segments column,
    # so it's kept out of filter_overrides (which maps 1:1 to DB columns via
    # to_filter_arguments/filter_segments) and passed to the pipeline
    # separately as theme_ids.
    theme_ids = [value for value in (request.theme or []) if value and value.strip()] or None

    # When the UI already sent explicit filter values (a theme, season, or
    # drama title click), the LLM parser's job -- extracting structured
    # filters from free text -- is redundant: it costs an OpenAI round trip
    # for no benefit, since filter_overrides already wins over anything the
    # parser would infer (see multimodal_pipeline.search). Use the fast
    # rule-based parser for those requests and reserve the LLM parser for
    # genuine free-text queries.
    effective_parser = RuleBasedQueryParser() if (filter_overrides or theme_ids) else parser

    output = pipeline.search(
        request.q,
        parser=effective_parser,
        top_k=candidate_k,
        search_depth=candidate_k,
        methods=("rrf",),
        filter_overrides=filter_overrides or None,
        theme_ids=theme_ids,
    )
    logger.info(
        "search completed filter_overrides=%s theme_ids=%s used_llm_parser=%s latency_ms=%s",
        filter_overrides or None,
        theme_ids,
        effective_parser is parser,
        output.get("latency_ms"),
    )
    results = build_search_results(output, top_k=request.top_k, lang=request.lang)
    return SearchResponse(
        results=results,
        fallback_used=output["fallback_used"],
        fallback_reason=output["fallback_reason"],
    )


@app.get("/api/spots")
def list_spots(region: str | None = None, repository=Depends(get_spots_repository)):
    return repository.list_spots(region)


@app.get("/api/spots/{spot_id}")
def get_spot(spot_id: int, repository=Depends(get_spots_repository)):
    spot = repository.get_spot(spot_id)
    if spot is None:
        raise HTTPException(status_code=404, detail="해당 관광지를 찾을 수 없어요.")
    return spot


@app.get("/api/segments")
def list_segments(
    video_id: str | None = None,
    place_id: str | None = None,
    drama_title: str | None = None,
    repository=Depends(get_segments_repository),
):
    return repository.list_segments(video_id, place_id, drama_title)


@app.get("/api/segments/{segment_id}")
def get_segment(segment_id: str, repository=Depends(get_segments_repository)):
    segment = repository.get_segment(segment_id)
    if segment is None:
        raise HTTPException(status_code=404, detail="해당 영상 구간을 찾을 수 없어요.")
    return segment
