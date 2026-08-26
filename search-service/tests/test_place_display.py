"""place_display_catalog.translated.json 로드와 다국어 표시 조회 테스트.

P031(충주 중앙탑공원)을 앵커로 쓴다: 실제 번들 카탈로그에 4개 언어
전부 번역된 주소가 있는 레코드라, README_BACKEND_APPLY.md 5절의
fallback 규칙까지 실제 데이터로 검증할 수 있다.
"""

from __future__ import annotations

from src.place_display import display_for, load_place_catalog


def test_load_place_catalog_reads_the_bundled_file():
    catalog = load_place_catalog()
    assert len(catalog) == 74


def test_display_for_returns_none_for_an_unknown_place_id():
    catalog = load_place_catalog()
    assert display_for("NOT_A_REAL_PLACE", "ko", catalog=catalog) is None


def test_display_for_korean_returns_the_source_address():
    catalog = load_place_catalog()
    display = display_for("P031", "ko", catalog=catalog)
    assert display["place_name"] == "충주 중앙탑공원"
    assert display["region"] == "충청북도"
    assert display["address"] == "충북 충주시 중앙탑면 탑정안길 6"
    assert display["location_label"] == "충청북도 · 충주시 · 충주 중앙탑공원"
    assert display["latitude"] == 37.01711679176299
    assert display["longitude"] == 127.86685914869933


def test_display_for_english_returns_a_real_translated_address_not_korean():
    catalog = load_place_catalog()
    display = display_for("P031", "en", catalog=catalog)
    assert display["place_name"] == "Chungju Jungangtap Park"
    assert display["region"] == "Chungcheongbuk-do"
    assert display["address"] == "6 Tapjeongan-gil, Jungangtap-myeon, Chungju-si, Chungcheongbuk-do"


def test_display_for_japanese_and_chinese_are_also_translated():
    catalog = load_place_catalog()
    ja = display_for("P031", "ja", catalog=catalog)
    zh = display_for("P031", "zh", catalog=catalog)
    assert ja["place_name"] == "忠州中央塔公園"
    assert zh["place_name"] == "忠州中央塔公园"


def test_display_for_falls_back_to_korean_address_when_the_language_has_none():
    # P001 (수원 화성) has an empty address in every language in the
    # bundled catalog (missing_source_address) -- falling back to Korean
    # doesn't help here, so it should end up as "", never crash.
    catalog = load_place_catalog()
    display = display_for("P001", "en", catalog=catalog)
    assert display["place_name"] == "Suwon Hwaseong"
    assert display["address"] == ""


def test_display_for_unknown_language_falls_back_to_korean():
    catalog = load_place_catalog()
    display = display_for("P031", "fr", catalog=catalog)
    assert display["place_name"] == "충주 중앙탑공원"
