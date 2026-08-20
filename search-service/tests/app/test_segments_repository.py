from app.segments_repository import SegmentsRepository


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


def _row():
    return (
        "V007_P031_S002_SCENE_001", "V007_P031_S002", "V007_Z7u5SNDq0jw",
        "P031", "충주 중앙탑공원", "충청북도", "충주시", "사랑의 불시착",
        0.0, 3.75, "야경", "summer", "night",
        "keyframes/x.jpg", ["peaceful"], ["walking"], ["bridge"], ["K드라마성지"],
    )


def test_list_segments_maps_rows_to_dicts():
    repo = SegmentsRepository(connection_factory=lambda: FakeConnection([_row()]))

    segments = repo.list_segments(video_id=None, place_id=None, drama_title=None)

    assert segments[0]["segment_id"] == "V007_P031_S002_SCENE_001"
    assert segments[0]["place_name"] == "충주 중앙탑공원"
    assert segments[0]["mood"] == ["peaceful"]


def test_get_segment_returns_none_when_missing():
    repo = SegmentsRepository(connection_factory=lambda: FakeConnection([]))

    assert repo.get_segment("does-not-exist") is None


def test_list_segments_filters_by_video_id():
    connection = FakeConnection([_row()])
    repo = SegmentsRepository(connection_factory=lambda: connection)

    repo.list_segments(video_id="V007_Z7u5SNDq0jw", place_id=None, drama_title=None)

    assert connection.last_cursor.executed_params == (
        "V007_Z7u5SNDq0jw", "V007_Z7u5SNDq0jw", None, None, None, None,
    )


def test_list_segments_filters_by_place_id():
    connection = FakeConnection([_row()])
    repo = SegmentsRepository(connection_factory=lambda: connection)

    repo.list_segments(video_id=None, place_id="P031", drama_title=None)

    assert connection.last_cursor.executed_params == (
        None, None, "P031", "P031", None, None,
    )


def test_list_segments_filters_by_drama_title():
    connection = FakeConnection([_row()])
    repo = SegmentsRepository(connection_factory=lambda: connection)

    repo.list_segments(video_id=None, place_id=None, drama_title="사랑의 불시착")

    assert connection.last_cursor.executed_params == (
        None, None, None, None, "사랑의 불시착", "사랑의 불시착",
    )


def test_list_segments_filters_by_all_three_combined():
    connection = FakeConnection([_row()])
    repo = SegmentsRepository(connection_factory=lambda: connection)

    repo.list_segments(video_id="V007_Z7u5SNDq0jw", place_id="P031", drama_title="사랑의 불시착")

    assert connection.last_cursor.executed_params == (
        "V007_Z7u5SNDq0jw", "V007_Z7u5SNDq0jw",
        "P031", "P031",
        "사랑의 불시착", "사랑의 불시착",
    )
