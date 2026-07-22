from pathlib import Path
import subprocess
import sys

import imageio_ffmpeg


# 프로젝트 최상위 폴더
PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_DIR = PROJECT_ROOT / "input" / "videos"
OUTPUT_DIR = PROJECT_ROOT / "output" / "converted_videos"

# 변환할 영상 파일
TARGET_FILES = [
    "VID_NAMI_02.mp4",
    "VID_NAMI_03.mp4",
]


def convert_video(input_path: Path, output_path: Path) -> None:
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

    command = [
        ffmpeg_path,
        "-y",
        "-i",
        str(input_path),

        # 영상 코덱을 범용 H.264로 변환
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",

        # Windows, 웹, 모바일 호환성 향상
        "-pix_fmt",
        "yuv420p",

        # 오디오를 AAC로 변환
        "-c:a",
        "aac",
        "-b:a",
        "192k",

        "-movflags",
        "+faststart",

        str(output_path),
    ]

    print(f"\n[변환 시작] {input_path.name}")

    result = subprocess.run(
        command,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"영상 변환에 실패했습니다: {input_path.name}"
        )

    print(f"[변환 완료] {output_path}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for filename in TARGET_FILES:
        input_path = INPUT_DIR / filename
        output_path = OUTPUT_DIR / filename

        if not input_path.exists():
            print(f"[파일 없음] {input_path}")
            continue

        try:
            convert_video(input_path, output_path)
        except Exception as error:
            print(f"[오류] {error}", file=sys.stderr)

    print("\n모든 변환 작업이 끝났습니다.")


if __name__ == "__main__":
    main()