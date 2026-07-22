from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2

ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "input" / "videos"
VIDEO_CONFIG = ROOT / "config" / "videos.json"


def get_video_info(path: Path) -> dict[str, Any]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"영상을 열 수 없습니다: {path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    if fps <= 0 or frame_count <= 0:
        raise RuntimeError(f"영상 정보를 확인할 수 없습니다: {path}")

    duration_time = frame_count / fps

    return {
        "duration_time": round(duration_time, 3),
        "fps": round(fps, 3),
        "frame_count": int(frame_count),
        "width": width,
        "height": height,
    }


def load_video_config() -> list[dict[str, Any]]:
    if not VIDEO_CONFIG.exists():
        raise FileNotFoundError(f"영상 설정 파일이 없습니다: {VIDEO_CONFIG}")

    try:
        videos = json.loads(VIDEO_CONFIG.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"videos.json 문법 오류: {error}") from error

    if not isinstance(videos, list) or not videos:
        raise ValueError("videos.json의 최상위 값은 비어 있지 않은 배열이어야 합니다.")
    if not all(isinstance(item, dict) for item in videos):
        raise ValueError("videos.json의 각 항목은 JSON 객체여야 합니다.")

    return videos


def main() -> None:
    videos = load_video_config()
    print("\n[영상 파일 검사]\n")

    has_error = False

    for item in videos:
        video_id = str(item.get("video_id", "")).strip()
        filename = str(item.get("filename", "")).strip()
        original_filename = str(item.get("original_filename", "")).strip()

        if not video_id or not filename:
            has_error = True
            print(f"[설정 오류] video_id 또는 filename이 비어 있습니다: {item}")
            continue

        path = VIDEO_DIR / filename

        if not path.exists():
            has_error = True
            print(f"[없음] {video_id} -> {path.name}")
            if original_filename:
                print(f"       원래 파일명: {original_filename}")
            continue

        try:
            info = get_video_info(path)
            print(
                f"[정상] {video_id} | {path.name} | "
                f"{info['duration_time']}초 | "
                f"{info['width']}x{info['height']} | "
                f"{info['fps']}fps"
            )
        except RuntimeError as error:
            has_error = True
            print(f"[오류] {error}")

    if has_error:
        raise SystemExit("\n영상 파일명과 videos.json을 확인한 뒤 다시 실행하세요.")

    print("\n모든 영상 파일이 정상입니다.")


if __name__ == "__main__":
    main()
