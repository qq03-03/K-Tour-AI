import pytest
from pydantic import ValidationError

from app.schemas import SearchRequest, SearchResultItem, SearchResponse


def test_search_request_requires_only_query():
    request = SearchRequest(query="봄에 궁궐 산책")
    assert request.query == "봄에 궁궐 산책"
    assert request.lang == "ko"
    assert request.top_k == 5
    assert request.candidate_k is None
    assert request.place_id is None
    assert request.season is None


def test_search_request_accepts_all_filters():
    request = SearchRequest(
        query="여름 바다",
        lang="en",
        place_id=["N-P031"],
        drama_title=["사랑의 불시착"],
        region=["충청북도"],
        city=["충주시"],
        season=["summer"],
        time_of_day=["night"],
        top_k=10,
        candidate_k=50,
    )
    assert request.place_id == ["N-P031"]
    assert request.top_k == 10


def test_search_request_rejects_empty_query():
    with pytest.raises(ValidationError):
        SearchRequest(query="")


def test_search_result_item_matches_the_contract_fields():
    item = SearchResultItem(
        rank=1,
        source_segment_id="V007_P031_S002",
        segment_id="V007_P031_S002_SCENE_001",
        keyframe_id="V007_P031_S002_SCENE_001",
        keyframe_path="keyframes/V007_Z7u5SNDq0jw/V007_P031_S002_SCENE_001.jpg",
        video_id="V007_Z7u5SNDq0jw",
        place_id="P031",
        place_name="충주 중앙탑공원",
        region="충청북도",
        city="충주시",
        latitude=37.017,
        longitude=127.867,
        drama_title="사랑의 불시착",
        start_time=0.0,
        end_time=3.75,
        season="summer",
        time_of_day="night",
        description="A nighttime view of a brightly lit bridge.",
        mood=["peaceful"],
        activity=["walking"],
        scene_elements=["bridge"],
        k_culture_elements=["K드라마성지"],
        text_score=0.82,
        image_score=0.77,
        text_rank=1,
        image_rank=2,
        final_score=0.031,
    )
    assert item.rank == 1
    assert item.keyframe_id == item.segment_id


def test_search_result_item_allows_null_score_and_rank():
    item = SearchResultItem(
        rank=1,
        source_segment_id="V007_P031_S002",
        segment_id="V007_P031_S002_SCENE_001",
        keyframe_id="V007_P031_S002_SCENE_001",
        keyframe_path="keyframes/x.jpg",
        video_id="V007_Z7u5SNDq0jw",
        place_id="P031",
        place_name="충주 중앙탑공원",
        region="충청북도",
        city="충주시",
        latitude=37.017,
        longitude=127.867,
        drama_title="사랑의 불시착",
        start_time=0.0,
        end_time=3.75,
        season="summer",
        time_of_day="night",
        description="설명",
        mood=[],
        activity=[],
        scene_elements=[],
        k_culture_elements=[],
        text_score=None,
        image_score=0.77,
        text_rank=None,
        image_rank=2,
        final_score=0.02,
    )
    assert item.text_score is None
    assert item.text_rank is None


def test_search_response_wraps_results_with_fallback_flags():
    response = SearchResponse(results=[], fallback_used=True, fallback_reason="필터 결과가 없어 원문 질문으로 다시 검색했습니다.")
    assert response.results == []
    assert response.fallback_used is True
