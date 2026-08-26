from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.api_contract import validate_search_request, validate_search_response


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_example(name: str):
    return json.loads((PROJECT_ROOT / "data" / name).read_text(encoding="utf-8"))


def test_request_example_matches_contract() -> None:
    request = validate_search_request(load_example("search_request_example.json"))

    assert request["lang"] == "ko"
    assert request["top_k"] == 5


def test_response_example_matches_contract() -> None:
    response = validate_search_response(load_example("search_response_example.json"))

    assert response["results"][0]["source_segment_id"] == "V008_P014_S001"
    assert response["results"][0]["segment_id"] == "V008_P014_S001_SCENE_001"


def test_response_rejects_duplicate_segment_results() -> None:
    response = load_example("search_response_example.json")
    duplicate = dict(response["results"][0])
    duplicate["rank"] = 2
    response["results"].append(duplicate)

    with pytest.raises(ValueError, match="중복"):
        validate_search_response(response)


def test_response_rejects_two_scenes_from_same_source_segment() -> None:
    response = load_example("search_response_example.json")
    second_scene = dict(response["results"][0])
    second_scene["rank"] = 2
    second_scene["segment_id"] = "V008_P014_S001_SCENE_002"
    second_scene["keyframe_id"] = "V008_P014_S001_SCENE_002"
    second_scene["keyframe_path"] = (
        "keyframes/GOBLIN_03/V008_P014_S001_SCENE_002.jpg"
    )
    response["results"].append(second_scene)

    with pytest.raises(ValueError, match="source_segment_id가 중복"):
        validate_search_response(response)


def test_response_requires_source_segment_id() -> None:
    response = load_example("search_response_example.json")
    del response["results"][0]["source_segment_id"]

    with pytest.raises(ValueError, match="source_segment_id"):
        validate_search_response(response)


def test_coordinate_pair_must_be_complete() -> None:
    response = load_example("search_response_example.json")
    response["results"][0]["longitude"] = None

    with pytest.raises(ValueError, match="둘 다"):
        validate_search_response(response)


def test_request_rejects_invalid_top_k() -> None:
    request = load_example("search_request_example.json")
    request["top_k"] = 0

    with pytest.raises(ValueError, match="1~50"):
        validate_search_request(request)


def test_not_found_response_must_not_return_unrelated_results() -> None:
    response = load_example("search_response_example.json")
    response["query_status"] = "not_found"
    response["possible_title"] = "서울의 봄"

    with pytest.raises(ValueError, match="비어 있어야"):
        validate_search_response(response)
