import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

METADATA_PATH = (
    REPO_ROOT
    / "embedding-db"
    / "metadata"
    / "metadata.json"
)

KEYFRAME_BASE = (
    REPO_ROOT
    / "K-contents_preprocessed"
    / "preprocessed_output"
)


def load_metadata():
    with METADATA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_realdata_metadata_contains_45_records():
    metadata = load_metadata()

    assert len(metadata) == 45


def test_all_metadata_keyframe_paths_are_unique():
    metadata = load_metadata()

    paths = [item["keyframe_path"] for item in metadata]

    assert len(paths) == 45
    assert len(set(paths)) == 45


def test_all_metadata_keyframe_files_exist():
    metadata = load_metadata()

    missing = []

    for item in metadata:
        image_path = KEYFRAME_BASE / item["keyframe_path"]

        if not image_path.is_file():
            missing.append(str(image_path))

    assert missing == []


def test_all_segment_ids_are_unique():
    metadata = load_metadata()

    segment_ids = [
        item["segment_id"]
        for item in metadata
    ]

    assert len(segment_ids) == 45
    assert len(set(segment_ids)) == 45


def test_region_and_drama_title_exist():
    metadata = load_metadata()

    for item in metadata:
        assert isinstance(item.get("region"), str)
        assert item["region"].strip()

        assert isinstance(item.get("drama_title"), str)
        assert item["drama_title"].strip()


def test_segment_time_range_is_valid():
    metadata = load_metadata()

    for item in metadata:
        start_time = float(item["start_time"])
        end_time = float(item["end_time"])

        assert start_time >= 0
        assert end_time > start_time


def test_vlm_list_fields_are_lists():
    metadata = load_metadata()

    list_fields = (
        "mood",
        "scene_elements",
        "activity",
    )

    for item in metadata:
        for field in list_fields:
            assert isinstance(
                item.get(field),
                list,
            ), (
                f"{item['segment_id']} "
                f"{item['keyframe_path']} "
                f"{field} is not a list"
            )

def test_obs_02_scene_02_uses_correct_haenggung_dong_spelling():
    metadata = load_metadata()

    item = next(
        item
        for item in metadata
        if item["segment_id"] == "OBS_02_SCENE_02"
    )

    assert "Haenggung-dong" in item["description"]
    assert "Hwangeong-dong" not in item["description"]


def test_hotel_deluna_mangsang_02_uses_correct_mangsang_spelling():
    metadata = load_metadata()

    item = next(
        item
        for item in metadata
        if item["segment_id"]
        == "hotel_deluna_mangsang_02_SCENE_01"
    )

    assert "MANGSANG" in item["description"]
    assert "MANGYONGDAE" not in item["description"]


def test_kingdom_scene_03_is_separate_changgyeonggung_place():
    import re

    metadata = load_metadata()

    item = next(
        item
        for item in metadata
        if item["segment_id"]
        == "kingdom_changdeok_01_SCENE_03"
    )

    assert item["place_id"] == "P030"
    assert item["place_name"] == "창경궁"
    assert "Changgyeonggung" in item["description"]
    assert re.search(
    r"\bChanggyeonggu\b",
    item["description"],
    ) is None

    p017_items = [
        row
        for row in metadata
        if row.get("place_id") == "P017"
    ]

    assert p017_items
    assert all(
        row["place_name"] == "창덕궁"
        for row in p017_items
    )
