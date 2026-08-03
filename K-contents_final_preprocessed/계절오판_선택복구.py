from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np


VIDEO_EXTENSIONS = (".mp4", ".mkv", ".webm", ".mov", ".m4v")
SEASON_REASON_PREFIXES = (
    "입력 계절 단서 부족",
    "다른 계절 단서가 더 강함",
)

SEASON_BY_SOURCE = {
    "V001_P001_S001": "봄",
    "V001_P002_S001": "봄",
    "V001_P003_S001": "봄",
    "V002_P004_S001": "봄",
    "V002_P004_S002": "봄",
    "V002_P004_S003": "봄",
    "V013_P019_S001": "봄",
    "V013_P020_S001": "봄",

    "V004_P008_S001": "여름",
    "V004_P009_S001": "여름",
    "V005_P010_S003": "여름",
    "V008_P013_S002": "여름",
    "V006_P011_S002": "여름",
    "V009_P022_S001": "여름",
    "V011_P016_S002": "여름",
    "V011_P017_S002": "여름",

    "V003_P006_S001": "가을",
    "V007_P012_S001": "가을",
    "V011_P017_S001": "가을",
    "V012_P018_S001": "가을",

    "V006_P011_S001": "겨울",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, value: Any) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp.replace(path)


def safe_name(value: str) -> str:
    result = "".join(
        char if char.isalnum() or char in "-_" else "_"
        for char in str(value)
    ).strip("_")
    return result or "video"


def first_existing(root: Path, names: list[str]) -> Path:
    for name in names:
        path = root / name
        if path.exists():
            return path
    return root / names[0]


def get_ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found

    try:
        import imageio_ffmpeg
        found = imageio_ffmpeg.get_ffmpeg_exe()
        if found and Path(found).exists():
            return str(found)
    except Exception:
        pass

    raise RuntimeError(
        "FFmpeg를 찾을 수 없습니다. 먼저 실행.ps1 setup을 실행하세요."
    )


def run_command(command: list[str]) -> None:
    print("실행:", " ".join(command))
    result = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout[-5000:])


def extract_clip(
    source_video: Path,
    output_path: Path,
    start_time: float,
    end_time: float,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = end_time - start_time
    run_command([
        get_ffmpeg(),
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-ss", f"{start_time:.3f}",
        "-i", str(source_video),
        "-t", f"{duration:.3f}",
        "-map", "0:v:0",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-crf", "19",
        "-preset", "fast",
        "-c:a", "aac",
        "-movflags", "+faststart",
        str(output_path),
    ])


def extract_keyframe(
    source_video: Path,
    output_path: Path,
    time_sec: float,
) -> None:
    capture = cv2.VideoCapture(str(source_video))
    if not capture.isOpened():
        raise RuntimeError(f"원본 영상을 열 수 없습니다: {source_video}")

    capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, time_sec) * 1000.0)
    ok, frame = capture.read()
    capture.release()
    if not ok or frame is None:
        raise RuntimeError(
            f"대표 이미지 추출 실패: {source_video} @ {time_sec}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), frame):
        raise RuntimeError(f"대표 이미지 저장 실패: {output_path}")


def make_contact_sheet(
    image_items: list[tuple[Path, str]],
    output_path: Path,
) -> None:
    loaded: list[tuple[np.ndarray, str]] = []
    for path, label in image_items:
        image = cv2.imread(str(path))
        if image is not None:
            loaded.append((image, label))

    if not loaded:
        return

    tile_w = 320
    tile_h = 260
    label_h = 65
    columns = min(4, len(loaded))
    rows = math.ceil(len(loaded) / columns)

    canvas = np.full(
        (rows * (tile_h + label_h), columns * tile_w, 3),
        255,
        dtype=np.uint8,
    )

    for index, (image, label) in enumerate(loaded):
        height, width = image.shape[:2]
        scale = min(tile_w / width, tile_h / height)
        resized = cv2.resize(
            image,
            (
                max(1, int(width * scale)),
                max(1, int(height * scale)),
            ),
        )

        row = index // columns
        column = index % columns
        x = column * tile_w
        y = row * (tile_h + label_h)
        ox = x + (tile_w - resized.shape[1]) // 2
        oy = y + (tile_h - resized.shape[0]) // 2
        canvas[
            oy:oy + resized.shape[0],
            ox:ox + resized.shape[1],
        ] = resized

        cv2.putText(
            canvas,
            label[:48],
            (x + 8, y + tile_h + 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (0, 0, 0),
            1,
            cv2.LINE_AA,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), canvas)


def find_source_video(
    source_dir: Path,
    video_result: dict[str, Any],
) -> Path:
    raw_path = Path(str(video_result.get("raw_video_path", "")))
    basename = raw_path.name
    if basename:
        candidate = source_dir / basename
        if candidate.exists():
            return candidate

    video_id = safe_name(str(video_result.get("video_id", "")))
    youtube_id = safe_name(str(video_result.get("youtube_id", "")))
    patterns = [
        f"{video_id}_{youtube_id}.*",
        f"{video_id}*",
        f"*{youtube_id}*",
    ]

    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(
            path
            for path in source_dir.glob(pattern)
            if path.is_file()
            and path.suffix.lower() in VIDEO_EXTENSIONS
        )

    if not candidates:
        raise FileNotFoundError(
            f"원본 영상을 찾을 수 없습니다: "
            f"video_id={video_result.get('video_id')} / {source_dir}"
        )

    return max(
        set(candidates),
        key=lambda path: path.stat().st_size,
    )


def next_segment_id(
    video_id: str,
    existing_segments: list[dict[str, Any]],
) -> str:
    prefix = safe_name(video_id)
    maximum = 0
    pattern = re.compile(
        rf"^{re.escape(prefix)}_SCENE_(\d+)$"
    )
    for segment in existing_segments:
        match = pattern.match(str(segment.get("segment_id", "")))
        if match:
            maximum = max(maximum, int(match.group(1)))
    return f"{prefix}_SCENE_{maximum + 1:02d}"


def update_manual_season(
    item: dict[str, Any],
    verified_season: str,
    review_note: str,
    *,
    rejected: bool,
) -> list[str]:
    old_detected = item.get(
        "auto_detected_season",
        item.get(
            "overall_detected_season",
            item.get("detected_season", ""),
        ),
    )
    old_score = item.get(
        "auto_season_score",
        item.get("season_score"),
    )
    scores = item.get("season_scores")
    if not isinstance(scores, dict):
        scores = {}

    item.setdefault(
        "auto_expected_season",
        item.get("expected_season"),
    )
    item.setdefault("auto_detected_season", old_detected)
    item.setdefault("auto_season_score", old_score)

    item["expected_season"] = verified_season
    item["expected_seasons"] = [verified_season]
    item["detected_season"] = verified_season
    item["overall_detected_season"] = verified_season
    item["verified_season"] = verified_season
    item["season_verified"] = True
    item["season_review_status"] = "reviewed"
    item["manual_season_override"] = True
    item["season_review_note"] = review_note

    if verified_season in scores:
        item["season_score"] = scores[verified_season]
    else:
        item["season_score"] = old_score

    if not rejected:
        return []

    original_reasons = list(
        item.get(
            "auto_rejection_reasons",
            item.get("rejection_reasons") or [],
        )
    )
    item["auto_rejection_reasons"] = original_reasons
    remaining = [
        reason
        for reason in original_reasons
        if not str(reason).startswith(SEASON_REASON_PREFIXES)
    ]
    item["rejection_reasons"] = remaining
    item["remaining_non_season_rejection_reasons"] = remaining
    item["season_rejection_cancelled"] = (
        len(remaining) < len(original_reasons)
    )
    return remaining


def build_segment(
    record: dict[str, Any],
    video_result: dict[str, Any],
    candidate: dict[str, Any],
    segment_id: str,
    verified_season: str,
    clip_rel: str,
    keyframe_rel: str,
) -> dict[str, Any]:
    review_note = (
        f"{candidate.get('source_segment_id')} 사용자 영상 검수 결과 "
        f"{verified_season}으로 확정. 자동 계절 제외를 취소하고 "
        "기존 후보 시간으로 선택 복구함."
    )
    scores = candidate.get("season_scores")
    if not isinstance(scores, dict):
        scores = {}

    return {
        "segment_id": segment_id,
        "source_segment_id": candidate.get("source_segment_id"),
        "video_id": video_result.get("video_id"),
        "youtube_id": video_result.get("youtube_id"),
        "drama_title": record.get("drama_title", ""),
        "place_candidates": record.get("place_candidates", []),
        "region": record.get("region", ""),
        "city": record.get("city", ""),
        "expected_seasons": [verified_season],
        "expected_season": verified_season,
        "detected_season": verified_season,
        "overall_detected_season": verified_season,
        "auto_detected_season": candidate.get(
            "auto_detected_season",
            candidate.get("overall_detected_season", ""),
        ),
        "season_score": scores.get(
            verified_season,
            candidate.get("season_score"),
        ),
        "auto_season_score": candidate.get(
            "auto_season_score",
            candidate.get("season_score"),
        ),
        "season_scores": scores,
        "verified_season": verified_season,
        "season_verified": True,
        "season_review_status": "reviewed",
        "season_match_required": False,
        "manual_season_override": True,
        "season_review_note": review_note,
        "start_time": candidate.get("start_time"),
        "end_time": candidate.get("end_time"),
        "duration": round(
            float(candidate.get("end_time"))
            - float(candidate.get("start_time")),
            3,
        ),
        "representative_frame_time": candidate.get(
            "representative_frame_time"
        ),
        "description": (
            candidate.get("source_description")
            or record.get("candidate_ranges", [{}])[0].get(
                "description",
                "수동 계절 검수로 복구한 장면",
            )
        ),
        "selection_score": candidate.get("total_score"),
        "scene_change_confidence": candidate.get(
            "scene_change_confidence"
        ),
        "quality_components": candidate.get(
            "quality_components",
            {},
        ),
        "selection_reason": (
            "기존 자동 선별에서 계절 색상 오판으로 제외됐으나, "
            "사용자 수동 검수 계절과 일치하고 흐림·암부·과노출 등 "
            "다른 제외 사유가 없어 기존 후보 시간으로 선택 복구"
        ),
        "auto_rejection_reasons": candidate.get(
            "auto_rejection_reasons",
            [],
        ),
        "manual_recovery": True,
        "clip_path": clip_rel,
        "keyframe_path": keyframe_rel,
        "time_verified": False,
        "review_status": "needs_review",
    }


def matching_quality_row(
    row: dict[str, str],
    video_id: str,
    start_time: float,
    end_time: float,
) -> bool:
    try:
        return (
            row.get("video_id") == video_id
            and abs(float(row.get("candidate_start", "nan")) - start_time)
            < 0.002
            and abs(float(row.get("candidate_end", "nan")) - end_time)
            < 0.002
        )
    except ValueError:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "기존 전처리 결과를 삭제하지 않고 계절 오판 후보만 "
            "기존 시간으로 선택 복구"
        )
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="K-contents 프로젝트 루트",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="파일을 수정하지 않고 복구 계획만 출력",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    output_root = project_root / "preprocessed_output"
    manifest_path = project_root / "preprocessing_manifest.json"
    preprocessed_path = output_root / "preprocessed_segments.json"
    rejected_path = output_root / "rejected_candidates.json"
    quality_path = output_root / "quality_report.csv"

    required = [
        manifest_path,
        preprocessed_path,
        rejected_path,
        quality_path,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "필수 파일이 없습니다:\n- " + "\n- ".join(missing)
        )

    source_dir = first_existing(
        output_root,
        ["original_videos", "raw_videos"],
    )
    processed_dir = first_existing(
        output_root,
        ["preprocessed_video", "clips"],
    )
    keyframes_root = output_root / "keyframes"
    contact_root = output_root / "contact_sheets"

    if not source_dir.exists():
        raise FileNotFoundError(
            f"원본 영상 폴더가 없습니다: {source_dir}"
        )

    manifest = load_json(manifest_path)
    results = load_json(preprocessed_path)

    with quality_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)
        fieldnames = list(reader.fieldnames or [])
        quality_rows = list(reader)

    records = manifest.get("records", [])
    record_by_source = {
        str(record.get("source_segment_id", "")): record
        for record in records
    }
    result_by_video = {
        str(result.get("video_id", "")): result
        for result in results
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = output_root / f"manual_season_backup_{timestamp}"

    log_rows: list[dict[str, Any]] = []
    total_recovered = 0

    for source_id, verified_season in SEASON_BY_SOURCE.items():
        record = record_by_source.get(source_id)
        if record is None:
            log_rows.append({
                "source_segment_id": source_id,
                "video_id": "",
                "verified_season": verified_season,
                "status": "manifest_id_not_found",
                "recovered_count": 0,
                "memo": "manifest에서 ID를 찾지 못함",
            })
            continue

        video_id = str(record.get("video_id", ""))
        result = result_by_video.get(video_id)
        if result is None:
            log_rows.append({
                "source_segment_id": source_id,
                "video_id": video_id,
                "verified_season": verified_season,
                "status": "result_not_found",
                "recovered_count": 0,
                "memo": "preprocessed_segments에서 video_id를 찾지 못함",
            })
            continue

        review_note = (
            f"{source_id} 사용자 영상 검수 결과 "
            f"{verified_season}으로 확정."
        )

        record["season"] = [verified_season]
        record["expected_seasons"] = [verified_season]
        record["verified_season"] = verified_season
        record["season_verified"] = True
        record["season_review_status"] = "reviewed"
        record["season_match_required"] = False
        record["season_review_note"] = review_note

        result["expected_seasons"] = [verified_season]
        result["verified_season"] = verified_season
        result["season_verified"] = True
        result["season_review_status"] = "reviewed"
        result["season_match_required"] = False
        result["manual_season_override"] = True
        result["season_review_note"] = review_note

        existing_segments = result.get("segments", [])
        for segment in existing_segments:
            if segment.get("source_segment_id") == source_id:
                update_manual_season(
                    segment,
                    verified_season,
                    review_note,
                    rejected=False,
                )

        candidates = [
            candidate
            for candidate in result.get(
                "rejected_candidates",
                [],
            )
            if candidate.get("source_segment_id") == source_id
        ]

        # 선택 여부와 관계없이 해당 영상의 계절 관련 CSV 값도
        # 수동 검수 계절로 통일합니다. 자동 판정 이력은 JSON의
        # auto_* 필드에 보존됩니다.
        for segment in existing_segments:
            if segment.get("source_segment_id") != source_id:
                continue
            for row in quality_rows:
                if matching_quality_row(
                    row,
                    video_id,
                    float(segment.get("start_time", 0.0)),
                    float(segment.get("end_time", 0.0)),
                ):
                    row["accepted"] = "True"
                    row["expected_season"] = verified_season
                    row["season_score"] = str(
                        segment.get("season_score", "")
                    )
                    row["detected_season"] = verified_season
                    row["rejection_reasons"] = ""

        eligible: list[dict[str, Any]] = []
        quality_blocked: list[dict[str, Any]] = []

        for candidate in candidates:
            remaining = update_manual_season(
                candidate,
                verified_season,
                review_note,
                rejected=True,
            )

            for row in quality_rows:
                if matching_quality_row(
                    row,
                    video_id,
                    float(candidate.get("start_time", 0.0)),
                    float(candidate.get("end_time", 0.0)),
                ):
                    row["expected_season"] = verified_season
                    row["season_score"] = str(
                        candidate.get("season_score", "")
                    )
                    row["detected_season"] = verified_season
                    row["rejection_reasons"] = " / ".join(remaining)

            if remaining:
                candidate["manual_recovery_status"] = (
                    "계절 외 품질 사유로 제외 유지"
                )
                quality_blocked.append(candidate)
            else:
                candidate["manual_recovery_status"] = (
                    "계절 오판 복구 가능"
                )
                eligible.append(candidate)

        max_selected = int(
            record.get(
                "max_selected_scenes",
                2 if record.get("source_type") == "쇼츠" else 3,
            )
        )
        remaining_slots = max(
            0,
            max_selected - len(existing_segments),
        )

        eligible.sort(
            key=lambda item: float(item.get("total_score", 0.0)),
            reverse=True,
        )
        chosen = eligible[:remaining_slots]
        not_chosen = eligible[remaining_slots:]

        for candidate in not_chosen:
            candidate["accepted"] = False
            candidate["rejection_reasons"] = [
                "영상당 최대 선택 개수 초과(기존 선택 장면 유지)"
            ]
            candidate["manual_recovery_status"] = (
                "선택 개수 제한으로 제외 유지"
            )

        print(
            f"{source_id} | {video_id} | {verified_season} | "
            f"기존 선택 {len(existing_segments)} | "
            f"복구 가능 {len(eligible)} | 실제 복구 {len(chosen)} | "
            f"품질 제외 유지 {len(quality_blocked)}"
        )

        recovered_items: list[tuple[Path, str]] = []

        if chosen and not args.dry_run:
            source_video = find_source_video(
                source_dir,
                result,
            )

            video_folder = safe_name(video_id)
            clip_dir = processed_dir / video_folder
            frame_dir = keyframes_root / video_folder

            for candidate in chosen:
                segment_id = next_segment_id(
                    video_id,
                    existing_segments,
                )
                clip_path = clip_dir / f"{segment_id}.mp4"
                frame_path = frame_dir / f"{segment_id}.jpg"

                start_time = float(candidate["start_time"])
                end_time = float(candidate["end_time"])
                representative_time = float(
                    candidate["representative_frame_time"]
                )

                extract_clip(
                    source_video,
                    clip_path,
                    start_time,
                    end_time,
                )
                extract_keyframe(
                    source_video,
                    frame_path,
                    representative_time,
                )

                segment = build_segment(
                    record=record,
                    video_result=result,
                    candidate=candidate,
                    segment_id=segment_id,
                    verified_season=verified_season,
                    clip_rel=clip_path.relative_to(
                        output_root
                    ).as_posix(),
                    keyframe_rel=frame_path.relative_to(
                        output_root
                    ).as_posix(),
                )
                existing_segments.append(segment)
                candidate["accepted"] = True
                candidate["manual_recovery_status"] = "복구 완료"

                recovered_items.append(
                    (
                        frame_path,
                        (
                            f"{segment_id} "
                            f"{start_time:.2f}-{end_time:.2f}s "
                            f"{verified_season}"
                        ),
                    )
                )

                for row in quality_rows:
                    if matching_quality_row(
                        row,
                        video_id,
                        start_time,
                        end_time,
                    ):
                        row["accepted"] = "True"
                        row["expected_season"] = verified_season
                        row["season_score"] = str(
                            segment.get("season_score", "")
                        )
                        row["detected_season"] = verified_season
                        row["rejection_reasons"] = ""

                total_recovered += 1

            result["segments"] = sorted(
                existing_segments,
                key=lambda item: float(item.get("start_time", 0.0)),
            )

            chosen_ids = {id(candidate) for candidate in chosen}
            result["rejected_candidates"] = [
                candidate
                for candidate in result.get(
                    "rejected_candidates",
                    [],
                )
                if id(candidate) not in chosen_ids
            ]

            result["accepted_scene_count"] = len(
                result["segments"]
            )
            result["rejected_scene_count"] = len(
                result["rejected_candidates"]
            )

            sheet_path = (
                contact_root
                / f"{safe_name(video_id)}_MANUAL_RECOVERED.jpg"
            )
            make_contact_sheet(recovered_items, sheet_path)
            result["manual_recovery_contact_sheet"] = (
                sheet_path.relative_to(output_root).as_posix()
            )

        log_rows.append({
            "source_segment_id": source_id,
            "video_id": video_id,
            "verified_season": verified_season,
            "status": (
                "dry_run"
                if args.dry_run
                else (
                    "recovered"
                    if chosen
                    else "metadata_only"
                )
            ),
            "existing_selected_count": len(existing_segments),
            "eligible_season_only_count": len(eligible),
            "recovered_count": len(chosen),
            "quality_blocked_count": len(quality_blocked),
            "selection_limit_blocked_count": len(not_chosen),
            "memo": (
                "기존 선택 영상·이미지는 삭제하지 않음. "
                "기존 rejected 후보 시간만 사용함."
            ),
        })

    if args.dry_run:
        print("DRY RUN: 실제 파일은 변경하지 않았습니다.")
        return

    backup_dir.mkdir(parents=True, exist_ok=True)
    for path in required:
        shutil.copy2(path, backup_dir / path.name)

    save_json(manifest_path, manifest)
    save_json(preprocessed_path, results)

    rejected_value = [
        {
            "video_id": result.get("video_id"),
            "youtube_id": result.get("youtube_id"),
            "rejected_candidates": result.get(
                "rejected_candidates",
                [],
            ),
        }
        for result in results
    ]
    save_json(rejected_path, rejected_value)

    with quality_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(quality_rows)

    log_path = output_root / "manual_season_recovery_log.csv"
    log_fields = [
        "source_segment_id",
        "video_id",
        "verified_season",
        "status",
        "existing_selected_count",
        "eligible_season_only_count",
        "recovered_count",
        "quality_blocked_count",
        "selection_limit_blocked_count",
        "memo",
    ]
    with log_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=log_fields,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(log_rows)

    print("")
    print("계절 오판 선택 복구 완료")
    print(f"- 추가 생성한 클립·대표 이미지: {total_recovered}개")
    print(f"- 기존 결과 백업: {backup_dir}")
    print(f"- 복구 로그: {log_path}")
    print("- 기존 전처리 영상과 이미지는 삭제하지 않았습니다.")


if __name__ == "__main__":
    main()
