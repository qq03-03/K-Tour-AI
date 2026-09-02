from __future__ import annotations

from run_address_translation import _normalize_duplicate_source_addresses


def test_duplicate_korean_address_uses_consistent_target_translation() -> None:
    source_rows = [
        {"place_id": "P069", "address_ko": "남이섬길 1"},
        {"place_id": "P070", "address_ko": "남이섬길 1"},
        {"place_id": "P071", "address_ko": "남이섬길 1"},
    ]
    completed: dict[str, object] = {
        "P069": {"place_id": "P069", "en": "1 Namiseom-gil", "ja": "南怡島キル1", "zh": "南怡岛街1"},
        "P070": {"place_id": "P070", "en": "1 Namiseom-gil", "ja": "南怡島キル1", "zh": "南怡島街1"},
        "P071": {"place_id": "P071", "en": "1 Namiseom-gil", "ja": "南怡島キル1", "zh": "南怡岛街1"},
    }

    changes = _normalize_duplicate_source_addresses(source_rows, completed)

    assert completed["P070"]["zh"] == "南怡岛街1"  # type: ignore[index]
    assert changes[0]["place_id"] == "P070"
