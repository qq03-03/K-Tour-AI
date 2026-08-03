import json
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

METADATA_PATH = REPO_ROOT / "metadata_vlm_final.json"

KEYFRAME_BASE = (
    REPO_ROOT
    / "K-contents_preprocessed"
    / "preprocessed_output"
)


def load_metadata():
    with METADATA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_realdata_metadata_contains_42_records():
    metadata = load_metadata()

    assert len(metadata) == 42


def test_all_metadata_keyframe_paths_are_unique():
    metadata = load_metadata()

    paths = [item["keyframe_path"] for item in metadata]

    assert len(paths) == 42
    assert len(set(paths)) == 42


def test_all_metadata_keyframe_files_exist():
    metadata = load_metadata()

    missing = []

    for item in metadata:
        image_path = KEYFRAME_BASE / item["keyframe_path"]

        if not image_path.is_file():
            missing.append(str(image_path))

    assert missing == []


def test_duplicate_segment_ids_exist_and_are_allowed():
    metadata = load_metadata()

    counts = Counter(
        item["segment_id"]
        for item in metadata
    )

    duplicates = {
        segment_id: count
        for segment_id, count in counts.items()
        if count > 1
    }

    assert duplicates
    assert len(metadata) > len(counts)


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
