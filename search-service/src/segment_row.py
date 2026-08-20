from collections.abc import Sequence
from typing import Any


def segment_from_row(row: Sequence[Any]) -> dict[str, Any]:
    """Maps a video_segments row to a segment dict.

    Expects columns in exactly this order: segment_id, source_segment_id,
    video_id, place_id, place_name, region, city, drama_title, start_time,
    end_time, caption, season, time_of_day, keyframe_path, mood_tags,
    activity_tags, scene_elements, k_culture_elements.
    """
    return {
        "segment_id": row[0],
        "source_segment_id": row[1],
        "video_id": row[2],
        "place_id": row[3],
        "place_name": row[4],
        "region": row[5],
        "city": row[6],
        "drama_title": row[7],
        "start_time": float(row[8]),
        "end_time": float(row[9]),
        "description": row[10],
        "season": row[11],
        "time_of_day": row[12],
        "keyframe_path": row[13],
        "mood": list(row[14] or []),
        "activity": list(row[15] or []),
        "scene_elements": list(row[16] or []),
        "k_culture_elements": list(row[17] or []),
    }
