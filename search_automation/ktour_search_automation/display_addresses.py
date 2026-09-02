"""place_id 단위 표시 주소 카탈로그와 번역 검수 대기열을 만든다."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


LANGUAGES = ("ko", "en", "ja", "zh")


def build_display_address_catalog(
    metadata_records: Sequence[Mapping[str, Any]],
    coordinate_payload: object | None,
    translations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """도로명 주소는 place별 1회 저장하고 번역 누락 시 한국어로 fallback한다."""

    coordinate_by_id = _coordinates_by_place_id(coordinate_payload)
    translation_by_segment = {
        _text(item.get("segment_id")): item
        for item in translations
        if _text(item.get("segment_id"))
    }
    rows_by_place: dict[str, list[Mapping[str, Any]]] = {}
    for row in metadata_records:
        place_id = _text(row.get("place_id"))
        if place_id:
            rows_by_place.setdefault(place_id, []).append(row)

    records: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []
    for place_id, rows in sorted(rows_by_place.items()):
        coordinate = coordinate_by_id.get(place_id, {})
        source_address = _text(coordinate.get("address"))
        localized: dict[str, dict[str, Any]] = {}
        first_row = rows[0]
        first_translation = translation_by_segment.get(
            _text(first_row.get("segment_id")),
            {},
        )
        translation_payload = first_translation.get("translations")
        for language in LANGUAGES:
            translated = (
                translation_payload.get(language)
                if isinstance(translation_payload, Mapping)
                and isinstance(translation_payload.get(language), Mapping)
                else {}
            )
            translated_address = _text(translated.get("address"))
            if language == "ko":
                display_address = translated_address or source_address
                address_language = "ko" if display_address else None
                status = "source" if display_address else "missing_source_address"
            elif translated_address:
                display_address = translated_address
                address_language = language
                status = "translated"
            else:
                display_address = source_address
                address_language = "ko" if source_address else None
                status = (
                    "fallback_ko_pending_translation"
                    if source_address
                    else "missing_source_address"
                )
            localized[language] = {
                "place_name": _text(translated.get("place_name"))
                or _text(first_row.get("place_name")),
                "region": _text(translated.get("region"))
                or _text(first_row.get("region")),
                "city": _text(translated.get("city"))
                or _text(first_row.get("city")),
                "address": display_address,
                "address_language": address_language,
                "address_status": status,
            }
            localized[language]["location_label"] = _location_label(
                localized[language]
            )
            if language != "ko" and status != "translated":
                review_queue.append(
                    {
                        "place_id": place_id,
                        "language": language,
                        "source_address_ko": source_address,
                        "reason": status,
                    }
                )
        records.append(
            {
                "place_id": place_id,
                "latitude": coordinate.get("latitude"),
                "longitude": coordinate.get("longitude"),
                "localized": localized,
            }
        )

    return {
        "catalog": {
            "schema_version": "1.0",
            "key": "place_id",
            "fallback_policy": "requested language address -> Korean address -> empty",
            "records": records,
        },
        "review_queue": {
            "schema_version": "1.0",
            "purpose": "address_translation_or_missing_source_review",
            "entries": review_queue,
        },
        "summary": {
            "place_count": len(records),
            "source_address_count": sum(
                bool(_text(coordinate_by_id.get(place_id, {}).get("address")))
                for place_id in rows_by_place
            ),
            "review_item_count": len(review_queue),
        },
    }


def _coordinates_by_place_id(payload: object | None) -> dict[str, Mapping[str, Any]]:
    if payload is None:
        return {}
    raw = payload.get("records") if isinstance(payload, Mapping) else payload
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise ValueError("좌표 JSON은 records 배열을 가져야 합니다.")
    result: dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise ValueError(f"coordinates[{index}]는 객체여야 합니다.")
        place_id = _text(item.get("place_id"))
        if not place_id:
            continue
        if place_id in result:
            raise ValueError(f"좌표 place_id 중복: {place_id}")
        result[place_id] = item
    return result


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _location_label(value: Mapping[str, Any]) -> str:
    """정확한 번역 주소가 없어도 지역·도시·장소명은 해당 언어로 표시한다."""

    parts: list[str] = []
    for field in ("region", "city", "place_name"):
        text = _text(value.get(field))
        if text and text not in parts:
            parts.append(text)
    return " · ".join(parts)
