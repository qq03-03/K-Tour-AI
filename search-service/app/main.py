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
