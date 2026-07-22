from __future__ import annotations

import json
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "input" / "videos"
VIDEO_CONFIG = ROOT / "config" / "videos.json"


def get_video_info(path: Path) -> dict:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"영상을 열 수 없습니다: {path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = frame_count / fps if fps else 0.0
    cap.release()

    return {
        "duration_sec": round(duration, 3),
        "fps": round(fps, 3),
        "frame_count": int(frame_count),
        "width": width,
        "height": height,
    }


def main() -> None:
    videos = json.loads(VIDEO_CONFIG.read_text(encoding="utf-8"))
    print("\n[영상 파일 검사]\n")

    has_error = False
    for item in videos:
        path = VIDEO_DIR / item["filename"]
        if not path.exists():
            has_error = True
            print(f"[없음] {item['video_id']} -> {path.name}")
            print(f"       원래 파일명: {item['original_filename']}")
            continue

        try:
            info = get_video_info(path)
            print(
                f"[정상] {item['video_id']} | {path.name} | "
                f"{info['duration_sec']}초 | {info['width']}x{info['height']} | "
                f"{info['fps']}fps"
            )
        except RuntimeError as error:
            has_error = True
            print(f"[오류] {error}")

    if has_error:
        raise SystemExit("\n영상 파일명을 확인한 뒤 다시 실행하세요.")

    print("\n모든 영상 파일이 정상입니다.")


if __name__ == "__main__":
    main()
