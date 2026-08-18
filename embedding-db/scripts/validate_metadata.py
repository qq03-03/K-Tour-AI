import json
import re
import sys
from pathlib import Path


REQUIRED_FIELDS = {
    "segment_id",
    "source_segment_id",
    "video_id",
    "place_id",
    "place_name",
    "region",
    "city",
    "drama_title",
    "season",
    "time_of_day",
    "start_time",
    "end_time",
    "keyframe_path",
    "description",
}

LIST_FIELDS = {
    "mood",
    "scene_elements",
    "activity",
    "k_culture_elements",
}

SCENE_ID_PATTERN = re.compile(
    r"^(?P<source>V\d+_P\d+_S\d+)_SCENE_\d+$"
)


def load_metadata(metadata_path: Path) -> list[dict]:
    """UTF-8 JSON 메타데이터 파일을 읽는다."""
    if not metadata_path.exists():
        raise FileNotFoundError(
            f"메타데이터 파일이 없습니다: {metadata_path}"
        )

    with metadata_path.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError(
            "metadata.json의 최상위 구조는 배열이어야 합니다."
        )

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


def validate_metadata(
    data: list[dict],
    project_root: Path,
) -> int:
    """메타데이터를 검사하고 오류 개수를 반환한다."""
    error_count = 0
    segment_ids = []
    keyframe_paths = []

    image_found_count = 0
    image_waiting_count = 0

    print(f"전체 데이터 개수: {len(data)}건")
    print("-" * 60)

    for index, item in enumerate(data, start=1):

        if not isinstance(item, dict):
            print(
                f"[오류] 항목 {index}: JSON 객체 형식이 아닙니다."
            )
            error_count += 1
            continue

        label = item.get(
            "segment_id",
            f"항목 {index}",
        )

        missing_fields = sorted(
            REQUIRED_FIELDS - item.keys()
        )

        if missing_fields:
            print(
                f"[오류] {label}: 필수 필드 누락 → "
                f"{', '.join(missing_fields)}"
            )
            error_count += 1

        # -------------------------------------------------
        # segment_id 검증
        # -------------------------------------------------
        segment_id = item.get("segment_id")

        if isinstance(segment_id, str) and segment_id.strip():
            segment_id = segment_id.strip()
            segment_ids.append(segment_id)

            match = SCENE_ID_PATTERN.match(segment_id)

            if not match:
                print(
                    f"[오류] {label}: "
                    f"segment_id가 SCENE 형식이 아닙니다."
                )
                error_count += 1
            else:
                expected_source_segment_id = match.group(
                    "source"
                )

                actual_source_segment_id = item.get(
                    "source_segment_id"
                )

                if (
                    actual_source_segment_id
                    != expected_source_segment_id
                ):
                    print(
                        f"[오류] {label}: "
                        f"source_segment_id 불일치 → "
                        f"기대값={expected_source_segment_id}, "
                        f"실제값={actual_source_segment_id}"
                    )
                    error_count += 1

        else:
            print(
                f"[오류] 항목 {index}: "
                f"segment_id가 비어 있습니다."
            )
            error_count += 1

        # -------------------------------------------------
        # 시간 검증
        # -------------------------------------------------
        start_time = item.get("start_time")
        end_time = item.get("end_time")

        if not isinstance(start_time, (int, float)):
            print(
                f"[오류] {label}: "
                f"start_time이 숫자가 아닙니다."
            )
            error_count += 1

        if not isinstance(end_time, (int, float)):
            print(
                f"[오류] {label}: "
                f"end_time이 숫자가 아닙니다."
            )
            error_count += 1

        if (
            isinstance(start_time, (int, float))
            and isinstance(end_time, (int, float))
        ):
            if start_time < 0:
                print(
                    f"[오류] {label}: "
                    f"start_time이 음수입니다."
                )
                error_count += 1

            if end_time <= start_time:
                print(
                    f"[오류] {label}: "
                    f"end_time이 start_time보다 "
                    f"크지 않습니다."
                )
                error_count += 1

        # -------------------------------------------------
        # description
        # -------------------------------------------------
        description = item.get("description")

        if (
            not isinstance(description, str)
            or not description.strip()
        ):
            print(
                f"[오류] {label}: "
                f"description이 비어 있습니다."
            )
            error_count += 1

        # -------------------------------------------------
        # drama_title
        #
        # 필드는 존재해야 하지만 값 자체는 null 허용.
        # 향후 85개 미확정 데이터를 삭제하지 않기 위함.
        # -------------------------------------------------
        drama_title = item.get("drama_title")

        if (
            drama_title is not None
            and not isinstance(drama_title, str)
        ):
            print(
                f"[오류] {label}: "
                f"drama_title은 문자열 또는 null이어야 합니다."
            )
            error_count += 1

        # -------------------------------------------------
        # 배열 계열
        #
        # null은 빈 배열과 동일하게 허용.
        # -------------------------------------------------
        for field_name in LIST_FIELDS:
            value = item.get(field_name)

            if value is None:
                continue

            if not isinstance(value, list):
                print(
                    f"[오류] {label}: "
                    f"{field_name}는 배열 또는 null이어야 합니다."
                )
                error_count += 1
                continue

            invalid_elements = [
                element
                for element in value
                if not isinstance(element, str)
            ]

            if invalid_elements:
                print(
                    f"[오류] {label}: "
                    f"{field_name}에 문자열이 아닌 값이 있습니다."
                )
                error_count += 1

            duplicate_values = find_duplicates(
                [
                    element.strip()
                    for element in value
                    if isinstance(element, str)
                    and element.strip()
                ]
            )

            if duplicate_values:
                print(
                    f"[주의] {label}: "
                    f"{field_name} 중복값 → "
                    f"{', '.join(duplicate_values)}"
                )

        # -------------------------------------------------
        # keyframe_path 검증
        # -------------------------------------------------
        keyframe_path = item.get("keyframe_path")

        if (
            isinstance(keyframe_path, str)
            and keyframe_path.strip()
        ):
            keyframe_path = keyframe_path.strip()
            keyframe_paths.append(keyframe_path)

            keyframe_stem = Path(
                keyframe_path
            ).stem

            if (
                isinstance(segment_id, str)
                and keyframe_stem != segment_id
            ):
                print(
                    f"[오류] {label}: "
                    f"keyframe 파일명과 segment_id 불일치 → "
                    f"{keyframe_stem}"
                )
                error_count += 1

            image_path = (
                project_root.parent
                / "K-contents_preprocessed"
                / "preprocessed_output"
                / keyframe_path
            )

            if image_path.exists():
                image_found_count += 1
            else:
                image_waiting_count += 1

        else:
            print(
                f"[오류] {label}: "
                f"keyframe_path가 비어 있습니다."
            )
            error_count += 1

    # -------------------------------------------------
    # 전체 중복 검증
    # -------------------------------------------------
    duplicate_segment_ids = find_duplicates(
        segment_ids
    )

    if duplicate_segment_ids:
        print(
            "[오류] 중복된 segment_id: "
            + ", ".join(duplicate_segment_ids)
        )
        error_count += len(
            duplicate_segment_ids
        )

    duplicate_keyframe_paths = find_duplicates(
        keyframe_paths
    )

    if duplicate_keyframe_paths:
        print(
            "[오류] 중복된 keyframe_path: "
            + ", ".join(duplicate_keyframe_paths)
        )
        error_count += len(
            duplicate_keyframe_paths
        )

    print("-" * 60)
    print(
        f"Keyframe 확인: "
        f"{image_found_count}개 존재 / "
        f"{image_waiting_count}개 대기"
    )

    if error_count == 0:
        print(
            "메타데이터 구조 검증 완료: 오류 없음"
        )
    else:
        print(
            f"메타데이터 구조 검증 실패: "
            f"오류 {error_count}건"
        )

    return error_count


def main() -> None:
    embedding_db_root = (
        Path(__file__).resolve().parent.parent
    )

    metadata_path = (
        embedding_db_root
        / "metadata"
        / "metadata.json"
    )

    try:
        data = load_metadata(
            metadata_path
        )

        error_count = validate_metadata(
            data,
            embedding_db_root,
        )

    except (
        FileNotFoundError,
        json.JSONDecodeError,
        ValueError,
    ) as error:
        print(
            f"[실행 실패] {error}"
        )
        sys.exit(1)

    sys.exit(
        1 if error_count else 0
    )


if __name__ == "__main__":
    main()