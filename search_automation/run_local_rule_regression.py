from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from collections import Counter
from pathlib import Path


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="실제 search-service에 생성된 작품명·지역·필터 규칙 사례를 실행합니다."
    )
    parser.add_argument("--search-service-root", type=Path, required=True)
    parser.add_argument(
        "--cases",
        type=Path,
        default=root / "output" / "current_517_check" / "search_rule_regression_cases.generated.json",
    )
    parser.add_argument(
        "--title-catalog",
        type=Path,
        default=root / "output" / "current_517_check" / "drama_title_catalog.generated.json",
    )
    parser.add_argument(
        "--location-catalog",
        type=Path,
        default=root / "output" / "current_517_check" / "location_alias_catalog.generated.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "output" / "local_rule_regression.json",
    )
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(args.search_service_root.resolve()))

    drama = importlib.import_module("src.drama_title_matcher")
    location = importlib.import_module("src.location_matcher")
    query_parser = importlib.import_module("src.query_parser")
    filters = importlib.import_module("src.filters")

    drama.CATALOG_PATH = args.title_catalog.resolve()
    drama.load_title_catalog.cache_clear()
    drama._alias_entries.cache_clear()
    location.CATALOG_PATH = args.location_catalog.resolve()
    location._catalog_entries.cache_clear()

    payload = json.loads(args.cases.read_text(encoding="utf-8-sig"))
    raw_cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("cases 파일에 cases 배열이 없습니다.")

    reports = []
    for case in raw_cases:
        case_type = str(case.get("case_type") or "")
        failures: list[str] = []
        actual = {}
        if case_type == "drama_title_protection":
            query = str(case.get("query") or "")
            expected = str(case.get("expected", {}).get("matched_drama_title") or "")
            match = drama.analyze_drama_titles(query)
            parsed = query_parser.RuleBasedQueryParser().parse(query)
            actual = {
                "status": match.status,
                "matched_titles": list(match.matched_titles),
                "filters": parsed.filters,
            }
            if match.status != "matched" or expected not in match.matched_titles:
                failures.append(f"작품명 {expected!r}를 인식하지 못함")
            for forbidden in ("season", "region"):
                if parsed.filters.get(forbidden):
                    failures.append(
                        f"작품 제목 단어를 {forbidden} 필터로 오인: {parsed.filters[forbidden]}"
                    )
        elif case_type == "region_group_expansion":
            query = str(case.get("query") or "")
            expected = set(case.get("expected", {}).get("region", []))
            match = location.analyze_locations(query)
            actual = {"region": list(match.region_filters)}
            if set(match.region_filters) != expected:
                failures.append(
                    f"지역권 확장 불일치: {sorted(match.region_filters)} != {sorted(expected)}"
                )
        elif case_type == "region_alias_matching":
            query = str(case.get("query") or "")
            expected = set(case.get("expected", {}).get("region", []))
            match = location.analyze_locations(query)
            actual = {"region": list(match.region_filters)}
            if set(match.region_filters) != expected:
                failures.append(
                    f"지역 별칭 불일치: {sorted(match.region_filters)} != {sorted(expected)}"
                )
        elif case_type == "place_alias_matching":
            query = str(case.get("query") or "")
            expected_place_id = str(
                case.get("expected", {}).get("place_id") or ""
            )
            expected_regions = set(case.get("expected", {}).get("region", []))
            match = location.analyze_locations(query)
            matched_place_ids = {place.place_id for place in match.places}
            actual = {
                "place_ids": sorted(matched_place_ids),
                "region": list(match.region_filters),
            }
            if expected_place_id not in matched_place_ids:
                failures.append(
                    f"장소 별칭이 {expected_place_id!r}를 인식하지 못함: "
                    f"{sorted(matched_place_ids)}"
                )
            if expected_regions and set(match.region_filters) != expected_regions:
                failures.append(
                    f"장소의 명시 지역 불일치: {sorted(match.region_filters)} "
                    f"!= {sorted(expected_regions)}"
                )
        elif case_type == "filter_value_normalization":
            fragment = str(case.get("query_fragment") or "")
            expected_mapping = case.get("expected", {})
            field = next(iter(expected_mapping), "")
            expected_values = list(expected_mapping.get(field, []))
            parsed_filters = query_parser.extract_explicit_scalar_filters(fragment)
            arguments = query_parser.to_filter_arguments(parsed_filters)
            synthetic = {"segment_id": "SYNTHETIC", field: expected_values[0]}
            matched = filters.filter_segments([synthetic], **arguments)
            actual = {
                "parsed_filters": parsed_filters,
                "filter_arguments": arguments,
                "synthetic_matched": bool(matched),
            }
            if field not in parsed_filters:
                failures.append(f"{field} 표현 {fragment!r}을 추출하지 못함")
            elif not matched:
                failures.append(
                    f"{fragment!r} 필터가 최종 canonical {expected_values!r} 데이터와 불일치"
                )
        else:
            failures.append(f"지원하지 않는 case_type={case_type!r}")
        reports.append(
            {
                "case_id": case.get("case_id"),
                "case_type": case_type,
                "input": case.get("query", case.get("query_fragment")),
                "expected": case.get("expected"),
                "actual": actual,
                "failures": failures,
                "passed": not failures,
            }
        )

    counts = Counter(item["case_type"] for item in reports)
    failures = [item for item in reports if not item["passed"]]
    report = {
        "schema_version": "1.0",
        "search_service_root": str(args.search_service_root.resolve()),
        "inputs": {
            "cases": file_manifest(args.cases),
            "title_catalog": file_manifest(args.title_catalog),
            "location_catalog": file_manifest(args.location_catalog),
            "drama_title_matcher": file_manifest(Path(drama.__file__)),
            "location_matcher": file_manifest(Path(location.__file__)),
            "query_parser": file_manifest(Path(query_parser.__file__)),
            "filters": file_manifest(Path(filters.__file__)),
        },
        "case_count": len(reports),
        "case_type_counts": dict(sorted(counts.items())),
        "passed_count": len(reports) - len(failures),
        "failed_count": len(failures),
        "passed": not failures,
        "cases": reports,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)
    print(json.dumps({key: report[key] for key in ("case_count", "case_type_counts", "passed_count", "failed_count", "passed")}, ensure_ascii=False, indent=2))
    print(f"보고서: {args.output.resolve()}")
    if args.strict and failures:
        raise SystemExit(1)


def file_manifest(path: Path) -> dict[str, object]:
    resolved = path.resolve()
    digest = hashlib.sha256()
    with resolved.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(resolved),
        "size_bytes": resolved.stat().st_size,
        "sha256": digest.hexdigest(),
    }


if __name__ == "__main__":
    main()
