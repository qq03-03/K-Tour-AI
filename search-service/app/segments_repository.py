from collections.abc import Callable
from typing import Any

from src.segment_row import segment_from_row

_COLUMNS = """
    vs.segment_id, vs.source_segment_id, vs.video_id,
    vs.place_id, vs.place_name, vs.region, vs.city,
    vs.drama_title, vs.start_time, vs.end_time,
    vs.caption, vs.season, vs.time_of_day, vs.keyframe_path,
    vs.mood_tags, vs.activity_tags, vs.scene_elements, vs.k_culture_elements
"""


class SegmentsRepository:
    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    def list_segments(
        self,
        video_id: str | None,
        place_id: str | None,
        drama_title: str | None,
    ) -> list[dict[str, Any]]:
        query = f"""
            SELECT {_COLUMNS}
            FROM video_segments AS vs
            WHERE (%s::text IS NULL OR vs.video_id = %s)
              AND (%s::text IS NULL OR vs.place_id = %s)
              AND (%s::text IS NULL OR vs.drama_title = %s)
            ORDER BY vs.segment_id
        """
        params = (video_id, video_id, place_id, place_id, drama_title, drama_title)
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
        return [segment_from_row(row) for row in rows]

    def get_segment(self, segment_id: str) -> dict[str, Any] | None:
        query = f"SELECT {_COLUMNS} FROM video_segments AS vs WHERE vs.segment_id = %s"
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (segment_id,))
                row = cursor.fetchone()
        return segment_from_row(row) if row else None
