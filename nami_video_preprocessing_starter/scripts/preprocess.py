from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "input" / "videos"
SEGMENT_DIR = ROOT / "output" / "segments"
FRAME_DIR = ROOT / "output" / "frames"
RESULT_PATH = ROOT / "output" / "preprocessing_results.json"


def get_duration_time(path: Path) -> float:
    """영상 전체 길이를 초 단위 실수로 반환합니다."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"영상을 열 수 없습니다: {path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()

    if fps <= 0 or frame_count <= 0:
        raise RuntimeError(f"영상 길이를 확인할 수 없습니다: {path}")

    return frame_count / fps


def sec_to_timecode(seconds: float) -> str:
    """초 단위 값을 HH:MM:SS.mmm 형식으로 변환합니다."""
    total_ms = int(round(seconds * 1000))
    hours, remain = divmod(total_ms, 3_600_000)
    minutes, remain = divmod(remain, 60_000)
    secs, millis = divmod(remain, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def run_command(command: list[str]) -> None:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "FFmpeg 실행 실패")


def cut_segment(
    ffmpeg_exe: str,
    source: Path,
    output: Path,
    start_time: float,
    end_time: float,
) -> None:
    duration_time = end_time - start_time

    command = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(source),
        "-ss",
        str(start_time),
        "-t",
        str(duration_time),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        "-sn",
        "-dn",
        str(output),
    ]
    run_command(command)


def extract_frame(
    ffmpeg_exe: str,
    source: Path,
    output: Path,
    representative_frame_time: float,
) -> None:
    command = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(source),
        "-ss",
        str(representative_frame_time),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output),
    ]
    run_command(command)


def validate_item(
    item: dict[str, Any],
    source_duration_time: float,
) -> None:
    required = [
        "segment_id",
        "video_id",
        "source_filename",
        "start_time",
        "end_time",
    ]
    missing = [key for key in required if key not in item]
    if missing:
        raise ValueError(f"필수 필드 누락: {missing}")

    if not str(item["segment_id"]).strip():
        raise ValueError("segment_id가 비어 있습니다.")
    if not str(item["video_id"]).strip():
        raise ValueError("video_id가 비어 있습니다.")
    if not str(item["source_filename"]).strip():
        raise ValueError("source_filename이 비어 있습니다.")

    try:
        start_time = float(item["start_time"])
        end_time = float(item["end_time"])
        representative_frame_time = float(
            item.get(
                "representative_frame_time",
                (start_time + end_time) / 2,
            )
        )
    except (TypeError, ValueError) as error:
        raise ValueError(
            "start_time, end_time, representative_frame_time은 숫자여야 합니다."
        ) from error

    if start_time < 0:
        raise ValueError("start_time은 0 이상이어야 합니다.")
    if end_time <= start_time:
        raise ValueError("end_time은 start_time보다 커야 합니다.")
    if end_time > source_duration_time + 0.1:
        raise ValueError(
            f"end_time({end_time})가 영상 길이"
            f"({source_duration_time:.3f})를 초과합니다."
        )

    # 구간의 끝 시각은 다음 장면 경계일 수 있으므로 대표 프레임은 끝보다 작아야 합니다.
    if not start_time <= representative_frame_time < end_time:
        raise ValueError(
            "representative_frame_time은 "
            "start_time 이상, end_time 미만이어야 합니다."
        )


def clean_output_files() -> None:
    """이전 실행에서 생성된 MP4/JPG/결과 JSON을 삭제합니다."""
    for directory, pattern in [
        (SEGMENT_DIR, "*.mp4"),
        (FRAME_DIR, "*.jpg"),
    ]:
        if directory.exists():
            for path in directory.glob(pattern):
                path.unlink()

    if RESULT_PATH.exists():
        RESULT_PATH.unlink()


def warn_time_boundaries(items: list[dict[str, Any]]) -> None:
    """같은 영상의 구간 사이에 빈 시간이나 겹침이 있으면 경고합니다."""
    by_video: dict[str, list[dict[str, Any]]] = {}

    for item in items:
        by_video.setdefault(str(item["video_id"]), []).append(item)

    for video_id, video_items in by_video.items():
        ordered = sorted(video_items, key=lambda x: float(x["start_time"]))

        for previous, current in zip(ordered, ordered[1:]):
            previous_end = float(previous["end_time"])
            current_start = float(current["start_time"])
            difference = round(current_start - previous_end, 3)

            if abs(difference) <= 0.01:
                continue
            if difference > 0:
                print(
                    f"[경고] {video_id}: "
                    f"{previous['segment_id']}와 {current['segment_id']} 사이에 "
                    f"{difference}초의 빈 구간이 있습니다."
                )
            else:
                print(
                    f"[경고] {video_id}: "
                    f"{previous['segment_id']}와 {current['segment_id']}가 "
                    f"{abs(difference)}초 겹칩니다."
                )


def process(config_path: Path, clean: bool = False) -> None:
    SEGMENT_DIR.mkdir(parents=True, exist_ok=True)
    FRAME_DIR.mkdir(parents=True, exist_ok=True)

    try:
        items = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(
            f"구간 설정 JSON 문법 오류: {error}"
        ) from error

    if not isinstance(items, list):
        raise ValueError("구간 설정 JSON의 최상위 값은 배열이어야 합니다.")
    if not items:
        raise ValueError("구간 설정 JSON에 구간 데이터가 없습니다.")
    if not all(isinstance(item, dict) for item in items):
        raise ValueError("모든 구간 항목은 JSON 객체여야 합니다.")

    segment_ids = [str(item.get("segment_id", "")).strip() for item in items]
    if "" in segment_ids:
        raise ValueError("segment_id가 없는 구간이 있습니다.")
    if len(segment_ids) != len(set(segment_ids)):
        raise ValueError("중복된 segment_id가 있습니다.")

    if clean:
        clean_output_files()

    warn_time_boundaries(items)

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    results: list[dict[str, Any]] = []

    for index, item in enumerate(items, start=1):
        segment_id = str(item["segment_id"])
        source_path = VIDEO_DIR / str(item["source_filename"])

        if not source_path.exists():
            raise FileNotFoundError(f"원본 영상이 없습니다: {source_path}")

        source_duration_time = get_duration_time(source_path)
        validate_item(item, source_duration_time)

        start_time = float(item["start_time"])
        end_time = float(item["end_time"])
        representative_frame_time = float(
            item.get(
                "representative_frame_time",
                (start_time + end_time) / 2,
            )
        )

        segment_path = SEGMENT_DIR / f"{segment_id}.mp4"
        frame_path = FRAME_DIR / f"{segment_id}.jpg"

        print(f"[{index}/{len(items)}] {segment_id} 처리 중...")

        cut_segment(
            ffmpeg_exe,
            source_path,
            segment_path,
            start_time,
            end_time,
        )
        extract_frame(
            ffmpeg_exe,
            source_path,
            frame_path,
            representative_frame_time,
        )

        results.append(
            {
                "segment_id": segment_id,
                "video_id": item["video_id"],
                "start_time": start_time,
                "end_time": end_time,
                "start_timecode": sec_to_timecode(start_time),
                "end_timecode": sec_to_timecode(end_time),
                "duration_time": round(end_time - start_time, 3),
                "source_duration_time": round(source_duration_time, 3),
                "source_video_path": source_path.relative_to(ROOT).as_posix(),
                "segment_video_path": segment_path.relative_to(ROOT).as_posix(),
                "representative_frame_path": frame_path.relative_to(ROOT).as_posix(),
                "representative_frame_time": representative_frame_time,
                "spot_name": item.get("spot_name", ""),
                "description": item.get("description", ""),
                "time_verified": False,
                "review_status": "needs_review",
                "notes": "출력 영상을 직접 재생한 후 시간 경계를 검토하세요.",
            }
        )

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "config_file": config_path.relative_to(ROOT).as_posix(),
        "segment_count": len(results),
        "segments": results,
    }

    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n전처리 완료")
    print(f"생성 구간 수: {len(results)}")
    print(f"구간 영상: {SEGMENT_DIR}")
    print(f"대표 프레임: {FRAME_DIR}")
    print(f"결과 JSON: {RESULT_PATH}")
    print(
        "\n출력 MP4와 JPG를 확인한 뒤 "
        "JSON의 time_verified/review_status를 수정하세요."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="남이섬 영상 구간 및 대표 프레임 추출"
    )
    parser.add_argument(
        "--config",
        default="config/segments_all_9_template.json",
        help="프로젝트 루트 기준 구간 설정 JSON 경로",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="실행 전에 기존 구간 영상, 대표 프레임, 결과 JSON을 삭제",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = ROOT / args.config

    if not config_path.exists():
        raise FileNotFoundError(f"설정 파일이 없습니다: {config_path}")

    process(config_path, clean=args.clean)


if __name__ == "__main__":
    main()
