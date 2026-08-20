from app.search_response import build_search_results


def _segment(segment_id, source_segment_id, **overrides):
    base = {
        "segment_id": segment_id,
        "source_segment_id": source_segment_id,
        "video_id": "V007_Z7u5SNDq0jw",
        "place_id": "P031",
        "place_name": "충주 중앙탑공원",
        "region": "충청북도",
        "city": "충주시",
        "drama_title": "사랑의 불시착",
        "start_time": 0.0,
        "end_time": 3.75,
        "season": "summer",
        "time_of_day": "night",
        "description": "설명",
        "mood": [],
        "activity": [],
        "scene_elements": [],
        "k_culture_elements": [],
        "keyframe_path": "keyframes/x.jpg",
    }
    base.update(overrides)
    return base


def _pipeline_output(rrf_results, text_results, image_results):
    return {
        "results_by_method": {"rrf": rrf_results},
        "source_results": {"text": text_results, "image": image_results},
        "fallback_used": False,
        "fallback_reason": None,
    }


def test_maps_fields_to_the_contract_shape():
    rrf = [
        {**_segment("S001", "SEG001"), "rrf_score": 0.031, "source_ranks": {"text": 1, "image": 2}},
    ]
    text = [{"segment_id": "S001", "score": 0.82}]
    image = [{"segment_id": "S001", "score": 0.77}]
    output = _pipeline_output(rrf, text, image)

    results = build_search_results(output, top_k=5)

    assert len(results) == 1
    item = results[0]
    assert item["rank"] == 1
    assert item["segment_id"] == "S001"
    assert item["source_segment_id"] == "SEG001"
    assert item["keyframe_id"] == "S001"
    assert item["text_score"] == 0.82
    assert item["image_score"] == 0.77
    assert item["text_rank"] == 1
    assert item["image_rank"] == 2
    assert item["final_score"] == 0.031


def test_null_score_and_rank_when_a_segment_is_missing_from_one_source():
    rrf = [
        {**_segment("S001", "SEG001"), "rrf_score": 0.02, "source_ranks": {"image": 1}},
    ]
    text: list[dict] = []
    image = [{"segment_id": "S001", "score": 0.9}]
    output = _pipeline_output(rrf, text, image)

    results = build_search_results(output, top_k=5)

    assert results[0]["text_score"] is None
    assert results[0]["text_rank"] is None
    assert results[0]["image_score"] == 0.9
    assert results[0]["image_rank"] == 1


def test_dedupes_by_source_segment_id_keeping_the_best_final_score():
    rrf = [
        {**_segment("S001", "SEG001"), "rrf_score": 0.02, "source_ranks": {"text": 3}},
        {**_segment("S002", "SEG001"), "rrf_score": 0.05, "source_ranks": {"text": 1}},
        {**_segment("S003", "SEG002"), "rrf_score": 0.01, "source_ranks": {"text": 5}},
    ]
    text = [
        {"segment_id": "S001", "score": 0.5},
        {"segment_id": "S002", "score": 0.9},
        {"segment_id": "S003", "score": 0.3},
    ]
    output = _pipeline_output(rrf, text, [])

    results = build_search_results(output, top_k=5)

    assert [item["segment_id"] for item in results] == ["S002", "S003"]
    assert [item["source_segment_id"] for item in results] == ["SEG001", "SEG002"]


def test_applies_top_k_after_dedup_and_reranks_sequentially():
    rrf = [
        {**_segment("S001", "SEG001"), "rrf_score": 0.05, "source_ranks": {"text": 1}},
        {**_segment("S002", "SEG002"), "rrf_score": 0.04, "source_ranks": {"text": 2}},
        {**_segment("S003", "SEG003"), "rrf_score": 0.03, "source_ranks": {"text": 3}},
    ]
    output = _pipeline_output(rrf, [], [])

    results = build_search_results(output, top_k=2)

    assert len(results) == 2
    assert [item["rank"] for item in results] == [1, 2]
    assert [item["segment_id"] for item in results] == ["S001", "S002"]


def test_returns_empty_list_for_no_results():
    output = _pipeline_output([], [], [])
    assert build_search_results(output, top_k=5) == []
