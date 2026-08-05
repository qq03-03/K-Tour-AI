from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from pathlib import Path
from typing import Iterable


KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
OUTPUT_FIELDS = [
    "place_id",
    "query_candidate",
    "query",
    "region",
    "city",
    "linked_segment_ids",
    "linked_video_ids",
    "linked_source_urls",
    "result_rank",
    "kakao_place_name",
    "category_name",
    "address",
    "road_address",
    "latitude",
    "longitude",
    "kakao_place_url",
    "selection_status",
    "notes",
]


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description=(
            "좌표가 비어 있는 관광지 후보를 카카오 Local API로 검색하고 "
            "검수용 후보 CSV를 생성합니다. 원본 CSV는 수정하지 않습니다."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=project_root / "data" / "places_coordinates_review.csv",
        help="좌표 검수 원본 CSV 경로",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "data" / "places_coordinates_kakao_candidates.csv",
        help="카카오 검색 후보 CSV 경로",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
        choices=range(1, 16),
        metavar="1-15",
        help="장소 후보 하나당 저장할 최대 검색 결과 수 (기본값: 5)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.15,
        help="API 요청 사이 대기 시간(초) (기본값: 0.15)",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="API를 호출하지 않고 조회 예정 목록만 생성",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="기존 출력 파일 덮어쓰기 허용",
    )
    return parser.parse_args()


def read_review_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "place_id",
            "source_segment_id",
            "video_id",
            "source_url",
            "current_place_candidates",
            "region",
            "city",
            "latitude",
            "longitude",
        }
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"입력 CSV 필드 누락: {', '.join(sorted(missing))}")
        return [dict(row) for row in reader]


def has_coordinates(row: dict[str, str]) -> bool:
    return bool((row.get("latitude") or "").strip()) and bool(
        (row.get("longitude") or "").strip()
    )


def split_place_candidates(value: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for raw in (value or "").split("/"):
        candidate = raw.strip()
        if candidate and candidate not in seen:
            seen.add(candidate)
            candidates.append(candidate)
    return candidates


def build_query_units(rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    units: OrderedDict[tuple[str, str, str, str], dict[str, object]] = OrderedDict()
    for row in rows:
        if has_coordinates(row):
            continue
        place_id = (row.get("place_id") or "").strip()
        region = (row.get("region") or "").strip()
        city = (row.get("city") or "").strip()
        candidates = split_place_candidates(row.get("current_place_candidates") or "")
        if not candidates:
            candidates = [place_id]
        for candidate in candidates:
            key = (place_id, candidate, region, city)
            if key not in units:
                query_parts = [candidate]
                if city and city not in candidate:
                    query_parts.append(city)
                units[key] = {
                    "place_id": place_id,
                    "query_candidate": candidate,
                    "query": " ".join(query_parts),
                    "region": region,
                    "city": city,
                    "segment_ids": [],
                    "video_ids": [],
                    "source_urls": [],
                }
            unit = units[key]
            append_unique(unit["segment_ids"], row.get("source_segment_id") or "")
            append_unique(unit["video_ids"], row.get("video_id") or "")
            append_unique(unit["source_urls"], row.get("source_url") or "")

    result: list[dict[str, str]] = []
    for unit in units.values():
        result.append(
            {
                "place_id": str(unit["place_id"]),
                "query_candidate": str(unit["query_candidate"]),
                "query": str(unit["query"]),
                "region": str(unit["region"]),
                "city": str(unit["city"]),
                "linked_segment_ids": "; ".join(unit["segment_ids"]),
                "linked_video_ids": "; ".join(unit["video_ids"]),
                "linked_source_urls": "; ".join(unit["source_urls"]),
            }
        )
    return result


def append_unique(values: object, value: str) -> None:
    if not isinstance(values, list):
        raise TypeError("내부 목록 형식 오류")
    value = value.strip()
    if value and value not in values:
        values.append(value)


def plan_row(unit: dict[str, str]) -> dict[str, str]:
    row = {field: "" for field in OUTPUT_FIELDS}
    row.update(unit)
    row["selection_status"] = "조회 예정"
    return row


def kakao_search(query: str, api_key: str, max_results: int) -> list[dict[str, object]]:
    params = urllib.parse.urlencode({"query": query, "size": max_results})
    request = urllib.request.Request(
        f"{KAKAO_KEYWORD_URL}?{params}",
        headers={
            "Authorization": f"KakaoAK {api_key}",
            "Accept": "application/json",
            "User-Agent": "K-Tour-AI-coordinate-review/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"네트워크 오류: {exc.reason}") from exc
    documents = payload.get("documents", [])
    if not isinstance(documents, list):
        raise RuntimeError("카카오 API 응답에 documents 배열이 없습니다")
    return documents


def result_rows(
    unit: dict[str, str], documents: list[dict[str, object]]
) -> list[dict[str, str]]:
    if not documents:
        row = {field: "" for field in OUTPUT_FIELDS}
        row.update(unit)
        row["selection_status"] = "검색 결과 없음"
        return [row]

    rows: list[dict[str, str]] = []
    for rank, document in enumerate(documents, start=1):
        row = {field: "" for field in OUTPUT_FIELDS}
        row.update(unit)
        row.update(
            {
                "result_rank": str(rank),
                "kakao_place_name": str(document.get("place_name") or ""),
                "category_name": str(document.get("category_name") or ""),
                "address": str(document.get("address_name") or ""),
                "road_address": str(document.get("road_address_name") or ""),
                "latitude": str(document.get("y") or ""),
                "longitude": str(document.get("x") or ""),
                "kakao_place_url": str(document.get("place_url") or ""),
                "selection_status": "미검수",
            }
        )
        rows.append(row)
    return rows


def error_row(unit: dict[str, str], message: str) -> dict[str, str]:
    row = {field: "" for field in OUTPUT_FIELDS}
    row.update(unit)
    row["selection_status"] = "API 오류"
    row["notes"] = message[:500]
    return row


def write_csv(path: Path, rows: list[dict[str, str]], overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"출력 파일이 이미 있습니다: {path}\n"
            "덮어쓰려면 --overwrite 옵션을 사용하세요."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        raise FileExistsError(f"임시 출력 파일이 이미 있습니다: {temporary}")
    try:
        with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    args = parse_args()
    if args.delay < 0:
        raise ValueError("--delay는 0 이상이어야 합니다")

    review_rows = read_review_rows(args.input)
    query_units = build_query_units(review_rows)
    if not query_units:
        print("좌표가 비어 있는 장소 후보가 없습니다.")
        return 0

    if args.plan_only:
        output_rows = [plan_row(unit) for unit in query_units]
        write_csv(args.output, output_rows, args.overwrite)
        print(f"계획 파일 생성 완료: {args.output}")
        print(f"조회 예정 장소 후보: {len(query_units)}건")
        return 0

    api_key = (os.environ.get("KAKAO_REST_API_KEY") or "").strip()
    if not api_key:
        print(
            "KAKAO_REST_API_KEY 환경변수가 없습니다. 같은 PowerShell 터미널에서 "
            "REST API 키를 설정한 뒤 다시 실행하세요.",
            file=sys.stderr,
        )
        return 2

    output_rows: list[dict[str, str]] = []
    error_count = 0
    for index, unit in enumerate(query_units, start=1):
        print(f"[{index}/{len(query_units)}] {unit['query']}")
        try:
            documents = kakao_search(unit["query"], api_key, args.max_results)
            output_rows.extend(result_rows(unit, documents))
        except RuntimeError as exc:
            error_count += 1
            output_rows.append(error_row(unit, str(exc)))
        if index < len(query_units) and args.delay:
            time.sleep(args.delay)

    write_csv(args.output, output_rows, args.overwrite)
    print(f"카카오 후보 파일 생성 완료: {args.output}")
    print(f"조회 단위: {len(query_units)}건 / 결과 행: {len(output_rows)}건")
    if error_count:
        print(f"API 오류: {error_count}건 (후보 CSV의 notes 확인)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
