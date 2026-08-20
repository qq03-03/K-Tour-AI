from app.spots_repository import SpotsRepository


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.executed_query = None
        self.executed_params = None

    def execute(self, query, params=None):
        self.executed_query = query
        self.executed_params = params

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeConnection:
    def __init__(self, rows):
        self._rows = rows
        self.last_cursor = None

    def cursor(self):
        self.last_cursor = FakeCursor(self._rows)
        return self.last_cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_list_spots_filters_by_region():
    rows = [(1, "충주 중앙탑공원", "충청북도", "충북 충주시 중앙탑면 탑정안길 6", 37.017, 127.867, "설명", None)]
    connection = FakeConnection(rows)
    repo = SpotsRepository(connection_factory=lambda: connection)

    repo.list_spots(region="충청북도")

    assert connection.last_cursor.executed_params == ("충청북도", "충청북도")


def test_list_spots_maps_rows_to_dicts():
    rows = [(1, "충주 중앙탑공원", "충청북도", "충북 충주시 중앙탑면 탑정안길 6", 37.017, 127.867, "설명", None)]
    repo = SpotsRepository(connection_factory=lambda: FakeConnection(rows))

    spots = repo.list_spots(region=None)

    assert spots == [
        {
            "spot_id": 1,
            "spot_name": "충주 중앙탑공원",
            "region": "충청북도",
            "address": "충북 충주시 중앙탑면 탑정안길 6",
            "latitude": 37.017,
            "longitude": 127.867,
            "description": "설명",
            "source_url": None,
        }
    ]


def test_get_spot_returns_none_when_missing():
    repo = SpotsRepository(connection_factory=lambda: FakeConnection([]))

    assert repo.get_spot(999) is None
