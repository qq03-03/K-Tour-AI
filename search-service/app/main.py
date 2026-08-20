import psycopg
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.dependencies import get_pipeline, get_query_parser
from app.schemas import SearchRequest, SearchResponse
from app.search_response import build_search_results

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
