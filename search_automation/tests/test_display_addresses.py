from __future__ import annotations

from ktour_search_automation.display_addresses import build_display_address_catalog


def test_address_catalog_is_place_based_and_falls_back_to_korean() -> None:
    metadata = [
        {
            "segment_id": "SCENE_001",
            "place_id": "P001",
            "place_name": "경복궁",
            "region": "서울특별시",
            "city": "서울특별시",
        },
        {
            "segment_id": "SCENE_002",
            "place_id": "P001",
            "place_name": "경복궁",
            "region": "서울특별시",
            "city": "서울특별시",
        },
    ]
    coordinates = {
        "records": [
            {
                "place_id": "P001",
                "address": "서울특별시 종로구 사직로 161",
                "latitude": 37.0,
                "longitude": 127.0,
            }
        ]
    }
    translations = [
        {
            "segment_id": "SCENE_001",
            "translations": {
                "ko": {"place_name": "경복궁", "region": "서울특별시", "city": "서울특별시"},
                "en": {"place_name": "Gyeongbokgung Palace", "region": "Seoul", "city": "Seoul"},
                "ja": {"place_name": "景福宮", "region": "ソウル", "city": "ソウル"},
                "zh": {"place_name": "景福宫", "region": "首尔", "city": "首尔"},
            },
        }
    ]

    result = build_display_address_catalog(metadata, coordinates, translations)

    assert result["summary"]["place_count"] == 1
    assert result["summary"]["source_address_count"] == 1
    record = result["catalog"]["records"][0]
    assert record["localized"]["en"]["place_name"] == "Gyeongbokgung Palace"
    assert record["localized"]["en"]["location_label"] == "Seoul · Gyeongbokgung Palace"
    assert record["localized"]["en"]["address"] == "서울특별시 종로구 사직로 161"
    assert record["localized"]["en"]["address_status"] == "fallback_ko_pending_translation"
    assert len(result["review_queue"]["entries"]) == 3


def test_existing_translated_address_is_used_without_review() -> None:
    metadata = [
        {
            "segment_id": "SCENE_001",
            "place_id": "P001",
            "place_name": "장소",
            "region": "서울",
            "city": "서울",
        }
    ]
    coordinates = {"records": [{"place_id": "P001", "address": "한국어 주소"}]}
    translations = [
        {
            "segment_id": "SCENE_001",
            "translations": {
                "en": {"address": "English address"},
                "ja": {"address": "日本語住所"},
                "zh": {"address": "中文地址"},
            },
        }
    ]

    result = build_display_address_catalog(metadata, coordinates, translations)

    assert result["catalog"]["records"][0]["localized"]["en"]["address"] == "English address"
    assert result["review_queue"]["entries"] == []
