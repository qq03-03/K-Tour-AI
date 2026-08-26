from functools import cmp_to_key
from typing import Any


def build_search_results(pipeline_output: dict[str, Any], *, top_k: int) -> list[dict[str, Any]]:
    rrf_results = pipeline_output["results_by_method"].get("rrf", [])
    text_scores = {item["segment_id"]: item["score"] for item in pipeline_output["source_results"]["text"]}
    image_scores = {item["segment_id"]: item["score"] for item in pipeline_output["source_results"]["image"]}

    mapped = []
    for segment in rrf_results:
        segment_id = segment["segment_id"]
        source_ranks = segment.get("source_ranks", {})
        mapped.append(
            {
                "source_segment_id": segment["source_segment_id"],
                "segment_id": segment_id,
                "keyframe_id": segment_id,
                "keyframe_path": segment["keyframe_path"],
                "video_id": segment["video_id"],
                "place_id": segment["place_id"],
                "place_name": segment["place_name"],
                "region": segment["region"],
                "city": segment["city"],
                # No code path currently supplies real coordinates: video_segments
                # has no lat/lng columns, and the separate spots table isn't linked
                # to segments by place_id. Explicitly None until that data model
                # gap is closed (deferred to future work).
                "latitude": None,
                "longitude": None,
                "drama_title": segment["drama_title"],
                "start_time": segment["start_time"],
                "end_time": segment["end_time"],
                "season": segment["season"],
                "time_of_day": segment["time_of_day"],
                "description": segment["description"],
                "mood": segment["mood"],
                "activity": segment["activity"],
                "scene_elements": segment["scene_elements"],
                "k_culture_elements": segment["k_culture_elements"],
                "themes": segment.get("themes", []),
                "text_score": text_scores.get(segment_id),
                "image_score": image_scores.get(segment_id),
                "text_rank": source_ranks.get("text"),
                "image_rank": source_ranks.get("image"),
                "final_score": segment["rrf_score"],
            }
        )

    best_by_place: dict[str, dict[str, Any]] = {}
    for item in mapped:
        key = item["source_segment_id"]
        current_best = best_by_place.get(key)
        if current_best is None or _is_better(item, current_best):
            best_by_place[key] = item

    ordered = sorted(best_by_place.values(), key=cmp_to_key(_compare))

    trimmed = ordered[:top_k]
    for rank, item in enumerate(trimmed, start=1):
        item["rank"] = rank
    return trimmed


def _is_better(candidate: dict[str, Any], current_best: dict[str, Any]) -> bool:
    if candidate["final_score"] != current_best["final_score"]:
        return candidate["final_score"] > current_best["final_score"]
    candidate_image = candidate["image_score"] if candidate["image_score"] is not None else -1
    best_image = current_best["image_score"] if current_best["image_score"] is not None else -1
    if candidate_image != best_image:
        return candidate_image > best_image
    candidate_text = candidate["text_score"] if candidate["text_score"] is not None else -1
    best_text = current_best["text_score"] if current_best["text_score"] is not None else -1
    if candidate_text != best_text:
        return candidate_text > best_text
    return candidate["segment_id"] < current_best["segment_id"]


def _compare(a: dict[str, Any], b: dict[str, Any]) -> int:
    """Comparator for sorting, built on the same rules as `_is_better` so the
    dedup pass and the final ordering can never disagree."""
    if _is_better(a, b):
        return -1
    if _is_better(b, a):
        return 1
    return 0
