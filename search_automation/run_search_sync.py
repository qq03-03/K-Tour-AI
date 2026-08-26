from __future__ import annotations

import argparse
import json
from pathlib import Path

from ktour_search_automation.sync import prepare_search_assets, write_search_assets


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="새 metadata를 검색 규칙·테마·평가 자산과 안전하게 동기화합니다."
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--baseline-metadata", type=Path)
    parser.add_argument("--translations", type=Path)
    parser.add_argument("--existing-title-catalog", type=Path)
    parser.add_argument("--existing-location-catalog", type=Path)
    parser.add_argument("--theme-mapping", type=Path)
    parser.add_argument("--theme-decisions", type=Path)
    parser.add_argument("--theme-rules", type=Path)
    parser.add_argument("--evaluation", type=Path)
    parser.add_argument("--text-embeddings", type=Path)
    parser.add_argument("--image-embeddings", type=Path)
    parser.add_argument("--coordinates", type=Path)
    parser.add_argument(
        "--policy",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="blocking error가 있으면 종료 코드 2를 반환합니다.",
    )
    args = parser.parse_args()
    if args.manifest:
        payload = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            parser.error("manifest는 JSON 객체여야 합니다.")
        base = args.manifest.resolve().parent
        path_fields = (
            "metadata",
            "baseline_metadata",
            "translations",
            "existing_title_catalog",
            "existing_location_catalog",
            "theme_mapping",
            "theme_decisions",
            "theme_rules",
            "evaluation",
            "text_embeddings",
            "image_embeddings",
            "coordinates",
            "policy",
            "output_dir",
        )
        for field in path_fields:
            if getattr(args, field) is not None or not payload.get(field):
                continue
            value = Path(str(payload[field]))
            setattr(args, field, value if value.is_absolute() else base / value)
    if args.metadata is None:
        parser.error("--metadata 또는 --manifest의 metadata가 필요합니다.")
    if args.policy is None:
        args.policy = root / "config" / "search_policy.json"
    if args.output_dir is None:
        args.output_dir = root / "output" / "latest"
    return args


def main() -> None:
    args = parse_args()
    assets = prepare_search_assets(
        metadata_path=args.metadata,
        baseline_metadata_path=args.baseline_metadata,
        translations_path=args.translations,
        existing_title_catalog_path=args.existing_title_catalog,
        existing_location_catalog_path=args.existing_location_catalog,
        theme_mapping_path=args.theme_mapping,
        theme_decisions_path=args.theme_decisions,
        theme_rules_path=args.theme_rules,
        evaluation_path=args.evaluation,
        text_embeddings_path=args.text_embeddings,
        image_embeddings_path=args.image_embeddings,
        coordinates_path=args.coordinates,
        policy_path=args.policy,
    )
    write_search_assets(args.output_dir, assets, overwrite=args.overwrite)
    summary = assets["search_sync_report"]["summary"]
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"결과 폴더: {args.output_dir.resolve()}")
    print("원본 metadata/임베딩/DB 수정: 없음")
    if args.strict and summary["blocking_error_count"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
