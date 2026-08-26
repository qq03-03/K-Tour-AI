from __future__ import annotations

import json

from ktour_search_automation.sync import (
    build_title_catalog,
    prepare_search_assets,
    validate_evaluation_compatibility,
    validate_translation_alignment,
    validate_search_metadata,
)


POLICY = {
    "result_unit": "source_segment_id",
    "hard_filter_fields": [
        "place_id",
        "drama_title",
        "region",
        "city",
        "season",
        "time_of_day",
        "theme",
    ],
    "soft_hint_fields": ["mood", "activity", "scene_elements"],
    "allowed_values": {
        "season": ["봄", "여름", "가을", "겨울"],
        "time_of_day": ["day", "evening", "night"],
        "theme": ["flower", "night_view"],
    },
    "value_aliases": {
        "season": {"봄": ["봄", "spring"]},
        "time_of_day": {"day": ["낮", "day"]},
    },
    "region_groups": {"수도권": ["서울", "경기", "인천"]},
    "candidate_k": {"minimum": 50, "top_k_multiplier": 5},
    "rrf_k": 60,
}


def scene(
    segment_id: str,
    source_id: str,
    place_id: str,
    place_name: str,
    title: str,
    *,
    description: str = "봄꽃이 핀 길",
) -> dict:
    return {
        "segment_id": segment_id,
        "source_segment_id": source_id,
        "video_id": source_id.split("_")[0] + "_video",
        "place_id": place_id,
        "place_name": place_name,
        "region": "경기도",
        "city": "수원시",
        "drama_title": title,
        "season": "봄",
        "time_of_day": "day",
        "start_time": 0.0,
        "end_time": 5.0,
        "keyframe_path": f"keyframes/{segment_id}.jpg",
        "description": description,
        "mood": ["peaceful"],
        "activity": ["walking"],
        "scene_elements": ["cherry blossom"],
    }


def write_json(path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def display_fields(row: dict, *, title: str, place_name: str) -> dict:
    return {
        "drama_title": title,
        "place_name": place_name,
        "region": row["region"],
        "city": row["city"],
        "season": row["season"],
        "time_of_day": row["time_of_day"],
        "description": row["description"],
        "mood": list(row["mood"]),
        "activity": list(row["activity"]),
        "scene_elements": list(row["scene_elements"]),
    }


def test_final_time_values_are_valid_and_missing_title_is_only_warning() -> None:
    row = scene("V001_P001_S001_SCENE_001", "V001_P001_S001", "P001", "화성", "")
    report = validate_search_metadata([row], POLICY)

    assert report["is_valid"] is True
    assert [item["code"] for item in report["issues"]] == [
        "DRAMA_TITLE_UNCONFIRMED"
    ]


def test_embedded_place_id_mismatch_is_blocking() -> None:
    row = scene(
        "V001_P064_S001_SCENE_001",
        "V001_P064_S001",
        "P032",
        "화홍문",
        "선재 업고 튀어",
    )
    report = validate_search_metadata([row], POLICY)

    codes = {item["code"] for item in report["issues"]}
    assert "PLACE_ID_EMBEDDED_ID_MISMATCH" in codes
    assert report["is_valid"] is False


def test_prepare_search_assets_detects_only_new_search_work(tmp_path) -> None:
    baseline = [
        scene(
            "V001_P001_S001_SCENE_001",
            "V001_P001_S001",
            "P001",
            "수원 화성",
            "서울의 봄",
        )
    ]
    current = [
        *baseline,
        scene(
            "V002_P002_S001_SCENE_001",
            "V002_P002_S001",
            "P002",
            "벚꽃길",
            "새 작품",
        ),
    ]
    translations = {
        "records": [
                {
                    "segment_id": row["segment_id"],
                    "keyframe_id": row["segment_id"],
                    "translations": {
                        "ko": display_fields(
                            row,
                            title=row["drama_title"],
                            place_name=row["place_name"],
                        ),
                        "en": display_fields(
                            row,
                            title="12.12: The Day"
                            if row["drama_title"] == "서울의 봄"
                            else "New Work",
                            place_name="Suwon Hwaseong"
                            if row["place_id"] == "P001"
                            else "Cherry Blossom Road",
                        ),
                        "ja": display_fields(
                            row,
                            title=row["drama_title"],
                            place_name=row["place_name"],
                        ),
                        "zh": display_fields(
                            row,
                            title=row["drama_title"],
                            place_name=row["place_name"],
                        ),
                    },
            }
            for row in current
        ]
    }
    titles = {
        "titles": [
            {
                "canonical_title": "서울의 봄",
                "aliases": {"ko": ["서울의 봄"]},
            }
        ]
    }
    locations = {
        "region_aliases": [
            {
                "canonical": "경기",
                "aliases": {"ko": ["경기"], "en": ["Gyeonggi"]},
            }
        ],
        "place_aliases": [
            {
                "place_id": "P001",
                "place_name": "수원 화성",
                "explicit_region_filter": None,
                "aliases": {"ko": ["수원 화성"]},
            }
        ],
    }
    theme_mapping = {
        "entries": [
            {"source_segment_id": "V001_P001_S001", "themes": ["flower"]}
        ]
    }
    theme_rules = {
        "themes": [
            {
                "id": "flower",
                "label": "꽃",
                "terms": ["cherry blossom", "꽃"],
                "strong_terms": ["cherry blossom"],
            }
        ]
    }
    evaluation = {
        "queries": [
            {
                "query_id": "E1",
                "language": "ko",
                "query": "꽃길",
                "theme": "꽃",
                "relevant_source_segment_ids": ["V001_P001_S001"],
                "relevant_segment_ids": ["V001_P001_S001_SCENE_001"],
                "relevant_keyframe_paths": [
                    "keyframes/V001_P001_S001_SCENE_001.jpg"
                ],
            }
        ]
    }
    paths = {}
    for name, payload in {
        "metadata": current,
        "baseline": baseline,
        "translations": translations,
        "titles": titles,
        "locations": locations,
        "themes": theme_mapping,
        "rules": theme_rules,
        "evaluation": evaluation,
        "policy": POLICY,
    }.items():
        path = tmp_path / f"{name}.json"
        write_json(path, payload)
        paths[name] = path

    assets = prepare_search_assets(
        metadata_path=paths["metadata"],
        baseline_metadata_path=paths["baseline"],
        translations_path=paths["translations"],
        existing_title_catalog_path=paths["titles"],
        existing_location_catalog_path=paths["locations"],
        theme_mapping_path=paths["themes"],
        theme_rules_path=paths["rules"],
        evaluation_path=paths["evaluation"],
        policy_path=paths["policy"],
    )

    report = assets["search_sync_report"]
    assert report["summary"]["added_scene_count"] == 1
    assert report["summary"]["generated_title_count"] == 2
    assert report["summary"]["generated_place_alias_count"] == 2
    assert report["summary"]["blocking_error_count"] == 0
    assert assets["theme_review_queue"]["entries"][0]["source_segment_id"] == "V002_P002_S001"
    assert assets["evaluation_compatibility"]["resolved_query_count"] == 1
    case_types = {
        item["case_type"]
        for item in assets["search_rule_regression_cases"]["cases"]
    }
    assert "region_alias_matching" in case_types
    assert "place_alias_matching" in case_types


def test_conflicting_translated_title_alias_is_quarantined() -> None:
    rows = [
        scene("A_SCENE_001", "A", "P001", "장소1", "가을동화"),
        scene("B_SCENE_001", "B", "P002", "장소2", "가을로"),
    ]
    translations = [
        {
            "segment_id": "A_SCENE_001",
            "translations": {"en": {"drama_title": "Autumn in My Heart"}},
        },
        {
            "segment_id": "B_SCENE_001",
            "translations": {"en": {"drama_title": "Autumn in My Heart"}},
        },
    ]

    catalog, review = build_title_catalog(rows, translations, {})
    aliases = {
        item["canonical_title"]: item["aliases"].get("en", [])
        for item in catalog["titles"]
    }
    assert aliases["가을동화"] == []
    assert aliases["가을로"] == []
    assert review["alias_collisions"][0]["kept_owner"] is None


def test_embedding_alignment_is_checked_with_metadata(tmp_path) -> None:
    current = [
        scene(
            "V001_P001_S001_SCENE_001",
            "V001_P001_S001",
            "P001",
            "수원 화성",
            "서울의 봄",
        )
    ]
    text_embedding = [
        {
            **{key: value for key, value in current[0].items() if key != "keyframe_path"},
            "search_text": "봄꽃 수원 화성 서울의 봄",
            "embedding_model": "clip-test",
            "text_embedding": [0.1, 0.2],
        }
    ]
    image_embedding = [
        {
            **current[0],
            "keyframe_id": current[0]["segment_id"],
            "embedding_model": "clip-test",
            "image_embedding": [0.3, 0.4],
        }
    ]
    policy = {
        **POLICY,
        "embedding_dimension": 2,
        "embedding_model": "clip-test",
        "embedding_norm_tolerance": 1.0,
        "keyframe_id_rule": "segment_id",
    }
    paths = {}
    for name, payload in {
        "metadata": current,
        "text": text_embedding,
        "image": image_embedding,
        "policy": policy,
    }.items():
        path = tmp_path / f"{name}.json"
        write_json(path, payload)
        paths[name] = path

    assets = prepare_search_assets(
        metadata_path=paths["metadata"],
        text_embeddings_path=paths["text"],
        image_embeddings_path=paths["image"],
        policy_path=paths["policy"],
    )

    alignment = assets["embedding_alignment"]
    assert alignment["is_valid"] is True
    assert alignment["text"]["record_count"] == 1
    assert alignment["image"]["record_count"] == 1


def test_missing_translation_segment_is_blocking() -> None:
    rows = [
        scene("V001_P001_S001_SCENE_001", "V001_P001_S001", "P001", "장소1", "작품1"),
        scene("V001_P001_S001_SCENE_002", "V001_P001_S001", "P001", "장소1", "작품1"),
    ]
    translation = {
        "segment_id": rows[0]["segment_id"],
        "keyframe_id": rows[0]["segment_id"],
        "translations": {
            language: display_fields(rows[0], title="작품1", place_name="장소1")
            for language in ("ko", "en", "ja", "zh")
        },
    }

    report = validate_translation_alignment(rows, [translation])

    assert rows[1]["segment_id"] in report["missing_segment_ids"]
    assert report["blocking_errors"]


def test_added_scene_reopens_existing_source_theme_review(tmp_path) -> None:
    baseline = [
        scene("V001_P001_S001_SCENE_001", "V001_P001_S001", "P001", "장소1", "작품1")
    ]
    current = [
        *baseline,
        scene("V001_P001_S001_SCENE_002", "V001_P001_S001", "P001", "장소1", "작품1"),
    ]
    paths = {}
    for name, payload in {
        "metadata": current,
        "baseline": baseline,
        "themes": {"entries": [{"source_segment_id": "V001_P001_S001", "themes": ["flower"]}]},
        "rules": {"themes": [{"id": "flower", "label": "꽃", "terms": ["꽃"]}]},
        "policy": POLICY,
    }.items():
        path = tmp_path / f"{name}.json"
        write_json(path, payload)
        paths[name] = path

    assets = prepare_search_assets(
        metadata_path=paths["metadata"],
        baseline_metadata_path=paths["baseline"],
        theme_mapping_path=paths["themes"],
        theme_rules_path=paths["rules"],
        policy_path=paths["policy"],
    )

    assert assets["theme_mapping_carried_forward"]["entries"] == []
    assert assets["theme_review_queue"]["entries"][0]["source_segment_id"] == "V001_P001_S001"


def test_approved_empty_theme_decision_is_reused_with_same_hash(tmp_path) -> None:
    rows = [
        scene("V001_P001_S001_SCENE_001", "V001_P001_S001", "P001", "장소1", "작품1")
    ]
    metadata = tmp_path / "metadata.json"
    policy = tmp_path / "policy.json"
    decisions = tmp_path / "decisions.json"
    themes = tmp_path / "themes.json"
    write_json(metadata, rows)
    write_json(policy, POLICY)
    write_json(
        themes,
        {
            "entries": [
                {
                    "source_segment_id": "V001_P001_S001",
                    "themes": ["flower"],
                }
            ]
        },
    )
    first = prepare_search_assets(
        metadata_path=metadata,
        baseline_metadata_path=metadata,
        theme_mapping_path=themes,
        policy_path=policy,
    )
    decision = dict(first["theme_decision_registry"]["entries"][0])
    decision["status"] = "approved_empty"
    write_json(decisions, {"entries": [decision]})

    second = prepare_search_assets(
        metadata_path=metadata,
        baseline_metadata_path=metadata,
        theme_mapping_path=themes,
        theme_decisions_path=decisions,
        policy_path=policy,
    )

    assert second["theme_review_queue"]["entries"] == []
    assert second["theme_mapping_carried_forward"]["entries"] == []
    assert second["theme_decision_registry"]["entries"][0]["status"] == "approved_empty"
    assert second["theme_decision_registry"]["entries"][0]["themes"] == []


def test_empty_theme_mapping_requires_explicit_review(tmp_path) -> None:
    rows = [
        scene("V001_P001_S001_SCENE_001", "V001_P001_S001", "P001", "장소1", "작품1")
    ]
    metadata = tmp_path / "metadata.json"
    themes = tmp_path / "themes.json"
    policy = tmp_path / "policy.json"
    write_json(metadata, rows)
    write_json(
        themes,
        {"entries": [{"source_segment_id": "V001_P001_S001", "themes": []}]},
    )
    write_json(policy, POLICY)

    assets = prepare_search_assets(
        metadata_path=metadata,
        baseline_metadata_path=metadata,
        theme_mapping_path=themes,
        policy_path=policy,
    )

    assert assets["theme_mapping_carried_forward"]["entries"] == []
    assert assets["theme_review_queue"]["entries"][0]["source_segment_id"] == "V001_P001_S001"


def test_place_name_change_reopens_approved_empty_theme_decision(tmp_path) -> None:
    baseline_rows = [
        scene("V001_P001_S001_SCENE_001", "V001_P001_S001", "P001", "수원천", "작품1")
    ]
    current_rows = [dict(baseline_rows[0], place_name="해수욕장")]
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    decisions = tmp_path / "decisions.json"
    policy = tmp_path / "policy.json"
    write_json(baseline, baseline_rows)
    write_json(current, current_rows)
    write_json(policy, POLICY)
    first = prepare_search_assets(
        metadata_path=baseline,
        baseline_metadata_path=baseline,
        policy_path=policy,
    )
    decision = dict(first["theme_decision_registry"]["entries"][0])
    decision["status"] = "approved_empty"
    write_json(decisions, {"entries": [decision]})

    second = prepare_search_assets(
        metadata_path=current,
        baseline_metadata_path=baseline,
        theme_decisions_path=decisions,
        policy_path=policy,
    )

    assert second["theme_review_queue"]["entries"][0]["source_segment_id"] == "V001_P001_S001"
    assert second["theme_decision_registry"]["entries"][0]["status"] == "needs_review"


def test_explicit_empty_translation_file_is_blocking(tmp_path) -> None:
    rows = [
        scene("V001_P001_S001_SCENE_001", "V001_P001_S001", "P001", "장소1", "작품1")
    ]
    metadata = tmp_path / "metadata.json"
    translations = tmp_path / "translations.json"
    policy = tmp_path / "policy.json"
    write_json(metadata, rows)
    write_json(translations, {"records": []})
    write_json(policy, POLICY)

    assets = prepare_search_assets(
        metadata_path=metadata,
        baseline_metadata_path=metadata,
        translations_path=translations,
        policy_path=policy,
    )

    report = assets["search_sync_report"]["translation_alignment"]
    assert report["provided"] is True
    assert report["missing_segment_ids"] == ["V001_P001_S001_SCENE_001"]
    assert report["blocking_errors"]
    assert assets["search_sync_report"]["summary"]["blocking_error_count"] > 0


def test_blank_translation_content_is_blocking() -> None:
    row = scene("V001_P001_S001_SCENE_001", "V001_P001_S001", "P001", "장소1", "작품1")
    payload = {
        language: display_fields(row, title="작품1", place_name="장소1")
        for language in ("ko", "en", "ja", "zh")
    }
    payload["ja"]["description"] = "   "
    payload["zh"]["mood"] = [""]
    report = validate_translation_alignment(
        [row],
        [
            {
                "segment_id": row["segment_id"],
                "keyframe_id": row["segment_id"],
                "translations": payload,
            }
        ],
    )

    assert any("빈 문자열" in message for message in report["blocking_errors"])
    assert any("빈 번역 배열 원소" in message for message in report["blocking_errors"])


def test_evaluation_anchors_and_filters_must_match_relevant_source() -> None:
    first = scene("V001_P001_S001_SCENE_001", "V001_P001_S001", "P001", "장소1", "작품1")
    second = scene("V002_P002_S001_SCENE_001", "V002_P002_S001", "P002", "장소2", "작품2")
    second["season"] = "여름"
    evaluation = {
        "queries": [
            {
                "query_id": "Q1",
                "language": "ko",
                "query": "여름 장소",
                "relevant_source_segment_ids": [first["source_segment_id"]],
                "relevant_segment_ids": [second["segment_id"]],
                "relevant_keyframe_ids": [second["segment_id"]],
                "relevant_keyframe_paths": [second["keyframe_path"]],
                "relevant_place_ids": [second["place_id"]],
                "expected_filters": {"season": ["여름"]},
            }
        ]
    }

    report = validate_evaluation_compatibility([first, second], evaluation, POLICY)

    assert report["resolved_query_count"] == 0
    unresolved = report["unresolved"][-1]
    assert unresolved["anchor_relationship_errors"]
    assert any(
        "모두 제외" in message
        for message in unresolved["invalid_expected_filters"]
    )


def test_explicit_empty_evaluation_file_is_blocking(tmp_path) -> None:
    rows = [
        scene("V001_P001_S001_SCENE_001", "V001_P001_S001", "P001", "장소1", "작품1")
    ]
    metadata = tmp_path / "metadata.json"
    evaluation = tmp_path / "evaluation.json"
    policy = tmp_path / "policy.json"
    write_json(metadata, rows)
    write_json(evaluation, {"queries": []})
    write_json(policy, POLICY)

    assets = prepare_search_assets(
        metadata_path=metadata,
        baseline_metadata_path=metadata,
        evaluation_path=evaluation,
        policy_path=policy,
    )

    report = assets["evaluation_compatibility"]
    assert report["provided"] is True
    assert report["resolved_query_count"] == 0
    assert report["unresolved"]
    assert assets["search_sync_report"]["summary"]["blocking_error_count"] > 0


def test_source_identity_reuse_is_blocked_when_all_scenes_are_replaced(tmp_path) -> None:
    baseline_rows = [
        scene("V001_P001_S001_SCENE_001", "V001_P001_S001", "P001", "장소1", "작품1")
    ]
    current_rows = [
        scene("V001_P001_S001_SCENE_002", "V001_P001_S001", "P001", "장소1", "작품1")
    ]
    baseline_rows[0]["video_id"] = "V001_old_video"
    current_rows[0]["video_id"] = "V001_new_video"
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    policy = tmp_path / "policy.json"
    write_json(baseline, baseline_rows)
    write_json(current, current_rows)
    write_json(policy, POLICY)

    assets = prepare_search_assets(
        metadata_path=current,
        baseline_metadata_path=baseline,
        policy_path=policy,
    )

    impact = assets["change_impact"]
    assert impact["source_identity_reuse_review_source_segment_ids"] == [
        "V001_P001_S001"
    ]
    assert any(
        item["code"] == "SOURCE_ID_REUSE_IDENTITY_CHANGE"
        for item in assets["search_sync_report"]["blocking_issues"]
    )
