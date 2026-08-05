"""실제 평가 전 PostgreSQL/pgvector 적재 상태를 검사한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.clip_backend import DatabaseConfig
from src.db_preflight import (
    analyze_db_snapshot,
    build_dry_run_snapshot,
    collect_db_snapshot,
)
from src.project_data_validation import extract_metadata_records, load_metadata_payload


PROJECT_ROOT = Path(__file__).resolve().parent
EMBEDDING_ROOT = PROJECT_ROOT.parent / "embedding-db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="실데이터 임베딩 DB 사전 점검")
    parser.add_argument(
        "--metadata",
        type=Path,
        default=EMBEDDING_ROOT / "metadata" / "metadata.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "output" / "db_preflight.json",
    )
    parser.add_argument(
        "--env",
        type=Path,
        default=EMBEDDING_ROOT / ".env",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB에 연결하지 않고 metadata로 점검기 동작만 확인",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    records = extract_metadata_records(load_metadata_payload(args.metadata))
    if args.dry_run:
        snapshot = build_dry_run_snapshot(records)
        mode = "dry_run_not_database_validation"
    else:
        config = DatabaseConfig.from_environment(args.env)
        snapshot = collect_db_snapshot(config.connection_string)
        mode = "live_database"
    report = analyze_db_snapshot(snapshot, records)
    report["execution_mode"] = mode
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("=== 임베딩 DB 사전 점검 ===")
    print(f"실행 모드: {mode}")
    print(f"결과: {report['summary']['status']}")
    print(f"실패 항목: {report['summary']['failed_checks']}")
    print(f"보고서: {args.output}")
    raise SystemExit(0 if report["summary"]["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
