from pathlib import Path


SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "schema.sql"
)


def load_schema():
    return SCHEMA_PATH.read_text(
        encoding="utf-8",
        errors="ignore",
    ).lower()


def test_schema_defines_segment_keyframes_table():
    schema = load_schema()

    assert "create table if not exists segment_keyframes" in schema


def test_segment_keyframes_has_required_columns():
    schema = load_schema()

    required_columns = [
        "keyframe_id text primary key",
        "segment_id text not null references video_segments(segment_id)",
        "keyframe_path text not null",
        "metadata jsonb",
    ]

    for column in required_columns:
        assert column in schema


def test_schema_defines_keyframe_embeddings_table():
    schema = load_schema()

    assert "create table if not exists keyframe_embeddings" in schema


def test_keyframe_embeddings_has_512_dimension_image_embedding():
    schema = load_schema()

    assert "image_embedding vector(512)" in schema


def test_video_segments_has_drama_title():
    schema = load_schema()

    video_segments_section = schema.split(
        "create table if not exists video_segments",
        1,
    )[1].split(
        ");",
        1,
    )[0]

    assert "drama_title text" in video_segments_section


def test_schema_has_keyframe_image_embedding_index():
    schema = load_schema()

    assert "idx_keyframe_image_embedding" in schema


def test_segment_embeddings_keeps_text_embedding():
    schema = load_schema()

    assert "text_embedding vector(512)" in schema
