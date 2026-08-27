"""backend_integrated_search_catalog_v2.json의 theme_mapping(v7) 로드와
테마 하드 필터 테스트.

여기 케이스들은 BACKEND_THEME_MAPPING_APPLY_GUIDE.txt의 "10. 필수 확인
테스트"를 그대로 옮긴 것으로, 번들된 실제 통합 카탈로그 파일을 대상으로
검증한다 (합성 fixture가 아님). v7은 v6의 101건을 그대로 유지한 채 영상
재검수로 확정된 8건을 추가해 총 109건이다.
"""

from __future__ import annotations

from src.theme_mapping import ALLOWED_THEMES, filter_by_theme, load_theme_index, themes_for


def test_load_theme_index_reads_the_bundled_v7_catalog():
    index = load_theme_index()
    assert len(index) == 109


def test_themes_for_returns_empty_list_for_an_unmapped_segment():
    index = load_theme_index()
    assert themes_for("NOT_A_REAL_SEGMENT_ID", index) == []


def test_flower_includes_suwon_university_and_achim_goyo_arboretum():
    index = load_theme_index()
    assert "flower" in themes_for("V001_P003_S001", index)
    assert "flower" in themes_for("V046_P072_S002", index)


def test_drive_includes_jahamun_tunnel():
    index = load_theme_index()
    assert "drive" in themes_for("V028_P052_S001", index)


def test_gochang_farm_is_in_field_and_flower_but_not_autumn_leaves():
    index = load_theme_index()
    themes = themes_for("V056_P004_S001", index)
    assert "field" in themes
    assert "flower" in themes
    assert "autumn_leaves" not in themes


def test_every_mapped_theme_is_within_the_nine_allowed_ids():
    index = load_theme_index()
    for themes in index.values():
        assert set(themes) <= ALLOWED_THEMES


def test_filter_by_theme_keeps_segments_matching_any_requested_theme():
    segments = [
        {"source_segment_id": "V001_P003_S001", "segment_id": "A"},
        {"source_segment_id": "V028_P052_S001", "segment_id": "B"},
        {"source_segment_id": "V999_UNMAPPED_S001", "segment_id": "C"},
    ]
    result = filter_by_theme(segments, ["flower"])
    assert [s["segment_id"] for s in result] == ["A"]


def test_filter_by_theme_is_an_or_across_multiple_requested_themes():
    segments = [
        {"source_segment_id": "V001_P003_S001", "segment_id": "A"},  # flower
        {"source_segment_id": "V028_P052_S001", "segment_id": "B"},  # drive
        {"source_segment_id": "V999_UNMAPPED_S001", "segment_id": "C"},
    ]
    result = filter_by_theme(segments, ["flower", "drive"])
    assert [s["segment_id"] for s in result] == ["A", "B"]


def test_filter_by_theme_with_no_requested_themes_returns_all_segments_unchanged():
    segments = [{"source_segment_id": "V999_UNMAPPED_S001", "segment_id": "C"}]
    assert filter_by_theme(segments, []) == segments
    assert filter_by_theme(segments, None) == segments
