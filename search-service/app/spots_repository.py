from collections.abc import Callable
from typing import Any


class SpotsRepository:
    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    def list_spots(self, region: str | None) -> list[dict[str, Any]]:
        query = """
            SELECT spot_id, spot_name, region, address, latitude, longitude, description, source_url
            FROM spots
            WHERE (%s::text IS NULL OR region = %s)
            ORDER BY spot_id
        """
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (region, region))
                rows = cursor.fetchall()
        return [self._spot_from_row(row) for row in rows]

    def get_spot(self, spot_id: int) -> dict[str, Any] | None:
        query = """
            SELECT spot_id, spot_name, region, address, latitude, longitude, description, source_url
            FROM spots
            WHERE spot_id = %s
        """
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (spot_id,))
                row = cursor.fetchone()
        return self._spot_from_row(row) if row else None

    @staticmethod
    def _spot_from_row(row) -> dict[str, Any]:
        return {
            "spot_id": row[0],
            "spot_name": row[1],
            "region": row[2],
            "address": row[3],
            "latitude": row[4],
            "longitude": row[5],
            "description": row[6],
            "source_url": row[7],
        }
