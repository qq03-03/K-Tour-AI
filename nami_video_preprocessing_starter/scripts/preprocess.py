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


def get_duration_sec(path: Path) -> float:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"영상을 열 수 없습니다: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    return frame_count / fps if fps else 0.0


def sec_to_timecode(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    hours, remain = divmod(total_ms, 3_600_000)
    minutes, remain = divmod(remain, 60_000)
    secs, millis = divmod(remain, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def run_command(command: list[str]) -> None:
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "FFmpeg 실행 실패")


def cut_segment(
    ffmpeg_exe: str,
    source: Path,
    output: Path,
    start_sec: float,
    end_sec: float,
) -> None:
    duration = end_sec - start_sec
    command = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(source),
        "-ss",
        str(start_sec),
        "-t",
        str(duration),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output),
    ]
    run_command(command)


def extract_frame(
    ffmpeg_exe: str,
    source: Path,
    output: Path,
    frame_sec: float,
) -> None:
    command = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(source),
        "-ss",
        str(frame_sec),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output),
    ]
    run_command(command)


def validate_item(item: dict[str, Any], source_duration: float) -> None:
    required = [
        "segment_id",
        "video_id",
        "source_filename",
        "start_sec",
        "end_sec",
    ]
    missing = [key for key in required if key not in item]
    if missing:
        raise ValueError(f"필수 필드 누락: {missing}")

    start = float(item["start_sec"])
    end = float(item["end_sec"])
    frame = float(item.get("representative_frame_sec", (start + end) / 2))

    if start < 0:
        raise ValueError("start_sec는 0 이상이어야 합니다.")
    if end <= start:
        raise ValueError("end_sec는 start_sec보다 커야 합니다.")
    if end > source_duration + 0.1:
        raise ValueError(
            f"end_sec({end})가 영상 길이({source_duration:.3f})를 초과합니다."
        )
    if not start <= frame <= end:
        raise ValueError("representative_frame_sec는 구간 안에 있어야 합니다.")


def process(config_path: Path) -> None:
    SEGMENT_DIR.mkdir(parents=True, exist_ok=True)
    FRAME_DIR.mkdir(parents=True, exist_ok=True)

    items = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(items, list):
        raise ValueError("구간 설정 JSON의 최상위 값은 배열이어야 합니다.")

    segment_ids = [item.get("segment_id") for item in items]
    if len(segment_ids) != len(set(segment_ids)):
        raise ValueError("중복된 segment_id가 있습니다.")

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    results: list[dict[str, Any]] = []

    for index, item in enumerate(items, start=1):
        segment_id = item["segment_id"]
        source_path = VIDEO_DIR / item["source_filename"]
        if not source_path.exists():
            raise FileNotFoundError(f"원본 영상이 없습니다: {source_path}")

        source_duration = get_duration_sec(source_path)
        validate_item(item, source_duration)

        start = float(item["start_sec"])
        end = float(item["end_sec"])
        frame_sec = float(item.get("representative_frame_sec", (start + end) / 2))

        segment_path = SEGMENT_DIR / f"{segment_id}.mp4"
        frame_path = FRAME_DIR / f"{segment_id}.jpg"

        print(f"[{index}/{len(items)}] {segment_id} 처리 중...")
        cut_segment(ffmpeg_exe, source_path, segment_path, start, end)
        extract_frame(ffmpeg_exe, source_path, frame_path, frame_sec)

        results.append(
            {
                "segment_id": segment_id,
                "video_id": item["video_id"],
                "start_sec": start,
                "end_sec": end,
                "start_time": sec_to_timecode(start),
                "end_time": sec_to_timecode(end),
                "duration_sec": round(end - start, 3),
                "source_video_path": source_path.relative_to(ROOT).as_posix(),
                "segment_video_path": segment_path.relative_to(ROOT).as_posix(),
                "representative_frame_path": frame_path.relative_to(ROOT).as_posix(),
                "representative_frame_sec": frame_sec,
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
    RESULT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n전처리 완료")
    print(f"구간 영상: {SEGMENT_DIR}")
    print(f"대표 프레임: {FRAME_DIR}")
    print(f"결과 JSON: {RESULT_PATH}")
    print("\n출력 MP4를 확인한 뒤 JSON의 time_verified/review_status를 수정하세요.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="남이섬 영상 구간 및 대표 프레임 추출")
    parser.add_argument(
        "--config",
        default="config/segments_sample.json",
        help="프로젝트 루트 기준 구간 설정 JSON 경로",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = ROOT / args.config
    if not config_path.exists():
        raise FileNotFoundError(f"설정 파일이 없습니다: {config_path}")
    process(config_path)


if __name__ == "__main__":
    main()
