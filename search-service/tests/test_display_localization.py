from __future__ import annotations

import copy

import pytest

from src.display_localization import (
    build_translation_source,
    derive_keyframe_id,
    localize_search_result,
    normalize_display_language,
    validate_translation_catalog,
)


def metadata_record() -> dict:
    return {
        "segment_id": "SEG_001",
        "video_id": "VID_001",
        "place_id": "P030",
        "place_name": "창경궁",
        "region": "서울특별시",
        "drama_title": "킹덤",
        "season": "가을",
        "time_of_day": "day",
        "description": "A quiet palace in autumn.",
        "mood": ["quiet"],
        "activity": [],
        "scene_elements": ["palace"],
        "keyframe_path": "keyframes/SEG_001/SEG_001_SCENE_01.jpg",
    }


def localized_fields(language: str) -> dict:
    descriptions = {
        "ko": "가을의 고요한 궁궐 풍경입니다.",
        "en": "A quiet palace scene in autumn.",
        "ja": "秋の静かな宮殿の風景です。",
        "zh": "这是秋日宁静的宫殿风景。",
    }
    place_names = {"ko": "창경궁", "en": "Changgyeonggung Palace", "ja": "昌慶宮", "zh": "昌庆宫"}
    return {
        "drama_title": {"ko": "킹덤", "en": "Kingdom", "ja": "キングダム", "zh": "王国"}[language],
        "place_name": place_names[language],
        "region": {"ko": "서울특별시", "en": "Seoul", "ja": "ソウル特別市", "zh": "首尔特别市"}[language],
        "season": {"ko": "가을", "en": "autumn", "ja": "秋", "zh": "秋季"}[language],
        "time_of_day": {"ko": "낮", "en": "daytime", "ja": "昼", "zh": "白天"}[language],
        "description": descriptions[language],
        "mood": [{"ko": "고요한", "en": "quiet", "ja": "静かな", "zh": "宁静的"}[language]],
        "activity": [],
        "scene_elements": [{"ko": "궁궐", "en": "palace", "ja": "宮殿", "zh": "宫殿"}[language]],
    }


def translation_catalog() -> dict:
    return {
        "schema_version": 1,
        "records": [
            {
                "segment_id": "SEG_001",
                "keyframe_id": "SEG_001__SEG_001_SCENE_01",
                "translations": {
                    language: localized_fields(language)
                    for language in ("ko", "en", "ja", "zh")
                },
            }
        ],
    }


def test_build_source_derives_keyframe_id_from_path() -> None:
    source = build_translation_source([metadata_record()])

    assert source["record_count"] == 1
    assert source["purpose"] == "display_localization_only_no_reembedding"
    assert source["records"][0]["keyframe_id"] == "SEG_001__SEG_001_SCENE_01"


def test_localize_result_keeps_scores_and_replaces_display_fields() -> None:
    result = {
        **metadata_record(),
        "keyframe_id": "SEG_001__SEG_001_SCENE_01",
        "rank": 1,
        "text_score": 0.7,
        "image_score": 0.8,
        "final_score": 0.75,
    }

    localized = localize_search_result(result, lang="ja-JP", catalog=translation_catalog())

    assert localized["place_name"] == "昌慶宮"
    assert localized["description"] == "秋の静かな宮殿の風景です。"
    assert localized["display_lang"] == "ja"
    assert localized["segment_id"] == result["segment_id"]
    assert localized["final_score"] == result["final_score"]


def test_missing_requested_language_falls_back_to_korean() -> None:
    catalog = translation_catalog()
    del catalog["records"][0]["translations"]["ja"]

    localized = localize_search_result(metadata_record(), lang="ja", catalog=catalog)

    assert localized["description"] == "가을의 고요한 궁궐 풍경입니다."
    assert localized["display_lang"] == "ko"


def test_missing_catalog_record_preserves_source_result() -> None:
    localized = localize_search_result(metadata_record(), lang="zh", catalog={"records": []})

    assert localized["description"] == metadata_record()["description"]
    assert localized["display_lang"] == "source"


def test_catalog_validation_requires_all_languages_and_matching_ids() -> None:
    catalog = translation_catalog()
    validated = validate_translation_catalog(catalog, expected_source=[metadata_record()])
    assert validated["record_count"] == 1

    broken = copy.deepcopy(catalog)
    del broken["records"][0]["translations"]["zh"]
    with pytest.raises(ValueError, match="번역 언어 누락"):
        validate_translation_catalog(broken, expected_source=[metadata_record()])


def test_keyframe_and_language_validation() -> None:
    assert derive_keyframe_id(metadata_record()) == "SEG_001__SEG_001_SCENE_01"
    assert normalize_display_language("zh-CN") == "zh"
    assert normalize_display_language("auto") == "ko"
    with pytest.raises(ValueError, match="ko/en/ja/zh"):
        normalize_display_language("fr")
