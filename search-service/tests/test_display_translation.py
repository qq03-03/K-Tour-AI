from __future__ import annotations

import json
from types import SimpleNamespace

from src.display_localization import build_translation_source
from src.display_translation import (
    OpenAIDisplayTranslator,
    TranslationBatch,
    build_display_translation_catalog,
)


def test_build_catalog_combines_semantic_translation_and_verified_names() -> None:
    metadata = [
        {
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
    ]
    source = build_translation_source(metadata)
    semantic = [
        {
            "segment_id": "SEG_001",
            "keyframe_id": "SEG_001__SEG_001_SCENE_01",
            "ko": {
                "description": "가을의 고요한 궁궐입니다.",
                "mood": ["고요한"],
                "activity": [],
                "scene_elements": ["궁궐"],
            },
            "ja": {
                "description": "秋の静かな宮殿です。",
                "mood": ["静かな"],
                "activity": [],
                "scene_elements": ["宮殿"],
            },
            "zh": {
                "description": "这是秋日宁静的宫殿。",
                "mood": ["宁静的"],
                "activity": [],
                "scene_elements": ["宫殿"],
            },
        }
    ]
    locations = {
        "place_aliases": [
            {
                "place_id": "P030",
                "place_name": "창경궁",
                "aliases": {
                    "ko": ["창경궁"],
                    "en": ["Changgyeonggung Palace"],
                    "ja": ["昌慶宮"],
                    "zh": ["昌庆宫"],
                },
            }
        ]
    }
    dramas = {
        "titles": [
            {
                "canonical_title": "킹덤",
                "aliases": {
                    "ko": ["킹덤"],
                    "en": ["Kingdom"],
                    "ja": ["キングダム"],
                    "zh": ["王国"],
                },
            }
        ]
    }

    catalog = build_display_translation_catalog(
        source,
        semantic,
        location_alias_payload=locations,
        drama_alias_payload=dramas,
        model="test-model",
    )

    translated = catalog["records"][0]["translations"]
    assert translated["ja"]["place_name"] == "昌慶宮"
    assert translated["ja"]["description"] == "秋の静かな宮殿です。"
    assert translated["en"]["description"] == "A quiet palace in autumn."
    assert translated["ko"]["time_of_day"] == "낮"
    assert catalog["purpose"] == "display_localization_only_no_reembedding"


def test_catalog_prefers_simplified_chinese_name_and_applies_override() -> None:
    metadata = [
        {
            "segment_id": "SEG_001",
            "video_id": "VID_001",
            "place_id": "P030",
            "place_name": "창경궁",
            "region": "서울특별시",
            "drama_title": "킹덤",
            "season": "가을",
            "time_of_day": "day",
            "description": "A palace.",
            "mood": [],
            "activity": [],
            "scene_elements": [],
            "keyframe_path": "keyframes/SEG_001/SEG_001.jpg",
        }
    ]
    source = build_translation_source(metadata)
    semantic = [
        {
            "segment_id": "SEG_001",
            "keyframe_id": "SEG_001__SEG_001",
            "ko": {"description": "궁궐입니다.", "mood": [], "activity": [], "scene_elements": []},
            "ja": {"description": "宮殿です。", "mood": [], "activity": [], "scene_elements": []},
            "zh": {"description": "这是一座宫殿。", "mood": [], "activity": [], "scene_elements": []},
        }
    ]
    catalog = build_display_translation_catalog(
        source,
        semantic,
        location_alias_payload={"place_aliases": []},
        drama_alias_payload={
            "titles": [
                {
                    "canonical_title": "킹덤",
                    "aliases": {
                        "ko": ["킹덤"], "en": ["Kingdom"], "ja": ["キングダム"],
                        "zh": ["屍戰朝鮮", "尸战朝鲜"],
                    },
                }
            ]
        },
        model="test",
        overrides_payload={
            "records": [
                {
                    "segment_id": "SEG_001", "keyframe_id": "SEG_001__SEG_001",
                    "translations": {"en": {"description": "A historic palace."}},
                }
            ]
        },
    )
    translated = catalog["records"][0]["translations"]
    assert translated["zh"]["drama_title"] == "尸战朝鲜"
    assert translated["en"]["description"] == "A historic palace."


def test_openai_payload_uses_only_anonymous_batch_number() -> None:
    source_record = build_translation_source(
        [
            {
                "segment_id": "PRIVATE_SEGMENT_001",
                "video_id": "PRIVATE_VIDEO_001",
                "place_id": "PRIVATE_PLACE_001",
                "place_name": "비공개 장소",
                "region": "서울특별시",
                "drama_title": "비공개 작품",
                "season": "가을",
                "time_of_day": "day",
                "description": "A quiet palace in autumn.",
                "mood": ["quiet"],
                "activity": [],
                "scene_elements": ["palace"],
                "keyframe_path": "keyframes/private/PRIVATE_KEYFRAME_001.jpg",
            }
        ]
    )["records"][0]

    class FakeResponses:
        def parse(self, **kwargs):
            outbound = kwargs["input"][1]["content"]
            assert "PRIVATE_SEGMENT_001" not in outbound
            assert "PRIVATE_KEYFRAME_001" not in outbound
            assert "PRIVATE_PLACE_001" not in outbound
            payload = json.loads(outbound)
            assert payload["records"][0]["item_id"] == 1
            response = {
                "records": [
                    {
                        "item_id": 1,
                        "ko": {
                            "description": "가을의 고요한 궁궐입니다.",
                            "mood": ["고요한"],
                            "activity": [],
                            "scene_elements": ["궁궐"],
                        },
                        "en": {
                            "description": "A quiet palace in autumn.",
                            "mood": ["quiet"],
                            "activity": [],
                            "scene_elements": ["palace"],
                        },
                        "ja": {
                            "description": "秋の静かな宮殿です。",
                            "mood": ["静かな"],
                            "activity": [],
                            "scene_elements": ["宮殿"],
                        },
                        "zh": {
                            "description": "这是秋日宁静的宫殿。",
                            "mood": ["宁静的"],
                            "activity": [],
                            "scene_elements": ["宫殿"],
                        },
                    }
                ]
            }
            return SimpleNamespace(output_parsed=TranslationBatch.model_validate(response))

    fake_client = SimpleNamespace(responses=FakeResponses())
    output = OpenAIDisplayTranslator(client=fake_client).translate_batch([source_record])

    assert output[0]["segment_id"] == "PRIVATE_SEGMENT_001"
    assert output[0]["keyframe_id"] == "PRIVATE_SEGMENT_001__PRIVATE_KEYFRAME_001"
