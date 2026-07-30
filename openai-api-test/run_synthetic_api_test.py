"""프로젝트 데이터를 전송하지 않는 OpenAI API 격리 테스트."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field


ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = "gpt-5.6-luna"
PING_PROMPT = "Reply with exactly: OK"
STRUCTURED_SYSTEM_PROMPT = (
    "You structure a fictional tourism search sentence. "
    "Return only values supported by the sentence. Do not add real locations."
)
STRUCTURED_USER_PROMPT = (
    "Fictional test only: A traveler wants a calm spring morning walk "
    "through a flower garden in Example City."
)


class SyntheticQuery(BaseModel):
    """합성 관광 문장의 구조화 출력."""

    model_config = ConfigDict(extra="forbid")

    search_text: str = Field(min_length=1)
    region: list[str] = Field(default_factory=list)
    season: list[str] = Field(default_factory=list)
    time_of_day: list[str] = Field(default_factory=list)
    mood: list[str] = Field(default_factory=list)
    activity: list[str] = Field(default_factory=list)
    scene_elements: list[str] = Field(default_factory=list)


def run_ping(client: Any, model: str) -> dict[str, Any]:
    started = time.perf_counter()
    response = client.responses.create(model=model, input=PING_PROMPT)
    answer = response.output_text.strip()
    if answer != "OK":
        raise RuntimeError(f"예상한 응답 'OK'와 다릅니다: {answer!r}")
    return {
        "status": "passed",
        "sent_text": PING_PROMPT,
        "answer": answer,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def run_structured(client: Any, model: str) -> dict[str, Any]:
    started = time.perf_counter()
    response = client.responses.parse(
        model=model,
        input=[
            {"role": "system", "content": STRUCTURED_SYSTEM_PROMPT},
            {"role": "user", "content": STRUCTURED_USER_PROMPT},
        ],
        text_format=SyntheticQuery,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("구조화된 API 응답이 없습니다.")
    return {
        "status": "passed",
        "sent_text": STRUCTURED_USER_PROMPT,
        "parsed": parsed.model_dump(),
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="프로젝트 데이터 없는 OpenAI API 격리 테스트"
    )
    parser.add_argument(
        "--stage",
        choices=("ping", "structured", "all"),
        default="all",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OPENAI_QUERY_MODEL", DEFAULT_MODEL),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output" / "synthetic_api_test.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY가 없습니다. run_api_test.ps1을 실행해 키를 입력하세요."
        )

    client = OpenAI()
    report: dict[str, Any] = {
        "scope": {
            "project_data_sent": False,
            "input_source": "constants_in_this_script_only",
        },
        "model": args.model,
        "stage": args.stage,
        "tests": {},
    }
    if args.stage in {"ping", "all"}:
        report["tests"]["ping"] = run_ping(client, args.model)
    if args.stage in {"structured", "all"}:
        report["tests"]["structured"] = run_structured(client, args.model)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report={args.output}")


if __name__ == "__main__":
    main()
