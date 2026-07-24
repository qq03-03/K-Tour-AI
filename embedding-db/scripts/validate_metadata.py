import json
import sys
from pathlib import Path


REQUIRED_FIELDS = {
    "segment_id",
    "video_id",
    "spot_name",
    "start_time",
    "end_time",
    "keyframe_path",
    "description",
}

LIST_FIELDS = {
    "mood",
    "scene_elements",
    "activity",
}


def load_metadata(metadata_path: Path) -> list[dict]:
    """UTF-8 JSON 메타데이터 파일을 읽는다."""
    if not metadata_path.exists():
        raise FileNotFoundError(f"메타데이터 파일이 없습니다: {metadata_path}")

    with metadata_path.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("metadata.json의 최상위 구조는 배열이어야 합니다.")

    return data


def find_duplicates(values: list[str]) -> list[str]:
    """목록 안의 중복 값을 반환한다."""
    seen = set()
    duplicates = set()

    for value in values:
        if value in seen:
            duplicates.add(value)
        else:
            seen.add(value)

    return sorted(duplicates)


def validate_metadata(data: list[dict], project_root: Path) -> int:
    """메타데이터를 검사하고 오류 개수를 반환한다."""
    error_count = 0
    segment_ids = []

    print(f"전체 데이터 개수: {len(data)}건")
    print("-" * 60)

    for index, item in enumerate(data, start=1):
        label = item.get("segment_id", f"항목 {index}")

        if not isinstance(item, dict):
            print(f"[오류] 항목 {index}: JSON 객체 형식이 아닙니다.")
            error_count += 1
            continue

        missing_fields = sorted(REQUIRED_FIELDS - item.keys())

        if missing_fields:
            print(
                f"[오류] {label}: 필수 필드 누락 → "
                f"{', '.join(missing_fields)}"
            )
            error_count += 1

        segment_id = item.get("segment_id")
        if isinstance(segment_id, str) and segment_id.strip():
            segment_ids.append(segment_id)
        else:
            print(f"[오류] 항목 {index}: segment_id가 비어 있습니다.")
            error_count += 1

        start_time = item.get("start_time")
        end_time = item.get("end_time")

        if not isinstance(start_time, (int, float)):
            print(f"[오류] {label}: start_time이 숫자가 아닙니다.")
            error_count += 1

        if not isinstance(end_time, (int, float)):
            print(f"[오류] {label}: end_time이 숫자가 아닙니다.")
            error_count += 1

        if isinstance(start_time, (int, float)) and isinstance(
            end_time, (int, float)
        ):
            if start_time < 0:
                print(f"[오류] {label}: start_time이 음수입니다.")
                error_count += 1

            if end_time <= start_time:
                print(
                    f"[오류] {label}: end_time이 start_time보다 "
                    f"크지 않습니다."
                )
                error_count += 1

        description = item.get("description")
        if not isinstance(description, str) or not description.strip():
            print(f"[오류] {label}: description이 비어 있습니다.")
            error_count += 1

        for field_name in LIST_FIELDS:
            value = item.get(field_name, [])

            if not isinstance(value, list):
                print(f"[오류] {label}: {field_name}는 배열이어야 합니다.")
                error_count += 1
                continue

            duplicate_values = find_duplicates(
                [str(element) for element in value]
            )

            if duplicate_values:
                print(
                    f"[주의] {label}: {field_name} 중복값 → "
                    f"{', '.join(duplicate_values)}"
                )

        keyframe_path = item.get("keyframe_path")

        if isinstance(keyframe_path, str) and keyframe_path.strip():
            image_path = project_root / keyframe_path

            if image_path.exists():
                print(f"[정상] {label}: 이미지 확인")
            else:
                print(
                    f"[대기] {label}: 이미지가 아직 없습니다 → "
                    f"{image_path}"
                )

    duplicate_segment_ids = find_duplicates(segment_ids)

    if duplicate_segment_ids:
        print(
            "[오류] 중복된 segment_id: "
            + ", ".join(duplicate_segment_ids)
        )
        error_count += len(duplicate_segment_ids)

    print("-" * 60)

    if error_count == 0:
        print("메타데이터 구조 검증 완료: 오류 없음")
    else:
        print(f"메타데이터 구조 검증 실패: 오류 {error_count}건")

    return error_count


def main() -> None:
    embedding_db_root = Path(__file__).resolve().parent.parent
    metadata_path = embedding_db_root / "metadata" / "metadata.json"

    try:
        data = load_metadata(metadata_path)
        error_count = validate_metadata(data, embedding_db_root)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as error:
        print(f"[실행 실패] {error}")
        sys.exit(1)

    sys.exit(1 if error_count else 0)


if __name__ == "__main__":
    main()
