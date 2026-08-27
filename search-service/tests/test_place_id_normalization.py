"""P013/P044 동일 장소 place_id 정규화 테스트.

강릉 주문진(P013)과 주문진 방파제(P044)는 사용자가 직접 확인한 동일 장소라,
필터 요청 시 두 id를 OR로 확장하고 표시는 canonical id(P044)로 통일한다
(BACKEND_APPLY_GUIDE.md 5절 참고). 번들된 실제 통합 카탈로그 파일을 대상으로
검증한다 (합성 fixture가 아님).
"""

from __future__ import annotations

from src.place_id_normalization import (
    canonicalize_place_id,
    expand_place_ids,
    load_place_id_normalization_index,
)


def test_load_place_id_normalization_index_maps_p013_to_p044():
    index = load_place_id_normalization_index()
    assert index == {"P013": "P044"}


def test_canonicalize_place_id_resolves_the_legacy_id_to_the_canonical_id():
    assert canonicalize_place_id("P013") == "P044"


def test_canonicalize_place_id_returns_non_legacy_ids_unchanged():
    assert canonicalize_place_id("P044") == "P044"
    assert canonicalize_place_id("P001") == "P001"


def test_expand_place_ids_adds_the_canonical_partner_for_a_legacy_id():
    assert expand_place_ids(["P013"]) == ["P013", "P044"]


def test_expand_place_ids_adds_the_legacy_partner_for_a_canonical_id():
    assert expand_place_ids(["P044"]) == ["P044", "P013"]


def test_expand_place_ids_leaves_unrelated_ids_unchanged():
    assert expand_place_ids(["P001", "P002"]) == ["P001", "P002"]


def test_expand_place_ids_does_not_duplicate_when_both_are_already_requested():
    assert expand_place_ids(["P013", "P044"]) == ["P013", "P044"]
