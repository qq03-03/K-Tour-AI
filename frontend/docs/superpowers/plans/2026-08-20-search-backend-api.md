# 검색·조회 백엔드 API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap the already-built and tested `search-service/` search logic in a FastAPI app (search + tourist-spot lookup + video-segment lookup + health check), and produce a deployable Docker image, so this can be deployed to Railway and connected to the frontend.

**Architecture:** A single FastAPI app under `search-service/app/` loads the CLIP model and DB connection once at startup and reuses them across requests, via `MultimodalSearchPipeline` from the existing `search-service/src/`. Route handlers depend on injected repository/pipeline objects (`fastapi.Depends`) so they can be tested with fakes, without needing a real Postgres+pgvector database or the CLIP/torch model installed.

**Tech Stack:** Python, FastAPI, Pydantic v2, psycopg (already a `search-service` dependency), pytest, `fastapi.testclient.TestClient`.

## Global Constraints

- Work happens on a new local branch `backend-search-api`, created from `origin/main` (the K-Tour-AI monorepo) — **not** from `frontend-origin-main` or `frontend-only`, which are an unrelated, disconnected history (the extracted frontend-only repo).
- Do not modify anything under `search-service/src/` except the one documented fix in Task 2. The rest of `search-service/` (159 passing tests) is trusted, working code — treat it as a dependency, not something to refactor.
- New app code goes under `search-service/app/`, matching the existing `search-service/` project root (its own `requirements.txt`, `tests/`, etc.).
- Route-layer and adapter-layer tests must run without a real Postgres database, the CLIP model, or an OpenAI API key — use fakes/dependency overrides. Full-stack verification (real DB + real model) is a manual step at the end (Task 10), since this environment doesn't have `torch`/`transformers` installed and installing them here risks the disk-space issues seen earlier this session.
- API response fields for `/api/search` must match `docs/search_api_contract.md` exactly: `rank, source_segment_id, segment_id, keyframe_id, keyframe_path, video_id, place_id, place_name, region, city, latitude, longitude, drama_title, start_time, end_time, season, time_of_day, description, mood, activity, scene_elements, k_culture_elements, text_score, image_score, text_rank, image_rank, final_score`.
- `keyframe_id` always equals `segment_id` (per the contract's fixed principle) — never a separate stored value.
- CORS must allow exactly `https://qq03-03.github.io` — never a wildcard.

---

### Task 1: Create the backend branch and merge in the existing search logic

**Files:** None created — this is a git setup task.

**Interfaces:**
- Produces: local branch `backend-search-api`, containing everything from `origin/main` plus everything from `origin/feature/search-core-kdh` (notably the `search-service/` directory), used as the base for every later task.

- [ ] **Step 1: Fetch the latest remote state**

```bash
cd "C:\Users\human\Desktop\K-Tour-AI"
git fetch origin
```

Expected: fetch completes, no errors.

- [ ] **Step 2: Create the branch from origin/main**

```bash
git checkout -b backend-search-api origin/main
```

Expected: `Switched to a new branch 'backend-search-api'`.

- [ ] **Step 3: Merge in the search logic**

```bash
git merge origin/feature/search-core-kdh --no-edit
```

Expected: merge completes without conflicts (verified ahead of time — `git merge-tree` between these two branches produced no conflict markers). If it does conflict, stop and resolve manually rather than guessing; do not use `git checkout --ours`/`--theirs` blindly.

- [ ] **Step 4: Verify the search-service directory is present**

```bash
ls search-service/src
```

Expected: lists `clip_backend.py`, `multimodal_pipeline.py`, `fusion.py`, `filters.py`, `interfaces.py`, `query_parser.py`, `llm_query_parser.py`, `openai_client.py`, `search.py`, `search_pipeline.py`, `vlm_metadata.py`, `data_loader.py`, `metrics.py`, `dummy_embedder.py`, `ollama_client.py`, `failure_analysis.py`, `multimodal_evaluation.py`, `query_parser_evaluation.py`, `__init__.py`.

- [ ] **Step 5: Commit the merge is already done by `git merge` — no additional commit needed.** Confirm the branch state:

```bash
git log --oneline -3
```

Expected: top commit is the merge commit (or a fast-forward to `feature/search-core-kdh`'s tip if `main` had no divergent history in that area).

---

### Task 2: Fix `list_segments()` to read the real 517-dataset columns

**Files:**
- Create: `search-service/src/segment_row.py`
- Modify: `search-service/src/clip_backend.py` (the `PgVectorRepository.list_segments()` query and `_segment_from_row()` method)
- Test: `search-service/tests/test_segment_row.py`
- Test: `search-service/tests/test_clip_backend.py`

**Interfaces:**
- Consumes: none new.
- Produces: `segment_from_row(row: Sequence[Any]) -> dict[str, Any]` in `search-service/src/segment_row.py`, converting a `video_segments` row (in the fixed column order `segment_id, source_segment_id, video_id, place_id, place_name, region, city, drama_title, start_time, end_time, caption, season, time_of_day, keyframe_path, mood_tags, activity_tags, scene_elements, k_culture_elements`) into a dict with keys `segment_id, source_segment_id, video_id, place_id, place_name, region, city, drama_title, start_time, end_time, description, season, time_of_day, keyframe_path, mood, activity, scene_elements, k_culture_elements`. Used by `PgVectorRepository.list_segments()` in this task and by `SegmentsRepository` in Task 8 — both query `video_segments` for the exact same 18 columns in this exact order, so both share this one row-mapping function instead of each defining their own.

**Why this is needed:** `list_segments()` as merged in Task 1 was written for an earlier prototype schema — it reads `place_name`/`description`/`drama_title`/etc. out of a JSONB `metadata` column. The real 517-segment data (loaded by `embedding-db/scripts/insert_embeddings.py`, already verified against `main`) writes these into dedicated `video_segments` columns instead (`place_id`, `place_name`, `region`, `city`, `drama_title`, `season`, `time_of_day`, `caption` for description, `activity_tags`, `scene_elements`, `k_culture_elements`, `source_segment_id`). Without this fix, `list_segments()` would return empty/wrong values for real data.

- [ ] **Step 1: Write the failing test for the shared row-mapping function**

Create `search-service/tests/test_segment_row.py`:

```python
from src.segment_row import segment_from_row


def test_segment_from_row_reads_the_517_dataset_columns():
    row = (
        "V007_P031_S002_SCENE_001",   # segment_id
        "V007_P031_S002",             # source_segment_id
        "V007_Z7u5SNDq0jw",           # video_id
        "P031",                       # place_id
        "충주 중앙탑공원",              # place_name
        "충청북도",                     # region
        "충주시",                      # city
        "사랑의 불시착",                # drama_title
        0.0,                          # start_time
        3.75,                         # end_time
        "A nighttime view of a brightly lit bridge over calm water.",  # description (caption column)
        "summer",                     # season
        "night",                      # time_of_day
        "keyframes/V007_Z7u5SNDq0jw/V007_P031_S002_SCENE_001.jpg",  # keyframe_path
        ["peaceful", "calm", "serene"],           # mood
        ["walking", "strolling"],                 # activity
        ["bridge", "water", "lights"],             # scene_elements
        ["K드라마성지"],                            # k_culture_elements
    )
    segment = segment_from_row(row)
    assert segment["segment_id"] == "V007_P031_S002_SCENE_001"
    assert segment["source_segment_id"] == "V007_P031_S002"
    assert segment["place_id"] == "P031"
    assert segment["place_name"] == "충주 중앙탑공원"
    assert segment["region"] == "충청북도"
    assert segment["city"] == "충주시"
    assert segment["drama_title"] == "사랑의 불시착"
    assert segment["description"] == "A nighttime view of a brightly lit bridge over calm water."
    assert segment["season"] == "summer"
    assert segment["time_of_day"] == "night"
    assert segment["mood"] == ["peaceful", "calm", "serene"]
    assert segment["activity"] == ["walking", "strolling"]
    assert segment["scene_elements"] == ["bridge", "water", "lights"]
    assert segment["k_culture_elements"] == ["K드라마성지"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd search-service && python -m pytest tests/test_segment_row.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.segment_row'`.

- [ ] **Step 3: Write the shared row-mapping function**

Create `search-service/src/segment_row.py`:

```python
from collections.abc import Sequence
from typing import Any


def segment_from_row(row: Sequence[Any]) -> dict[str, Any]:
    """Maps a video_segments row to a segment dict.

    Expects columns in exactly this order: segment_id, source_segment_id,
    video_id, place_id, place_name, region, city, drama_title, start_time,
    end_time, caption, season, time_of_day, keyframe_path, mood_tags,
    activity_tags, scene_elements, k_culture_elements.
    """
    return {
        "segment_id": row[0],
        "source_segment_id": row[1],
        "video_id": row[2],
        "place_id": row[3],
        "place_name": row[4],
        "region": row[5],
        "city": row[6],
        "drama_title": row[7],
        "start_time": float(row[8]),
        "end_time": float(row[9]),
        "description": row[10],
        "season": row[11],
        "time_of_day": row[12],
        "keyframe_path": row[13],
        "mood": list(row[14] or []),
        "activity": list(row[15] or []),
        "scene_elements": list(row[16] or []),
        "k_culture_elements": list(row[17] or []),
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd search-service && python -m pytest tests/test_segment_row.py -v`
Expected: PASS

- [ ] **Step 5: Write the failing test for `list_segments()` using the shared function**

Run: `cat search-service/tests/test_clip_backend.py | head -60` first, to confirm how existing tests fake a DB cursor/connection (they use a fake `psycopg.connect` via `monkeypatch` — follow the same pattern below, matching whatever fixture helper that file already defines; do not invent a second one).

Add to `search-service/tests/test_clip_backend.py`:

```python
def test_list_segments_uses_the_517_dataset_columns(monkeypatch):
    row = (
        "V007_P031_S002_SCENE_001", "V007_P031_S002", "V007_Z7u5SNDq0jw",
        "P031", "충주 중앙탑공원", "충청북도", "충주시", "사랑의 불시착",
        0.0, 3.75, "야경", "summer", "night", "keyframes/x.jpg",
        ["peaceful"], ["walking"], ["bridge"], ["K드라마성지"],
    )
    # Use this file's existing fake-connection pattern here to make
    # psycopg.connect(...) return a fake connection whose cursor's
    # fetchall() returns [row]. Name the helper the same way the rest of
    # this file already does.
    repository = PgVectorRepository(DatabaseConfig("fake-connection-string"))

    segments = repository.list_segments()

    assert segments == [
        {
            "segment_id": "V007_P031_S002_SCENE_001",
            "source_segment_id": "V007_P031_S002",
            "video_id": "V007_Z7u5SNDq0jw",
            "place_id": "P031",
            "place_name": "충주 중앙탑공원",
            "region": "충청북도",
            "city": "충주시",
            "drama_title": "사랑의 불시착",
            "start_time": 0.0,
            "end_time": 3.75,
            "description": "야경",
            "season": "summer",
            "time_of_day": "night",
            "keyframe_path": "keyframes/x.jpg",
            "mood": ["peaceful"],
            "activity": ["walking"],
            "scene_elements": ["bridge"],
            "k_culture_elements": ["K드라마성지"],
        }
    ]
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `cd search-service && python -m pytest tests/test_clip_backend.py::test_list_segments_uses_the_517_dataset_columns -v`
Expected: FAIL — either an import/setup error from the fake-connection wiring, or an assertion mismatch, since `list_segments()` still queries the old columns.

- [ ] **Step 7: Rewrite `list_segments()` to use the shared function**

In `search-service/src/clip_backend.py`, add the import at the top:

```python
from .segment_row import segment_from_row
```

Replace the `list_segments` method body:

```python
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
```

Delete the `_segment_from_row` static method entirely (replaced by the shared `segment_from_row` function). Delete the now-unused `_PLACE_REGION_FALLBACKS`, `_SEASON_CANONICAL`, `_TIME_CANONICAL` module-level dicts and the `_canonical_scalar` function if nothing else in the file references them (check with `grep -n "_PLACE_REGION_FALLBACKS\|_SEASON_CANONICAL\|_TIME_CANONICAL\|_canonical_scalar" search-service/src/clip_backend.py` — if any of the four names appear anywhere outside the definitions you're removing, keep that one and only delete the others).

- [ ] **Step 8: Run the test to verify it passes**

Run: `cd search-service && python -m pytest tests/test_clip_backend.py::test_list_segments_uses_the_517_dataset_columns -v`
Expected: PASS

- [ ] **Step 9: Run the full search-service test suite to check for regressions**

Run: `cd search-service && python -m pytest -q`
Expected: all tests pass except possibly other tests in `test_clip_backend.py` that asserted the *old* row shape/field names (e.g. `spot_name`, `landscape`, `category`, `start_sec`/`end_sec`) — if any fail for that reason, update those specific assertions to match the new field set the same way Step 5's test does; do not weaken assertions elsewhere to make unrelated failures disappear.

- [ ] **Step 10: Commit**

```bash
git add search-service/src/segment_row.py search-service/src/clip_backend.py search-service/tests/test_segment_row.py search-service/tests/test_clip_backend.py
git commit -m "Read segment metadata from dedicated columns, matching the real 517-dataset schema"
```

---

### Task 3: FastAPI app skeleton, CORS, and health check

**Files:**
- Create: `search-service/requirements-api.txt`
- Create: `search-service/app/__init__.py`
- Create: `search-service/app/main.py`
- Test: `search-service/tests/app/__init__.py`
- Test: `search-service/tests/app/test_health.py`

**Interfaces:**
- Produces: `app` (the `FastAPI` instance) importable as `from app.main import app`, with CORS configured and `GET /health` registered. Every later route task imports and extends this same `app` object.

- [ ] **Step 1: Add the API-layer dependencies**

Create `search-service/requirements-api.txt`:

```
fastapi==0.121.2
uvicorn[standard]==0.38.1
httpx==0.28.1
```

- [ ] **Step 2: Install them**

```bash
cd search-service
python -m pip install -r requirements-api.txt
```

Expected: installs without error (these are lightweight — no `torch`/`transformers` involved).

- [ ] **Step 3: Write the failing test**

Create `search-service/tests/app/__init__.py` (empty file, makes `tests/app` a package).

Create `search-service/tests/app/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_allows_the_frontend_origin():
    response = client.options(
        "/health",
        headers={
            "Origin": "https://qq03-03.github.io",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers["access-control-allow-origin"] == "https://qq03-03.github.io"
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `cd search-service && python -m pytest tests/app/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app'`.

- [ ] **Step 5: Write the app skeleton**

Create `search-service/app/__init__.py` (empty).

Create `search-service/app/main.py`:

```python
import psycopg
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(title="K-Tour AI Search API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://qq03-03.github.io"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(psycopg.OperationalError)
def handle_db_connection_error(request: Request, exc: psycopg.OperationalError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "데이터베이스에 연결할 수 없어요. 잠시 후 다시 시도해주세요."})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 6: Write the failing test for the DB error handler**

Add to `search-service/tests/app/test_health.py`:

```python
import psycopg


def test_db_connection_failure_returns_503_with_a_safe_message():
    @app.get("/__test_db_error")
    def _raise_db_error():
        raise psycopg.OperationalError("connection refused")

    response = client.get("/__test_db_error")
    assert response.status_code == 503
    assert "detail" in response.json()
    assert "connection refused" not in response.json()["detail"]
```

- [ ] **Step 7: Run the tests to verify everything passes**

Run: `cd search-service && python -m pytest tests/app/test_health.py -v`
Expected: PASS (3 tests)

- [ ] **Step 8: Commit**

```bash
git add search-service/requirements-api.txt search-service/app search-service/tests/app
git commit -m "Add FastAPI app skeleton with CORS and a health check"
```

---

### Task 4: Pydantic schemas for `/api/search`

**Files:**
- Create: `search-service/app/schemas.py`
- Test: `search-service/tests/app/test_schemas.py`

**Interfaces:**
- Consumes: none new.
- Produces: `SearchRequest` (Pydantic model), `SearchResultItem` (Pydantic model), `SearchResponse` (Pydantic model) — imported by Task 5 (`search_response.py`) and Task 6 (the route).

- [ ] **Step 1: Write the failing test**

Create `search-service/tests/app/test_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from app.schemas import SearchRequest, SearchResultItem, SearchResponse


def test_search_request_requires_only_query():
    request = SearchRequest(query="봄에 궁궐 산책")
    assert request.query == "봄에 궁궐 산책"
    assert request.lang == "ko"
    assert request.top_k == 5
    assert request.candidate_k is None
    assert request.place_id is None
    assert request.season is None


def test_search_request_accepts_all_filters():
    request = SearchRequest(
        query="여름 바다",
        lang="en",
        place_id=["N-P031"],
        drama_title=["사랑의 불시착"],
        region=["충청북도"],
        city=["충주시"],
        season=["summer"],
        time_of_day=["night"],
        top_k=10,
        candidate_k=50,
    )
    assert request.place_id == ["N-P031"]
    assert request.top_k == 10


def test_search_request_rejects_empty_query():
    with pytest.raises(ValidationError):
        SearchRequest(query="")


def test_search_result_item_matches_the_contract_fields():
    item = SearchResultItem(
        rank=1,
        source_segment_id="V007_P031_S002",
        segment_id="V007_P031_S002_SCENE_001",
        keyframe_id="V007_P031_S002_SCENE_001",
        keyframe_path="keyframes/V007_Z7u5SNDq0jw/V007_P031_S002_SCENE_001.jpg",
        video_id="V007_Z7u5SNDq0jw",
        place_id="P031",
        place_name="충주 중앙탑공원",
        region="충청북도",
        city="충주시",
        latitude=37.017,
        longitude=127.867,
        drama_title="사랑의 불시착",
        start_time=0.0,
        end_time=3.75,
        season="summer",
        time_of_day="night",
        description="A nighttime view of a brightly lit bridge.",
        mood=["peaceful"],
        activity=["walking"],
        scene_elements=["bridge"],
        k_culture_elements=["K드라마성지"],
        text_score=0.82,
        image_score=0.77,
        text_rank=1,
        image_rank=2,
        final_score=0.031,
    )
    assert item.rank == 1
    assert item.keyframe_id == item.segment_id


def test_search_result_item_allows_null_score_and_rank():
    item = SearchResultItem(
        rank=1,
        source_segment_id="V007_P031_S002",
        segment_id="V007_P031_S002_SCENE_001",
        keyframe_id="V007_P031_S002_SCENE_001",
        keyframe_path="keyframes/x.jpg",
        video_id="V007_Z7u5SNDq0jw",
        place_id="P031",
        place_name="충주 중앙탑공원",
        region="충청북도",
        city="충주시",
        latitude=37.017,
        longitude=127.867,
        drama_title="사랑의 불시착",
        start_time=0.0,
        end_time=3.75,
        season="summer",
        time_of_day="night",
        description="설명",
        mood=[],
        activity=[],
        scene_elements=[],
        k_culture_elements=[],
        text_score=None,
        image_score=0.77,
        text_rank=None,
        image_rank=2,
        final_score=0.02,
    )
    assert item.text_score is None
    assert item.text_rank is None


def test_search_response_wraps_results_with_fallback_flags():
    response = SearchResponse(results=[], fallback_used=True, fallback_reason="필터 결과가 없어 원문 질문으로 다시 검색했습니다.")
    assert response.results == []
    assert response.fallback_used is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd search-service && python -m pytest tests/app/test_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.schemas'`.

- [ ] **Step 3: Write the schemas**

Create `search-service/app/schemas.py`:

```python
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    lang: str = "ko"
    place_id: list[str] | None = None
    drama_title: list[str] | None = None
    region: list[str] | None = None
    city: list[str] | None = None
    season: list[str] | None = None
    time_of_day: list[str] | None = None
    top_k: int = Field(default=5, ge=1)
    candidate_k: int | None = Field(default=None, ge=1)


class SearchResultItem(BaseModel):
    rank: int
    source_segment_id: str
    segment_id: str
    keyframe_id: str
    keyframe_path: str
    video_id: str
    place_id: str
    place_name: str
    region: str
    city: str
    latitude: float
    longitude: float
    drama_title: str
    start_time: float
    end_time: float
    season: str
    time_of_day: str
    description: str
    mood: list[str]
    activity: list[str]
    scene_elements: list[str]
    k_culture_elements: list[str]
    text_score: float | None
    image_score: float | None
    text_rank: int | None
    image_rank: int | None
    final_score: float


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    fallback_used: bool = False
    fallback_reason: str | None = None
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd search-service && python -m pytest tests/app/test_schemas.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add search-service/app/schemas.py search-service/tests/app/test_schemas.py
git commit -m "Add Pydantic schemas matching the search API contract"
```

---

### Task 5: Adapter — RRF pipeline output to contract-shaped results

**Files:**
- Create: `search-service/app/search_response.py`
- Test: `search-service/tests/app/test_search_response.py`

**Interfaces:**
- Consumes: the raw `dict` returned by `MultimodalSearchPipeline.search(...)` (has keys `results_by_method`, `source_results`, `fallback_used`, `fallback_reason` — see `search-service/src/multimodal_pipeline.py`).
- Produces: `build_search_results(pipeline_output: dict, *, top_k: int) -> list[dict]` — a plain list of dicts with exactly the `SearchResultItem` field names, deduplicated by `source_segment_id` (highest `final_score` wins; ties broken by `image_score` desc, then `text_score` desc, then `segment_id` asc) and trimmed to `top_k`. Used by Task 6's route.

**Why a separate function, and why dedup here:** `MultimodalSearchPipeline.search()` returns SCENE-level results (one entry per `segment_id`, not deduplicated by place) and applies `top_k` *before* any deduplication. The contract requires deduplication by `source_segment_id` and `top_k` applied *last* (`docs/search_api_contract.md`: "대표 SCENE final_score 내림차순 정렬 후 top_k 적용"). This function is the "검색 파트" layer the contract describes — call the pipeline with a larger `top_k` (the candidate pool) and let this function do the real trimming.

- [ ] **Step 1: Write the failing test**

Create `search-service/tests/app/test_search_response.py`:

```python
from app.search_response import build_search_results


def _segment(segment_id, source_segment_id, **overrides):
    base = {
        "segment_id": segment_id,
        "source_segment_id": source_segment_id,
        "video_id": "V007_Z7u5SNDq0jw",
        "place_id": "P031",
        "place_name": "충주 중앙탑공원",
        "region": "충청북도",
        "city": "충주시",
        "drama_title": "사랑의 불시착",
        "start_time": 0.0,
        "end_time": 3.75,
        "season": "summer",
        "time_of_day": "night",
        "description": "설명",
        "mood": [],
        "activity": [],
        "scene_elements": [],
        "k_culture_elements": [],
        "keyframe_path": "keyframes/x.jpg",
    }
    base.update(overrides)
    return base


def _pipeline_output(rrf_results, text_results, image_results):
    return {
        "results_by_method": {"rrf": rrf_results},
        "source_results": {"text": text_results, "image": image_results},
        "fallback_used": False,
        "fallback_reason": None,
    }


def test_maps_fields_to_the_contract_shape():
    rrf = [
        {**_segment("S001", "SEG001"), "rrf_score": 0.031, "source_ranks": {"text": 1, "image": 2}},
    ]
    text = [{"segment_id": "S001", "score": 0.82}]
    image = [{"segment_id": "S001", "score": 0.77}]
    output = _pipeline_output(rrf, text, image)

    results = build_search_results(output, top_k=5)

    assert len(results) == 1
    item = results[0]
    assert item["rank"] == 1
    assert item["segment_id"] == "S001"
    assert item["source_segment_id"] == "SEG001"
    assert item["keyframe_id"] == "S001"
    assert item["text_score"] == 0.82
    assert item["image_score"] == 0.77
    assert item["text_rank"] == 1
    assert item["image_rank"] == 2
    assert item["final_score"] == 0.031


def test_null_score_and_rank_when_a_segment_is_missing_from_one_source():
    rrf = [
        {**_segment("S001", "SEG001"), "rrf_score": 0.02, "source_ranks": {"image": 1}},
    ]
    text: list[dict] = []
    image = [{"segment_id": "S001", "score": 0.9}]
    output = _pipeline_output(rrf, text, image)

    results = build_search_results(output, top_k=5)

    assert results[0]["text_score"] is None
    assert results[0]["text_rank"] is None
    assert results[0]["image_score"] == 0.9
    assert results[0]["image_rank"] == 1


def test_dedupes_by_source_segment_id_keeping_the_best_final_score():
    rrf = [
        {**_segment("S001", "SEG001"), "rrf_score": 0.02, "source_ranks": {"text": 3}},
        {**_segment("S002", "SEG001"), "rrf_score": 0.05, "source_ranks": {"text": 1}},
        {**_segment("S003", "SEG002"), "rrf_score": 0.01, "source_ranks": {"text": 5}},
    ]
    text = [
        {"segment_id": "S001", "score": 0.5},
        {"segment_id": "S002", "score": 0.9},
        {"segment_id": "S003", "score": 0.3},
    ]
    output = _pipeline_output(rrf, text, [])

    results = build_search_results(output, top_k=5)

    assert [item["segment_id"] for item in results] == ["S002", "S003"]
    assert [item["source_segment_id"] for item in results] == ["SEG001", "SEG002"]


def test_applies_top_k_after_dedup_and_reranks_sequentially():
    rrf = [
        {**_segment("S001", "SEG001"), "rrf_score": 0.05, "source_ranks": {"text": 1}},
        {**_segment("S002", "SEG002"), "rrf_score": 0.04, "source_ranks": {"text": 2}},
        {**_segment("S003", "SEG003"), "rrf_score": 0.03, "source_ranks": {"text": 3}},
    ]
    output = _pipeline_output(rrf, [], [])

    results = build_search_results(output, top_k=2)

    assert len(results) == 2
    assert [item["rank"] for item in results] == [1, 2]
    assert [item["segment_id"] for item in results] == ["S001", "S002"]


def test_returns_empty_list_for_no_results():
    output = _pipeline_output([], [], [])
    assert build_search_results(output, top_k=5) == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd search-service && python -m pytest tests/app/test_search_response.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.search_response'`.

- [ ] **Step 3: Write the adapter**

Create `search-service/app/search_response.py`:

```python
from typing import Any


def build_search_results(pipeline_output: dict[str, Any], *, top_k: int) -> list[dict[str, Any]]:
    rrf_results = pipeline_output["results_by_method"].get("rrf", [])
    text_scores = {item["segment_id"]: item["score"] for item in pipeline_output["source_results"]["text"]}
    image_scores = {item["segment_id"]: item["score"] for item in pipeline_output["source_results"]["image"]}

    mapped = []
    for segment in rrf_results:
        segment_id = segment["segment_id"]
        source_ranks = segment.get("source_ranks", {})
        mapped.append(
            {
                "source_segment_id": segment["source_segment_id"],
                "segment_id": segment_id,
                "keyframe_id": segment_id,
                "keyframe_path": segment["keyframe_path"],
                "video_id": segment["video_id"],
                "place_id": segment["place_id"],
                "place_name": segment["place_name"],
                "region": segment["region"],
                "city": segment["city"],
                "drama_title": segment["drama_title"],
                "start_time": segment["start_time"],
                "end_time": segment["end_time"],
                "season": segment["season"],
                "time_of_day": segment["time_of_day"],
                "description": segment["description"],
                "mood": segment["mood"],
                "activity": segment["activity"],
                "scene_elements": segment["scene_elements"],
                "k_culture_elements": segment["k_culture_elements"],
                "text_score": text_scores.get(segment_id),
                "image_score": image_scores.get(segment_id),
                "text_rank": source_ranks.get("text"),
                "image_rank": source_ranks.get("image"),
                "final_score": segment["rrf_score"],
            }
        )

    best_by_place: dict[str, dict[str, Any]] = {}
    for item in mapped:
        key = item["source_segment_id"]
        current_best = best_by_place.get(key)
        if current_best is None or _is_better(item, current_best):
            best_by_place[key] = item

    ordered = sorted(
        best_by_place.values(),
        key=lambda item: (
            -item["final_score"],
            -(item["image_score"] or -1),
            -(item["text_score"] or -1),
            item["segment_id"],
        ),
    )

    trimmed = ordered[:top_k]
    for rank, item in enumerate(trimmed, start=1):
        item["rank"] = rank
    return trimmed


def _is_better(candidate: dict[str, Any], current_best: dict[str, Any]) -> bool:
    if candidate["final_score"] != current_best["final_score"]:
        return candidate["final_score"] > current_best["final_score"]
    candidate_image = candidate["image_score"] if candidate["image_score"] is not None else -1
    best_image = current_best["image_score"] if current_best["image_score"] is not None else -1
    if candidate_image != best_image:
        return candidate_image > best_image
    candidate_text = candidate["text_score"] if candidate["text_score"] is not None else -1
    best_text = current_best["text_score"] if current_best["text_score"] is not None else -1
    if candidate_text != best_text:
        return candidate_text > best_text
    return candidate["segment_id"] < current_best["segment_id"]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd search-service && python -m pytest tests/app/test_search_response.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add search-service/app/search_response.py search-service/tests/app/test_search_response.py
git commit -m "Add adapter that dedupes RRF results by place and applies top_k last"
```

---

### Task 6: `POST /api/search` route

**Files:**
- Create: `search-service/app/dependencies.py`
- Modify: `search-service/app/main.py`
- Test: `search-service/tests/app/test_search_route.py`

**Interfaces:**
- Consumes: `SearchRequest`/`SearchResponse` (Task 4), `build_search_results` (Task 5), `MultimodalSearchPipeline` (existing, `search-service/src/multimodal_pipeline.py`).
- Produces: `get_pipeline()` and `get_query_parser()` dependency providers in `app/dependencies.py`, overridable in tests via `app.dependency_overrides`. `POST /api/search` registered on `app`.

- [ ] **Step 1: Write the failing test**

Create `search-service/tests/app/test_search_route.py`:

```python
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_pipeline, get_query_parser


class FakePipeline:
    def search(self, query, *, parser, top_k, methods, **kwargs):
        segment = {
            "segment_id": "V007_P031_S002_SCENE_001",
            "source_segment_id": "V007_P031_S002",
            "video_id": "V007_Z7u5SNDq0jw",
            "place_id": "P031",
            "place_name": "충주 중앙탑공원",
            "region": "충청북도",
            "city": "충주시",
            "drama_title": "사랑의 불시착",
            "start_time": 0.0,
            "end_time": 3.75,
            "season": "summer",
            "time_of_day": "night",
            "description": "야경",
            "mood": ["peaceful"],
            "activity": [],
            "scene_elements": [],
            "k_culture_elements": [],
            "keyframe_path": "keyframes/x.jpg",
            "rrf_score": 0.03,
            "source_ranks": {"text": 1, "image": 1},
        }
        return {
            "results_by_method": {"rrf": [segment]},
            "source_results": {
                "text": [{"segment_id": "V007_P031_S002_SCENE_001", "score": 0.8}],
                "image": [{"segment_id": "V007_P031_S002_SCENE_001", "score": 0.75}],
            },
            "fallback_used": False,
            "fallback_reason": None,
        }


class FakeParser:
    pass


def _client():
    app.dependency_overrides[get_pipeline] = lambda: FakePipeline()
    app.dependency_overrides[get_query_parser] = lambda: FakeParser()
    return TestClient(app)


def test_search_returns_mapped_results():
    client = _client()
    response = client.post("/api/search", json={"query": "봄 궁궐 산책"})
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["place_name"] == "충주 중앙탑공원"
    assert body["results"][0]["rank"] == 1
    assert body["fallback_used"] is False


def test_search_rejects_an_empty_query():
    client = _client()
    response = client.post("/api/search", json={"query": ""})
    app.dependency_overrides.clear()

    assert response.status_code == 422
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd search-service && python -m pytest tests/app/test_search_route.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.dependencies'`.

- [ ] **Step 3: Write the dependency providers**

Create `search-service/app/dependencies.py`:

```python
import os
from functools import lru_cache

from src.clip_backend import ClipRuntime, DatabaseConfig, PgVectorRepository
from src.interfaces import QueryParser
from src.llm_query_parser import LLMQueryParser
from src.openai_client import DEFAULT_QUERY_MODEL, OpenAIStructuredClient
from src.query_parser import RuleBasedQueryParser


@lru_cache
def _runtime() -> ClipRuntime:
    return ClipRuntime(local_files_only=True)


@lru_cache
def _repository() -> PgVectorRepository:
    return PgVectorRepository(DatabaseConfig.from_environment())


def get_pipeline():
    from src.multimodal_pipeline import MultimodalSearchPipeline

    return MultimodalSearchPipeline(runtime=_runtime(), repository=_repository())


def get_query_parser() -> QueryParser:
    if os.getenv("OPENAI_API_KEY"):
        return LLMQueryParser(OpenAIStructuredClient(model=DEFAULT_QUERY_MODEL))
    return RuleBasedQueryParser()
```

Before relying on `RuleBasedQueryParser`, confirm the exact class name search-service actually exports for its rule-based fallback:

```bash
grep -n "class.*QueryParser" search-service/src/query_parser.py
```

If the real name differs from `RuleBasedQueryParser`, use the name `grep` reports instead, in both `dependencies.py` and nowhere else (this is the only place it's referenced).

- [ ] **Step 4: Wire the route into `app/main.py`**

Modify `search-service/app/main.py` — add these imports at the top:

```python
from fastapi import Depends

from app.dependencies import get_pipeline, get_query_parser
from app.schemas import SearchRequest, SearchResponse
from app.search_response import build_search_results
```

Add this route below the existing `health` function:

```python
@app.post("/api/search", response_model=SearchResponse)
def search(request: SearchRequest, pipeline=Depends(get_pipeline), parser=Depends(get_query_parser)):
    candidate_k = request.candidate_k or max(request.top_k * 5, 50)
    output = pipeline.search(
        request.query,
        parser=parser,
        top_k=candidate_k,
        search_depth=candidate_k,
        methods=("rrf",),
    )
    results = build_search_results(output, top_k=request.top_k)
    return SearchResponse(
        results=results,
        fallback_used=output["fallback_used"],
        fallback_reason=output["fallback_reason"],
    )
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd search-service && python -m pytest tests/app/test_search_route.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Run the full app test suite so far**

Run: `cd search-service && python -m pytest tests/app -v`
Expected: all tests across Tasks 3–6 pass.

- [ ] **Step 7: Commit**

```bash
git add search-service/app/dependencies.py search-service/app/main.py search-service/tests/app/test_search_route.py
git commit -m "Add POST /api/search route"
```

---

### Task 7: Tourist-spot lookup API

**Files:**
- Create: `search-service/app/spots_repository.py`
- Modify: `search-service/app/dependencies.py`
- Modify: `search-service/app/main.py`
- Test: `search-service/tests/app/test_spots_repository.py`
- Test: `search-service/tests/app/test_spots_route.py`

**Interfaces:**
- Produces: `SpotsRepository.list_spots(region: str | None) -> list[dict]`, `SpotsRepository.get_spot(spot_id: int) -> dict | None`; `get_spots_repository()` dependency provider; `GET /api/spots`, `GET /api/spots/{spot_id}` routes.

- [ ] **Step 1: Write the failing repository test**

Create `search-service/tests/app/test_spots_repository.py`:

```python
from app.spots_repository import SpotsRepository


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.executed_query = None
        self.executed_params = None

    def execute(self, query, params=None):
        self.executed_query = query
        self.executed_params = params

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeConnection:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return FakeCursor(self._rows)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_list_spots_maps_rows_to_dicts():
    rows = [(1, "충주 중앙탑공원", "충청북도", "충북 충주시 중앙탑면 탑정안길 6", 37.017, 127.867, "설명", None)]
    repo = SpotsRepository(connection_factory=lambda: FakeConnection(rows))

    spots = repo.list_spots(region=None)

    assert spots == [
        {
            "spot_id": 1,
            "spot_name": "충주 중앙탑공원",
            "region": "충청북도",
            "address": "충북 충주시 중앙탑면 탑정안길 6",
            "latitude": 37.017,
            "longitude": 127.867,
            "description": "설명",
            "source_url": None,
        }
    ]


def test_get_spot_returns_none_when_missing():
    repo = SpotsRepository(connection_factory=lambda: FakeConnection([]))

    assert repo.get_spot(999) is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd search-service && python -m pytest tests/app/test_spots_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.spots_repository'`.

- [ ] **Step 3: Write the repository**

Create `search-service/app/spots_repository.py`:

```python
from collections.abc import Callable
from typing import Any


class SpotsRepository:
    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    def list_spots(self, region: str | None) -> list[dict[str, Any]]:
        query = """
            SELECT spot_id, spot_name, region, address, latitude, longitude, description, source_url
            FROM spots
            WHERE (%s IS NULL OR region = %s)
            ORDER BY spot_id
        """
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (region, region))
                rows = cursor.fetchall()
        return [self._spot_from_row(row) for row in rows]

    def get_spot(self, spot_id: int) -> dict[str, Any] | None:
        query = """
            SELECT spot_id, spot_name, region, address, latitude, longitude, description, source_url
            FROM spots
            WHERE spot_id = %s
        """
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (spot_id,))
                row = cursor.fetchone()
        return self._spot_from_row(row) if row else None

    @staticmethod
    def _spot_from_row(row) -> dict[str, Any]:
        return {
            "spot_id": row[0],
            "spot_name": row[1],
            "region": row[2],
            "address": row[3],
            "latitude": row[4],
            "longitude": row[5],
            "description": row[6],
            "source_url": row[7],
        }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd search-service && python -m pytest tests/app/test_spots_repository.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Write the failing route test**

Create `search-service/tests/app/test_spots_route.py`:

```python
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_spots_repository


class FakeSpotsRepository:
    def list_spots(self, region):
        return [{"spot_id": 1, "spot_name": "충주 중앙탑공원", "region": "충청북도", "address": "주소", "latitude": 37.0, "longitude": 127.8, "description": "설명", "source_url": None}]

    def get_spot(self, spot_id):
        if spot_id == 1:
            return {"spot_id": 1, "spot_name": "충주 중앙탑공원", "region": "충청북도", "address": "주소", "latitude": 37.0, "longitude": 127.8, "description": "설명", "source_url": None}
        return None


def _client():
    app.dependency_overrides[get_spots_repository] = lambda: FakeSpotsRepository()
    return TestClient(app)


def test_list_spots():
    client = _client()
    response = client.get("/api/spots")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["spot_name"] == "충주 중앙탑공원"


def test_get_spot_found():
    client = _client()
    response = client.get("/api/spots/1")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["spot_id"] == 1


def test_get_spot_not_found():
    client = _client()
    response = client.get("/api/spots/999")
    app.dependency_overrides.clear()

    assert response.status_code == 404
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `cd search-service && python -m pytest tests/app/test_spots_route.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_spots_repository'`.

- [ ] **Step 7: Add the dependency provider**

In `search-service/app/dependencies.py`, add:

```python
from app.spots_repository import SpotsRepository


def get_spots_repository() -> SpotsRepository:
    import psycopg

    return SpotsRepository(connection_factory=lambda: psycopg.connect(_repository()._config.connection_string))
```

- [ ] **Step 8: Add the routes**

In `search-service/app/main.py`, add to the imports:

```python
from fastapi import HTTPException

from app.dependencies import get_spots_repository
```

Add the routes:

```python
@app.get("/api/spots")
def list_spots(region: str | None = None, repository=Depends(get_spots_repository)):
    return repository.list_spots(region)


@app.get("/api/spots/{spot_id}")
def get_spot(spot_id: int, repository=Depends(get_spots_repository)):
    spot = repository.get_spot(spot_id)
    if spot is None:
        raise HTTPException(status_code=404, detail="해당 관광지를 찾을 수 없어요.")
    return spot
```

- [ ] **Step 9: Run the test to verify it passes**

Run: `cd search-service && python -m pytest tests/app/test_spots_route.py -v`
Expected: PASS (3 tests)

- [ ] **Step 10: Commit**

```bash
git add search-service/app/spots_repository.py search-service/app/dependencies.py search-service/app/main.py search-service/tests/app/test_spots_repository.py search-service/tests/app/test_spots_route.py
git commit -m "Add tourist-spot lookup API (GET /api/spots, GET /api/spots/{id})"
```

---

### Task 8: Video-segment lookup API

**Files:**
- Create: `search-service/app/segments_repository.py`
- Modify: `search-service/app/dependencies.py`
- Modify: `search-service/app/main.py`
- Test: `search-service/tests/app/test_segments_repository.py`
- Test: `search-service/tests/app/test_segments_route.py`

**Interfaces:**
- Produces: `SegmentsRepository.list_segments(video_id, place_id, drama_title) -> list[dict]`, `SegmentsRepository.get_segment(segment_id: str) -> dict | None`; `get_segments_repository()` dependency; `GET /api/segments`, `GET /api/segments/{segment_id}` routes.

- [ ] **Step 1: Write the failing repository test**

Create `search-service/tests/app/test_segments_repository.py`:

```python
from app.segments_repository import SegmentsRepository


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.executed_params = None

    def execute(self, query, params=None):
        self.executed_params = params

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeConnection:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return FakeCursor(self._rows)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _row():
    return (
        "V007_P031_S002_SCENE_001", "V007_P031_S002", "V007_Z7u5SNDq0jw",
        "P031", "충주 중앙탑공원", "충청북도", "충주시", "사랑의 불시착",
        0.0, 3.75, "야경", "summer", "night",
        "keyframes/x.jpg", ["peaceful"], ["walking"], ["bridge"], ["K드라마성지"],
    )


def test_list_segments_maps_rows_to_dicts():
    repo = SegmentsRepository(connection_factory=lambda: FakeConnection([_row()]))

    segments = repo.list_segments(video_id=None, place_id=None, drama_title=None)

    assert segments[0]["segment_id"] == "V007_P031_S002_SCENE_001"
    assert segments[0]["place_name"] == "충주 중앙탑공원"
    assert segments[0]["mood"] == ["peaceful"]


def test_get_segment_returns_none_when_missing():
    repo = SegmentsRepository(connection_factory=lambda: FakeConnection([]))

    assert repo.get_segment("does-not-exist") is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd search-service && python -m pytest tests/app/test_segments_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.segments_repository'`.

- [ ] **Step 3: Write the repository**

Create `search-service/app/segments_repository.py`:

```python
from collections.abc import Callable
from typing import Any

from src.segment_row import segment_from_row

_COLUMNS = """
    vs.segment_id, vs.source_segment_id, vs.video_id,
    vs.place_id, vs.place_name, vs.region, vs.city,
    vs.drama_title, vs.start_time, vs.end_time,
    vs.caption, vs.season, vs.time_of_day, vs.keyframe_path,
    vs.mood_tags, vs.activity_tags, vs.scene_elements, vs.k_culture_elements
"""


class SegmentsRepository:
    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    def list_segments(
        self,
        video_id: str | None,
        place_id: str | None,
        drama_title: str | None,
    ) -> list[dict[str, Any]]:
        query = f"""
            SELECT {_COLUMNS}
            FROM video_segments AS vs
            WHERE (%s IS NULL OR vs.video_id = %s)
              AND (%s IS NULL OR vs.place_id = %s)
              AND (%s IS NULL OR vs.drama_title = %s)
            ORDER BY vs.segment_id
        """
        params = (video_id, video_id, place_id, place_id, drama_title, drama_title)
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
        return [segment_from_row(row) for row in rows]

    def get_segment(self, segment_id: str) -> dict[str, Any] | None:
        query = f"SELECT {_COLUMNS} FROM video_segments AS vs WHERE vs.segment_id = %s"
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (segment_id,))
                row = cursor.fetchone()
        return segment_from_row(row) if row else None
```

This reuses the same `segment_from_row` function Task 2 introduced in `search-service/src/segment_row.py` — the column order in `_COLUMNS` above matches its expected order exactly, so no separate mapping code is needed here.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd search-service && python -m pytest tests/app/test_segments_repository.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Write the failing route test**

Create `search-service/tests/app/test_segments_route.py`:

```python
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_segments_repository


_SEGMENT = {
    "segment_id": "V007_P031_S002_SCENE_001", "source_segment_id": "V007_P031_S002",
    "video_id": "V007_Z7u5SNDq0jw", "place_id": "P031", "place_name": "충주 중앙탑공원",
    "region": "충청북도", "city": "충주시", "drama_title": "사랑의 불시착",
    "start_time": 0.0, "end_time": 3.75, "description": "야경",
    "season": "summer", "time_of_day": "night", "keyframe_path": "keyframes/x.jpg",
    "mood": ["peaceful"], "activity": [], "scene_elements": [], "k_culture_elements": [],
}


class FakeSegmentsRepository:
    def list_segments(self, video_id, place_id, drama_title):
        return [_SEGMENT]

    def get_segment(self, segment_id):
        return _SEGMENT if segment_id == _SEGMENT["segment_id"] else None


def _client():
    app.dependency_overrides[get_segments_repository] = lambda: FakeSegmentsRepository()
    return TestClient(app)


def test_list_segments():
    client = _client()
    response = client.get("/api/segments")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["segment_id"] == "V007_P031_S002_SCENE_001"


def test_get_segment_found():
    client = _client()
    response = client.get(f"/api/segments/{_SEGMENT['segment_id']}")
    app.dependency_overrides.clear()

    assert response.status_code == 200


def test_get_segment_not_found():
    client = _client()
    response = client.get("/api/segments/does-not-exist")
    app.dependency_overrides.clear()

    assert response.status_code == 404
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `cd search-service && python -m pytest tests/app/test_segments_route.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_segments_repository'`.

- [ ] **Step 7: Add the dependency provider**

In `search-service/app/dependencies.py`, add:

```python
from app.segments_repository import SegmentsRepository


def get_segments_repository() -> SegmentsRepository:
    import psycopg

    return SegmentsRepository(connection_factory=lambda: psycopg.connect(_repository()._config.connection_string))
```

- [ ] **Step 8: Add the routes**

In `search-service/app/main.py`, add to the imports:

```python
from app.dependencies import get_segments_repository
```

Add the routes:

```python
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
```

- [ ] **Step 9: Run the test to verify it passes**

Run: `cd search-service && python -m pytest tests/app/test_segments_route.py -v`
Expected: PASS (3 tests)

- [ ] **Step 10: Run every app-layer test together**

Run: `cd search-service && python -m pytest tests/app -v`
Expected: all tests from Tasks 3–8 pass (25 tests total: 3 health + 6 schemas + 5 search_response + 2 search route + 2 spots repo + 3 spots route + 2 segments repo + 3 segments route — recount against actual output and note any mismatch).

- [ ] **Step 11: Commit**

```bash
git add search-service/app/segments_repository.py search-service/app/dependencies.py search-service/app/main.py search-service/tests/app/test_segments_repository.py search-service/tests/app/test_segments_route.py
git commit -m "Add video-segment lookup API (GET /api/segments, GET /api/segments/{id})"
```

---

### Task 9: Dockerfile

**Files:**
- Create: `search-service/Dockerfile`
- Create: `search-service/.dockerignore`

**Interfaces:** None — this produces a buildable image, verified by `docker build` succeeding (Docker itself isn't available in this environment per earlier session findings — verification here is limited to reviewing the file; a real `docker build` happens as part of Task 10's manual deployment).

- [ ] **Step 1: Write `.dockerignore`**

Create `search-service/.dockerignore`:

```
.venv
__pycache__
*.pyc
tests
output
data
.env
```

- [ ] **Step 2: Write the Dockerfile**

Create `search-service/Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-api.txt

COPY src ./src
COPY app ./app

ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Verify the file is well-formed**

Run: `cd search-service && docker build -t ktour-search-api . --check 2>&1 || echo "docker not available in this environment -- verify by running this same command on your own machine before deploying"`

This environment does not have Docker installed (confirmed earlier this session while investigating deployment options), so this step will print the fallback message — that's expected here. Actually building and running the image happens in Task 10, on your own machine or directly on Railway.

- [ ] **Step 4: Commit**

```bash
git add search-service/Dockerfile search-service/.dockerignore
git commit -m "Add Dockerfile for the FastAPI search API"
```

---

### Task 10: Deploy to Railway (manual — cannot be automated from this environment)

**Files:** None — this is a deployment checklist, not code. This environment has no Railway account, no Docker, and no access to the local machine's already-populated Postgres instance, so these steps must be run by you.

- [ ] **Step 1: Push the branch**

```bash
git push -u origin backend-search-api
```

- [ ] **Step 2: Create the Railway project**

In the Railway dashboard: New Project → Deploy from GitHub repo → select this repo and the `backend-search-api` branch.

- [ ] **Step 3: Add the Postgres+pgvector service**

Add a service using the Docker image `pgvector/pgvector:pg16` (not Railway's built-in Postgres plugin — it doesn't include the `vector` extension). Mount `search-service/../embedding-db/schema.sql` — or run it manually via `psql` against the new instance once it's up — so the tables exist before restoring data.

- [ ] **Step 4: Migrate the local DB data**

On your machine, with the local `embedding-db` Postgres container running:

```bash
docker exec ktour_pgvector pg_dump -U <your_postgres_user> -d <your_postgres_db> -F c -f /tmp/ktour_dump.pgdata
docker cp ktour_pgvector:/tmp/ktour_dump.pgdata ./ktour_dump.pgdata
```

Then restore into the Railway Postgres instance (get its connection details from the Railway dashboard):

```bash
pg_restore -h <railway-host> -p <railway-port> -U <railway-user> -d <railway-db> --no-owner ./ktour_dump.pgdata
```

- [ ] **Step 5: Add the FastAPI service**

Add a second Railway service pointing at `search-service/Dockerfile` in this repo. Set these environment variables in the Railway dashboard:

- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` — pointing at the Railway Postgres service from Step 3
- `OPENAI_API_KEY` — if you have one by this point; the app runs fine without it (falls back to the rule-based query parser)

- [ ] **Step 6: Verify the health check**

```bash
curl https://<your-railway-app>.up.railway.app/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 7: Verify a real search**

```bash
curl -X POST https://<your-railway-app>.up.railway.app/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "봄에 궁궐 산책"}'
```

Expected: `200` with a `results` array of real segments (not empty, unless the DB restore in Step 4 didn't complete).

- [ ] **Step 8: Report back**

Once Steps 6 and 7 both work, this backend is live. The next step — connecting the React frontend to this URL instead of its static local data — is a separate follow-up plan, out of scope here.
