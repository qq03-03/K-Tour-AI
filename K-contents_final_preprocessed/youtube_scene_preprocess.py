from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np


VIDEO_EXTENSIONS = (".mp4", ".mkv", ".webm", ".mov", ".m4v")
SEASONS = ("봄", "여름", "가을", "겨울")


@dataclass
class VideoInfo:
    duration: float
    fps: float
    width: int
    height: int


@dataclass
class FrameMetrics:
    time_sec: float
    sharpness: float
    laplacian_variance: float
    tenengrad: float
    brightness: float
    contrast: float
    saturation: float
    dark_ratio: float
    overexposed_ratio: float
    green_ratio: float
    yellow_ratio: float
    pink_ratio: float
    orange_red_ratio: float
    brown_ratio: float
    blue_ratio: float
    white_ratio: float
    white_upper_ratio: float
    white_lower_ratio: float
    white_largest_component_ratio: float
    white_edge_ratio: float
    low_saturation_ratio: float
    edge_density: float


@dataclass
class SceneCandidate:
    start_time: float
    end_time: float
    representative_frame_time: float
    representative_histogram: list[float]
    total_score: float
    scene_change_confidence: float
    sharpness_score: float
    season_score: float
    expected_season: str
    overall_detected_season: str
    quality_components: dict[str, float]
    season_scores: dict[str, float]
    source_segment_id: str
    source_description: str
    accepted: bool
    rejection_reasons: list[str]


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"JSON 문법 오류: {path}\n{error}") from error


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def safe_name(value: str) -> str:
    result = "".join(
        char if char.isalnum() or char in "-_" else "_"
        for char in str(value)
    ).strip("_")
    return result or "video"


def preferred_existing_dir(
    root: Path,
    names: tuple[str, ...],
) -> Path:
    for name in names:
        candidate = root / name
        if candidate.exists():
            return candidate
    return root / names[0]


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def median(values: list[float], default: float = 0.0) -> float:
    if not values:
        return default
    return float(np.median(np.asarray(values, dtype=np.float32)))


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
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
        raise RuntimeError(
            f"명령 실행 실패({result.returncode})\n{result.stdout[-5000:]}"
        )
    return result


def get_ffmpeg_executable() -> str:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    try:
        import imageio_ffmpeg
        bundled_ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled_ffmpeg and Path(bundled_ffmpeg).exists():
            return str(bundled_ffmpeg)
    except Exception:
        pass

    raise RuntimeError(
        "FFmpeg를 찾을 수 없습니다. .\\실행.ps1 setup 을 먼저 실행하세요."
    )


def check_dependencies() -> None:
    get_ffmpeg_executable()

    result = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--version"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "yt-dlp가 설치되지 않았습니다.\n"
            f"{sys.executable} -m pip install -U yt-dlp"
        )


def find_downloaded_video(raw_dir: Path, base_name: str) -> Path | None:
    candidates = [
        path
        for path in raw_dir.glob(f"{base_name}.*")
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    ]
    return max(candidates, key=lambda path: path.stat().st_size) if candidates else None


def download_video(
    record: dict[str, Any],
    raw_dir: Path,
    cookies_from_browser: str | None,
) -> Path:
    video_id = safe_name(record.get("video_id", ""))
    youtube_id = safe_name(record.get("youtube_id", ""))
    base_name = f"{video_id}_{youtube_id}"

    existing = find_downloaded_video(raw_dir, base_name)
    if existing:
        print(f"기존 원본 사용: {existing}")
        return existing

    source_url = str(record.get("source_url", "")).strip()
    if not source_url:
        raise ValueError(f"source_url이 없습니다: {record.get('youtube_id')}")

    raw_dir.mkdir(parents=True, exist_ok=True)
    output_template = raw_dir / f"{base_name}.%(ext)s"

    command = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--no-playlist",
        "--no-overwrites",
        "--merge-output-format",
        "mp4",
        "-f",
        "bv*[height<=1080]+ba/b[height<=1080]/b",
        "-o",
        str(output_template),
    ]
    if cookies_from_browser:
        command.extend(["--cookies-from-browser", cookies_from_browser])
    command.append(source_url)
    run_command(command)

    downloaded = find_downloaded_video(raw_dir, base_name)
    if downloaded is None:
        raise RuntimeError(f"다운로드 결과 파일을 찾지 못했습니다: {base_name}")
    return downloaded


def probe_video(video_path: Path) -> VideoInfo:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"영상을 열 수 없습니다: {video_path}")

    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    capture.release()

    if not math.isfinite(fps) or fps <= 0:
        fps = 30.0
    duration = frame_count / fps if frame_count > 0 else 0.0
    if duration <= 0:
        raise RuntimeError(f"영상 길이를 확인할 수 없습니다: {video_path}")

    return VideoInfo(duration=duration, fps=fps, width=width, height=height)


def read_frame(video_path: Path, time_sec: float) -> np.ndarray | None:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return None
    capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, time_sec) * 1000.0)
    ok, frame = capture.read()
    capture.release()
    return frame if ok else None


def resized_for_analysis(frame: np.ndarray, target_width: int = 640) -> np.ndarray:
    height, width = frame.shape[:2]
    if width <= target_width:
        return frame
    scale = target_width / width
    return cv2.resize(frame, (target_width, max(1, int(height * scale))))


def normalized_histogram(frame: np.ndarray) -> np.ndarray:
    small = cv2.resize(frame, (160, 90))
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [24, 16], [0, 180, 0, 256])
    cv2.normalize(hist, hist)
    return hist.flatten()


def frame_feature(frame: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    small = cv2.resize(frame, (160, 90))
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 70, 150)
    hist = cv2.calcHist([hsv], [0, 1], None, [24, 16], [0, 180, 0, 256])
    cv2.normalize(hist, hist)
    return hist, gray, edges


def feature_difference(
    previous: tuple[np.ndarray, np.ndarray, np.ndarray],
    current: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> float:
    prev_hist, prev_gray, prev_edges = previous
    curr_hist, curr_gray, curr_edges = current

    histogram_difference = float(
        cv2.compareHist(prev_hist, curr_hist, cv2.HISTCMP_BHATTACHARYYA)
    )
    gray_difference = float(np.mean(cv2.absdiff(prev_gray, curr_gray)) / 255.0)
    edge_difference = float(np.mean(cv2.absdiff(prev_edges, curr_edges)) / 255.0)

    return (
        0.58 * histogram_difference
        + 0.24 * gray_difference
        + 0.18 * edge_difference
    )


def detect_scene_boundaries(
    video_path: Path,
    range_start: float,
    range_end: float,
    sample_step: float,
    base_threshold: float,
    mad_multiplier: float,
    minimum_cut_gap: float,
) -> tuple[list[float], dict[float, float], float]:
    sample_times: list[float] = []
    differences: list[float] = []
    previous_feature = None
    time_sec = range_start

    while time_sec <= range_end + 1e-6:
        frame = read_frame(video_path, time_sec)
        if frame is not None:
            current_feature = frame_feature(frame)
            if previous_feature is not None:
                sample_times.append(time_sec)
                differences.append(
                    feature_difference(previous_feature, current_feature)
                )
            previous_feature = current_feature
        time_sec += sample_step

    if len(differences) < 3:
        return [range_start, range_end], {}, base_threshold

    values = np.asarray(differences, dtype=np.float32)
    med = float(np.median(values))
    mad = float(np.median(np.abs(values - med)))
    adaptive = med + mad_multiplier * max(mad, 0.008)
    threshold = max(base_threshold, min(0.78, adaptive))

    peak_candidates: list[tuple[float, float]] = []
    for index in range(1, len(differences) - 1):
        value = differences[index]
        if (
            value >= threshold
            and value >= differences[index - 1]
            and value >= differences[index + 1]
        ):
            confidence = clamp((value - threshold) / max(0.10, 1.0 - threshold) + 0.55)
            peak_candidates.append((sample_times[index], confidence))

    boundaries = [range_start]
    boundary_confidence: dict[float, float] = {}

    for time_sec, confidence in sorted(
        peak_candidates,
        key=lambda item: item[1],
        reverse=True,
    ):
        if all(abs(time_sec - existing) >= minimum_cut_gap for existing in boundaries):
            boundaries.append(time_sec)
            boundary_confidence[round(time_sec, 3)] = round(confidence, 4)

    boundaries = sorted(boundaries)
    if range_end - boundaries[-1] < 0.8 and len(boundaries) > 1:
        removed = boundaries.pop()
        boundary_confidence.pop(round(removed, 3), None)
    boundaries.append(range_end)

    return boundaries, boundary_confidence, threshold


def calculate_frame_metrics(frame: np.ndarray, time_sec: float) -> FrameMetrics:
    frame = resized_for_analysis(frame)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    laplacian_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    tenengrad = float(np.mean(gx * gx + gy * gy))

    lap_score = clamp(
        (math.log1p(laplacian_variance) - math.log1p(35.0))
        / (math.log1p(1200.0) - math.log1p(35.0))
    )
    tenengrad_score = clamp(
        (math.log1p(tenengrad) - math.log1p(180.0))
        / (math.log1p(8000.0) - math.log1p(180.0))
    )
    sharpness = 0.62 * lap_score + 0.38 * tenengrad_score

    h = hsv[:, :, 0]
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]

    total = float(h.size)
    upper_end = max(1, int(h.shape[0] * 0.72))
    lower_start = int(h.shape[0] * 0.40)
    upper_s = s[:upper_end, :]
    upper_v = v[:upper_end, :]
    lower_s = s[lower_start:, :]
    lower_v = v[lower_start:, :]

    def ratio(mask: np.ndarray) -> float:
        return float(np.count_nonzero(mask) / max(1.0, total))

    green = ratio((h >= 30) & (h <= 90) & (s >= 55) & (v >= 45))
    yellow = ratio((h >= 18) & (h <= 35) & (s >= 60) & (v >= 80))
    pink = ratio(
        (((h >= 145) & (h <= 179)) | ((h >= 0) & (h <= 8)))
        & (s >= 25)
        & (s <= 175)
        & (v >= 125)
    )
    orange_red = ratio(
        (((h >= 0) & (h <= 20)) | (h >= 165))
        & (s >= 55)
        & (v >= 45)
    )
    brown = ratio(
        (h >= 5) & (h <= 28)
        & (s >= 40) & (s <= 210)
        & (v >= 35) & (v <= 185)
    )
    blue = ratio((h >= 90) & (h <= 132) & (s >= 48) & (v >= 55))

    # 흰 벚꽃과 눈을 구분하기 위한 위치·형태 정보
    white_mask = (s <= 45) & (v >= 175)
    white = ratio(white_mask)
    white_upper = float(
        np.count_nonzero((upper_s <= 45) & (upper_v >= 175))
        / max(1, upper_s.size)
    )
    white_lower = float(
        np.count_nonzero((lower_s <= 45) & (lower_v >= 175))
        / max(1, lower_s.size)
    )

    component_count, _, component_stats, _ = (
        cv2.connectedComponentsWithStats(
            white_mask.astype(np.uint8),
            connectivity=8,
        )
    )
    if component_count > 1:
        largest_white_component = int(
            component_stats[1:, cv2.CC_STAT_AREA].max()
        )
    else:
        largest_white_component = 0
    white_largest_component = float(
        largest_white_component / max(1.0, total)
    )

    low_saturation = ratio(s <= 48)

    edges = cv2.Canny(gray, 70, 150)
    edge_pixels = edges > 0
    white_edge_ratio = float(
        np.count_nonzero(white_mask & edge_pixels)
        / max(1, np.count_nonzero(white_mask))
    )
    edge_density = float(np.mean(edge_pixels))

    return FrameMetrics(
        time_sec=round(time_sec, 3),
        sharpness=round(sharpness, 5),
        laplacian_variance=round(laplacian_variance, 3),
        tenengrad=round(tenengrad, 3),
        brightness=round(float(np.mean(gray)), 3),
        contrast=round(float(np.std(gray)), 3),
        saturation=round(float(np.mean(s)) / 255.0, 5),
        dark_ratio=round(float(np.mean(gray < 25)), 5),
        overexposed_ratio=round(float(np.mean(gray > 245)), 5),
        green_ratio=round(green, 5),
        yellow_ratio=round(yellow, 5),
        pink_ratio=round(pink, 5),
        orange_red_ratio=round(orange_red, 5),
        brown_ratio=round(brown, 5),
        blue_ratio=round(blue, 5),
        white_ratio=round(white, 5),
        white_upper_ratio=round(white_upper, 5),
        white_lower_ratio=round(white_lower, 5),
        white_largest_component_ratio=round(
            white_largest_component,
            5,
        ),
        white_edge_ratio=round(white_edge_ratio, 5),
        low_saturation_ratio=round(low_saturation, 5),
        edge_density=round(edge_density, 5),
    )


def season_scores(metrics: list[FrameMetrics]) -> dict[str, float]:
    green = median([m.green_ratio for m in metrics])
    yellow = median([m.yellow_ratio for m in metrics])
    pink = median([m.pink_ratio for m in metrics])
    warm = median([m.orange_red_ratio for m in metrics])
    brown = median([m.brown_ratio for m in metrics])
    blue = median([m.blue_ratio for m in metrics])
    white = median([m.white_ratio for m in metrics])
    white_upper = median([m.white_upper_ratio for m in metrics])
    white_lower = median([m.white_lower_ratio for m in metrics])
    largest_white = median([
        m.white_largest_component_ratio for m in metrics
    ])
    white_edge = median([m.white_edge_ratio for m in metrics])
    low_sat = median([m.low_saturation_ratio for m in metrics])
    saturation = median([m.saturation for m in metrics])
    brightness = median([m.brightness for m in metrics])
    contrast = median([m.contrast for m in metrics])

    green_p = clamp(green / 0.30)
    yellow_p = clamp(yellow / 0.16)
    pink_p = clamp(pink / 0.10)
    warm_p = clamp(warm / 0.20)
    brown_p = clamp(brown / 0.20)
    blue_p = clamp(blue / 0.28)
    white_p = clamp(white / 0.42)
    white_upper_p = clamp(white_upper / 0.30)
    snow_ground_p = clamp(white_lower / 0.42)
    large_white_p = clamp(largest_white / 0.24)
    white_edge_p = clamp(white_edge / 0.20)
    scattered_white_p = clamp(
        max(0.0, white - largest_white) / 0.18
    )
    low_sat_p = clamp(low_sat / 0.70)
    saturation_p = clamp(saturation / 0.55)
    bright_p = clamp((brightness - 55.0) / 125.0)
    contrast_p = clamp(contrast / 65.0)

    # 눈은 땅·산처럼 넓고 이어진 흰 영역에 가중치를 둡니다.
    snow_surface_p = clamp(
        0.58 * snow_ground_p
        + 0.42 * large_white_p
    )

    # 흰 벚꽃은 상단·수관부에 흩어진 작은 흰 영역과
    # 나뭇가지 윤곽, 주변 녹색·꽃 색상을 함께 사용합니다.
    white_blossom_p = clamp(
        0.34 * white_upper_p
        + 0.28 * scattered_white_p
        + 0.18 * white_edge_p
        + 0.12 * green_p
        + 0.08 * max(pink_p, yellow_p)
        - 0.42 * snow_surface_p
    )
    flower_p = max(pink_p, yellow_p, white_blossom_p)

    scores = {
        "봄": (
            0.23 * green_p
            + 0.22 * pink_p
            + 0.17 * yellow_p
            + 0.24 * white_blossom_p
            + 0.08 * bright_p
            + 0.06 * saturation_p
        ),
        "여름": (
            0.55 * green_p
            + 0.18 * blue_p
            + 0.15 * saturation_p
            + 0.12 * bright_p
            - 0.10 * flower_p
            - 0.10 * max(warm_p, brown_p)
            - 0.12 * snow_surface_p
        ),
        "가을": (
            0.43 * warm_p
            + 0.25 * brown_p
            + 0.17 * yellow_p
            + 0.08 * contrast_p
            + 0.07 * bright_p
            - 0.13 * snow_surface_p
            - 0.07 * white_blossom_p
        ),
        "겨울": (
            0.50 * snow_surface_p
            + 0.18 * low_sat_p
            + 0.10 * blue_p
            + 0.08 * bright_p
            + 0.06 * white_p
            - 0.22 * white_blossom_p
            - 0.12 * warm_p
            - 0.10 * brown_p
            - 0.10 * green_p
        ),
    }
    return {
        season: round(clamp(score), 5)
        for season, score in scores.items()
    }


def scene_sample_times(
    start_time: float,
    end_time: float,
    count: int,
) -> list[float]:
    duration = end_time - start_time
    if duration <= 0:
        return []
    if count <= 1:
        return [start_time + duration * 0.5]
    return [
        start_time + duration * (0.08 + 0.84 * index / (count - 1))
        for index in range(count)
    ]


def evaluate_scene(
    video_path: Path,
    start_time: float,
    end_time: float,
    expected_seasons: list[str],
    season_match_required: bool,
    scene_change_confidence: float,
    source_segment_id: str,
    source_description: str,
    rules: dict[str, Any],
) -> SceneCandidate:
    sharp_rules = rules["sharpness_filter"]
    exposure_rules = rules["exposure_filter"]
    season_rules = rules["season_filter"]

    frames: list[tuple[np.ndarray, FrameMetrics]] = []
    for time_sec in scene_sample_times(
        start_time,
        end_time,
        int(sharp_rules["sample_frames_per_scene"]),
    ):
        frame = read_frame(video_path, time_sec)
        if frame is not None:
            frames.append((frame, calculate_frame_metrics(frame, time_sec)))

    reasons: list[str] = []
    if len(frames) < 4:
        reasons.append("검사 가능한 프레임이 4장 미만")
        return SceneCandidate(
            start_time=start_time,
            end_time=end_time,
            representative_frame_time=(start_time + end_time) / 2,
            representative_histogram=[],
            total_score=0.0,
            scene_change_confidence=scene_change_confidence,
            sharpness_score=0.0,
            season_score=0.0,
            expected_season="",
            overall_detected_season="",
            quality_components={},
            season_scores={season: 0.0 for season in SEASONS},
            source_segment_id=source_segment_id,
            source_description=source_description,
            accepted=False,
            rejection_reasons=reasons,
        )

    metrics = [item[1] for item in frames]
    sharpness_values = [m.sharpness for m in metrics]
    median_sharpness = median(sharpness_values)
    best_index = int(np.argmax(np.asarray(sharpness_values)))
    best_frame, best_metrics = frames[best_index]
    best_sharpness = best_metrics.sharpness
    blurry_ratio = float(
        np.mean(
            np.asarray(sharpness_values)
            < float(sharp_rules["minimum_median_sharpness"])
        )
    )

    brightness = median([m.brightness for m in metrics])
    dark_ratio = median([m.dark_ratio for m in metrics])
    overexposed_ratio = median([m.overexposed_ratio for m in metrics])
    contrast = median([m.contrast for m in metrics])
    saturation = median([m.saturation for m in metrics])
    edge_density = median([m.edge_density for m in metrics])

    if median_sharpness < float(sharp_rules["minimum_median_sharpness"]):
        reasons.append(
            f"구간 중앙 선명도 부족({median_sharpness:.3f})"
        )
    if best_sharpness < float(sharp_rules["minimum_best_frame_sharpness"]):
        reasons.append(
            f"대표 프레임 선명도 부족({best_sharpness:.3f})"
        )
    if blurry_ratio > float(sharp_rules["maximum_blurry_frame_ratio"]):
        reasons.append(
            f"흐린 프레임 비율 초과({blurry_ratio:.1%})"
        )

    if brightness < float(exposure_rules["minimum_brightness"]):
        reasons.append(f"화면이 너무 어두움({brightness:.1f})")
    if brightness > float(exposure_rules["maximum_brightness"]):
        reasons.append(f"화면이 너무 밝음({brightness:.1f})")
    if dark_ratio > float(exposure_rules["maximum_dark_pixel_ratio"]):
        reasons.append(f"암부 비율 초과({dark_ratio:.1%})")
    if overexposed_ratio > float(
        exposure_rules["maximum_overexposed_pixel_ratio"]
    ):
        reasons.append(f"과노출 비율 초과({overexposed_ratio:.1%})")

    scores = season_scores(metrics)
    overall_detected_season = max(scores, key=scores.get)
    expected = [season for season in expected_seasons if season in SEASONS]

    if expected and season_rules.get("enabled", True):
        expected_season = max(expected, key=lambda season: scores[season])
        expected_score = scores[expected_season]
        other_score = max(
            (score for season, score in scores.items() if season not in expected),
            default=0.0,
        )
        advantage = other_score - expected_score

        # 사람이 계절을 직접 확인한 레코드는 점수는 기록하지만
        # 색상 휴리스틱의 오판만으로 장면을 제외하지 않습니다.
        if season_match_required:
            if expected_score < float(
                season_rules["minimum_expected_season_score"]
            ):
                reasons.append(
                    f"입력 계절 단서 부족({expected_season} {expected_score:.3f})"
                )
            if advantage > float(
                season_rules["maximum_other_season_advantage"]
            ):
                reasons.append(
                    f"다른 계절 단서가 더 강함({overall_detected_season})"
                )
    else:
        expected_season = ""
        expected_score = 1.0

    duration = end_time - start_time
    duration_score = clamp(1.0 - abs(duration - 7.0) / 7.0)
    exposure_score = clamp(
        1.0 - abs(brightness - 130.0) / 130.0
        - dark_ratio * 0.35
        - overexposed_ratio * 0.35
    )
    information_score = clamp(
        0.55 * clamp(edge_density / 0.14)
        + 0.25 * clamp(contrast / 62.0)
        + 0.20 * clamp(saturation / 0.48)
    )

    total_score = (
        0.34 * median_sharpness
        + 0.19 * best_sharpness
        + 0.20 * expected_score
        + 0.10 * exposure_score
        + 0.09 * information_score
        + 0.05 * duration_score
        + 0.03 * scene_change_confidence
    )

    histogram = normalized_histogram(best_frame).astype(float).tolist()

    return SceneCandidate(
        start_time=round(start_time, 3),
        end_time=round(end_time, 3),
        representative_frame_time=best_metrics.time_sec,
        representative_histogram=histogram,
        total_score=round(total_score, 6),
        scene_change_confidence=round(scene_change_confidence, 5),
        sharpness_score=round(median_sharpness, 5),
        season_score=round(expected_score, 5),
        expected_season=expected_season,
        overall_detected_season=overall_detected_season,
        quality_components={
            "median_sharpness": round(median_sharpness, 5),
            "best_frame_sharpness": round(best_sharpness, 5),
            "blurry_frame_ratio": round(blurry_ratio, 5),
            "brightness": round(brightness, 3),
            "dark_ratio": round(dark_ratio, 5),
            "overexposed_ratio": round(overexposed_ratio, 5),
            "contrast": round(contrast, 3),
            "saturation": round(saturation, 5),
            "edge_density": round(edge_density, 5),
            "exposure_score": round(exposure_score, 5),
            "information_score": round(information_score, 5),
            "duration_score": round(duration_score, 5),
            "representative_laplacian_variance": best_metrics.laplacian_variance,
            "representative_tenengrad": best_metrics.tenengrad,
        },
        season_scores=scores,
        source_segment_id=source_segment_id,
        source_description=source_description,
        accepted=not reasons,
        rejection_reasons=reasons,
    )


def histogram_similarity(
    first: list[float],
    second: list[float],
) -> float:
    if not first or not second:
        return 0.0
    first_arr = np.asarray(first, dtype=np.float32)
    second_arr = np.asarray(second, dtype=np.float32)
    return float(
        cv2.compareHist(first_arr, second_arr, cv2.HISTCMP_CORREL)
    )


def best_window_in_long_scene(
    video_path: Path,
    start_time: float,
    end_time: float,
    maximum_scene: float,
) -> tuple[float, float]:
    duration = end_time - start_time
    if duration <= maximum_scene:
        return start_time, end_time

    search_start = start_time + maximum_scene * 0.5
    search_end = end_time - maximum_scene * 0.5
    test_times = np.linspace(
        search_start,
        search_end,
        max(3, int((search_end - search_start) / 1.0) + 1),
    )

    best_time = (start_time + end_time) * 0.5
    best_score = -1.0

    for time_sec in test_times:
        frame = read_frame(video_path, float(time_sec))
        if frame is None:
            continue
        metrics = calculate_frame_metrics(frame, float(time_sec))
        exposure = clamp(1.0 - abs(metrics.brightness - 130.0) / 130.0)
        score = 0.75 * metrics.sharpness + 0.25 * exposure
        if score > best_score:
            best_score = score
            best_time = float(time_sec)

    half = maximum_scene * 0.5
    window_start = max(start_time, best_time - half)
    window_end = min(end_time, window_start + maximum_scene)
    window_start = max(start_time, window_end - maximum_scene)
    return window_start, window_end


def create_candidates_for_range(
    video_path: Path,
    range_start: float,
    range_end: float,
    source_segment_id: str,
    source_description: str,
    expected_seasons: list[str],
    season_match_required: bool,
    rules: dict[str, Any],
) -> tuple[list[SceneCandidate], float]:
    scene_rules = rules["scene_detection"]
    boundaries, confidences, threshold = detect_scene_boundaries(
        video_path=video_path,
        range_start=range_start,
        range_end=range_end,
        sample_step=float(scene_rules["sample_step_seconds"]),
        base_threshold=float(scene_rules["base_cut_threshold"]),
        mad_multiplier=float(scene_rules["adaptive_mad_multiplier"]),
        minimum_cut_gap=float(scene_rules["minimum_cut_gap_seconds"]),
    )

    padding = float(scene_rules["transition_padding_seconds"])
    minimum_scene = float(scene_rules["minimum_scene_seconds"])
    maximum_scene = float(scene_rules["maximum_scene_seconds"])
    candidates: list[SceneCandidate] = []

    for index in range(len(boundaries) - 1):
        raw_start = boundaries[index]
        raw_end = boundaries[index + 1]

        scene_start = raw_start + (padding if index > 0 else min(padding, 0.15))
        scene_end = raw_end - (
            padding if index < len(boundaries) - 2 else min(padding, 0.15)
        )

        if scene_end - scene_start < minimum_scene:
            continue

        scene_start, scene_end = best_window_in_long_scene(
            video_path,
            scene_start,
            scene_end,
            maximum_scene=maximum_scene,
        )

        left_confidence = (
            confidences.get(round(raw_start, 3), 0.75)
            if index > 0
            else 0.70
        )
        right_confidence = (
            confidences.get(round(raw_end, 3), 0.75)
            if index < len(boundaries) - 2
            else 0.70
        )
        scene_change_confidence = (left_confidence + right_confidence) / 2.0

        candidate = evaluate_scene(
            video_path=video_path,
            start_time=scene_start,
            end_time=scene_end,
            expected_seasons=expected_seasons,
            season_match_required=season_match_required,
            scene_change_confidence=scene_change_confidence,
            source_segment_id=source_segment_id,
            source_description=source_description,
            rules=rules,
        )
        candidates.append(candidate)

    return candidates, threshold


def select_candidates(
    candidates: list[SceneCandidate],
    max_count: int,
    duplicate_similarity: float,
) -> tuple[list[SceneCandidate], list[SceneCandidate]]:
    accepted_pool = sorted(
        [candidate for candidate in candidates if candidate.accepted],
        key=lambda item: item.total_score,
        reverse=True,
    )
    selected: list[SceneCandidate] = []
    selection_rejected: list[SceneCandidate] = []

    for candidate in accepted_pool:
        if len(selected) >= max_count:
            candidate.accepted = False
            candidate.rejection_reasons.append(
                "영상당 최대 선택 개수 초과(상위 점수 장면 우선 선택)"
            )
            selection_rejected.append(candidate)
            continue

        duplicate = False
        for existing in selected:
            similarity = histogram_similarity(
                candidate.representative_histogram,
                existing.representative_histogram,
            )
            if similarity >= duplicate_similarity:
                candidate.accepted = False
                candidate.rejection_reasons.append(
                    f"이미 선택된 장면과 화면이 유사함({similarity:.3f})"
                )
                selection_rejected.append(candidate)
                duplicate = True
                break

        if not duplicate:
            selected.append(candidate)

    return sorted(selected, key=lambda item: item.start_time), selection_rejected


def extract_clip(
    input_path: Path,
    output_path: Path,
    start_time: float,
    end_time: float,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = end_time - start_time
    command = [
        get_ffmpeg_executable(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{start_time:.3f}",
        "-i",
        str(input_path),
        "-t",
        f"{duration:.3f}",
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-crf",
        "19",
        "-preset",
        "fast",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    run_command(command)


def extract_keyframe(
    video_path: Path,
    output_path: Path,
    time_sec: float,
) -> None:
    frame = read_frame(video_path, time_sec)
    if frame is None:
        raise RuntimeError(
            f"대표 프레임 추출 실패: {video_path} @ {time_sec}"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), frame):
        raise RuntimeError(f"이미지 저장 실패: {output_path}")


def make_contact_sheet(
    frame_paths: list[tuple[Path, str]],
    output_path: Path,
) -> None:
    valid: list[tuple[Path, str, np.ndarray]] = []
    for frame_path, label in frame_paths:
        frame = cv2.imread(str(frame_path))
        if frame is not None:
            valid.append((frame_path, label, frame))

    if not valid:
        return

    tile_width = 300
    tile_height = 440
    label_height = 70
    columns = min(4, len(valid))
    rows = math.ceil(len(valid) / columns)

    canvas = np.full(
        (rows * (tile_height + label_height), columns * tile_width, 3),
        255,
        dtype=np.uint8,
    )

    for index, (frame_path, label, frame) in enumerate(valid):
        height, width = frame.shape[:2]
        scale = min(tile_width / width, tile_height / height)
        resized = cv2.resize(
            frame,
            (max(1, int(width * scale)), max(1, int(height * scale))),
        )

        row = index // columns
        column = index % columns
        x = column * tile_width
        y = row * (tile_height + label_height)
        offset_x = x + (tile_width - resized.shape[1]) // 2
        offset_y = y + (tile_height - resized.shape[0]) // 2
        canvas[
            offset_y:offset_y + resized.shape[0],
            offset_x:offset_x + resized.shape[1],
        ] = resized

        cv2.putText(
            canvas,
            frame_path.stem[:34],
            (x + 7, y + tile_height + 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (0, 0, 0),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            canvas,
            label[:40],
            (x + 7, y + tile_height + 51),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (0, 0, 0),
            1,
            cv2.LINE_AA,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), canvas)


def candidate_to_report(
    candidate: SceneCandidate,
    verified_season: str = "",
    season_verified: bool = False,
    season_review_note: str = "",
) -> dict[str, Any]:
    value = asdict(candidate)
    value.pop("representative_histogram", None)

    if season_verified and verified_season in SEASONS:
        auto_detected = value.get("overall_detected_season", "")
        auto_score = value.get("season_score")
        scores = value.get("season_scores", {})

        value["auto_expected_season"] = value.get("expected_season", "")
        value["auto_detected_season"] = auto_detected
        value["auto_season_score"] = auto_score
        value["expected_season"] = verified_season
        value["expected_seasons"] = [verified_season]
        value["overall_detected_season"] = verified_season
        value["detected_season"] = verified_season
        if isinstance(scores, dict) and verified_season in scores:
            value["season_score"] = scores[verified_season]
        value["verified_season"] = verified_season
        value["season_verified"] = True
        value["season_review_status"] = "reviewed"
        value["manual_season_override"] = True
        value["season_review_note"] = season_review_note

    return value


def write_quality_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "video_id",
        "youtube_id",
        "drama_title",
        "candidate_start",
        "candidate_end",
        "accepted",
        "total_score",
        "sharpness_score",
        "expected_season",
        "season_score",
        "detected_season",
        "auto_detected_season",
        "verified_season",
        "season_verified",
        "season_match_required",
        "season_review_note",
        "rejection_reasons",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_quality_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def process_record(
    record: dict[str, Any],
    output_root: Path,
    rules: dict[str, Any],
    cookies_from_browser: str | None,
    skip_download: bool,
    top_k_override: int | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    youtube_id = str(record.get("youtube_id", ""))
    video_id = str(record.get("video_id", youtube_id))
    processing_mode = str(record.get("processing_mode", ""))

    if processing_mode == "needs_time_fix":
        return {
            "video_id": video_id,
            "youtube_id": youtube_id,
            "processing_status": "skipped_time_fix_required",
            "review_status": "time_fix_required",
            "reason": "입력 시간에서 end_time이 start_time보다 크도록 수정해야 합니다.",
            "segments": [],
        }, []

    raw_dir = preferred_existing_dir(
        output_root,
        ("original_videos", "raw_videos"),
    )
    processed_video_root = preferred_existing_dir(
        output_root,
        ("preprocessed_video", "clips"),
    )
    clips_dir = processed_video_root / safe_name(video_id)
    frames_dir = output_root / "keyframes" / safe_name(video_id)
    rejected_frames_dir = output_root / "rejected_keyframes" / safe_name(video_id)
    sheets_dir = output_root / "contact_sheets"

    base_name = f"{safe_name(video_id)}_{safe_name(youtube_id)}"
    if skip_download:
        video_path = find_downloaded_video(raw_dir, base_name)
        if video_path is None:
            raise FileNotFoundError(
                f"원본 영상을 찾지 못했습니다: {raw_dir / base_name}"
            )
    else:
        video_path = download_video(
            record,
            raw_dir=raw_dir,
            cookies_from_browser=cookies_from_browser,
        )

    info = probe_video(video_path)
    expected_seasons = record.get("expected_seasons", record.get("season", []))
    if isinstance(expected_seasons, str):
        expected_seasons = [
            part.strip()
            for part in expected_seasons.split(",")
            if part.strip()
        ]

    verified_season = str(record.get("verified_season", "")).strip()
    season_verified = bool(record.get("season_verified", False))
    season_review_note = str(record.get("season_review_note", "")).strip()
    season_match_required = bool(
        record.get("season_match_required", True)
    )
    if verified_season in SEASONS:
        expected_seasons = [verified_season]

    raw_ranges = record.get("candidate_ranges", [])
    ranges: list[dict[str, Any]] = []

    for candidate_range in raw_ranges:
        start = max(0.0, float(candidate_range.get("start_time", 0.0)))
        end = min(
            info.duration,
            float(candidate_range.get("end_time", info.duration)),
        )
        if end > start:
            ranges.append({
                "start_time": start,
                "end_time": end,
                "source_segment_id": candidate_range.get(
                    "source_segment_id", ""
                ),
                "description": candidate_range.get("description", ""),
            })

    if not ranges:
        ranges = [{
            "start_time": 0.0,
            "end_time": info.duration,
            "source_segment_id": "",
            "description": "전체 영상에서  장면 탐지",
        }]

    all_candidates: list[SceneCandidate] = []
    thresholds: list[float] = []

    for item in ranges:
        candidates, threshold = create_candidates_for_range(
            video_path=video_path,
            range_start=item["start_time"],
            range_end=item["end_time"],
            source_segment_id=item["source_segment_id"],
            source_description=item["description"],
            expected_seasons=expected_seasons,
            season_match_required=season_match_required,
            rules=rules,
        )
        all_candidates.extend(candidates)
        thresholds.append(round(threshold, 6))

    if top_k_override:
        max_count = top_k_override
    elif record.get("source_type") == "쇼츠":
        max_count = int(rules["selection"]["shorts_max_scenes"])
    else:
        max_count = int(rules["selection"]["youtube_max_scenes"])

    selected, duplicate_rejected = select_candidates(
        all_candidates,
        max_count=max_count,
        duplicate_similarity=float(
            rules["duplicate_filter"]["maximum_histogram_similarity"]
        ),
    )
    all_rejected = [
        candidate for candidate in all_candidates if not candidate.accepted
    ]
    for candidate in duplicate_rejected:
        if candidate not in all_rejected:
            all_rejected.append(candidate)

    selected_segments = []
    accepted_sheet_items: list[tuple[Path, str]] = []
    rejected_sheet_items: list[tuple[Path, str]] = []
    quality_rows: list[dict[str, Any]] = []

    for index, candidate in enumerate(selected, 1):
        segment_id = f"{safe_name(video_id)}_SCENE_{index:02d}"
        clip_path = clips_dir / f"{segment_id}.mp4"
        frame_path = frames_dir / f"{segment_id}.jpg"

        extract_clip(
            input_path=video_path,
            output_path=clip_path,
            start_time=candidate.start_time,
            end_time=candidate.end_time,
        )
        extract_keyframe(
            video_path=video_path,
            output_path=frame_path,
            time_sec=candidate.representative_frame_time,
        )

        accepted_sheet_items.append(
            (
                frame_path,
                (
                    f"sharp={candidate.sharpness_score:.2f} "
                    f"season={candidate.expected_season}:"
                    f"{candidate.season_score:.2f}"
                ),
            )
        )

        selected_segments.append({
            "segment_id": segment_id,
            "source_segment_id": candidate.source_segment_id,
            "video_id": video_id,
            "youtube_id": youtube_id,
            "drama_title": record.get("drama_title", ""),
            "place_candidates": record.get("place_candidates", []),
            "region": record.get("region", ""),
            "city": record.get("city", ""),
            "expected_seasons": expected_seasons,
            "expected_season": (
                verified_season
                if season_verified and verified_season in SEASONS
                else candidate.expected_season
            ),
            "detected_season": (
                verified_season
                if season_verified and verified_season in SEASONS
                else candidate.overall_detected_season
            ),
            "overall_detected_season": (
                verified_season
                if season_verified and verified_season in SEASONS
                else candidate.overall_detected_season
            ),
            "auto_detected_season": candidate.overall_detected_season,
            "season_score": (
                candidate.season_scores.get(
                    verified_season,
                    candidate.season_score,
                )
                if season_verified and verified_season in SEASONS
                else candidate.season_score
            ),
            "auto_season_score": candidate.season_score,
            "season_scores": candidate.season_scores,
            "verified_season": (
                verified_season
                if season_verified and verified_season in SEASONS
                else ""
            ),
            "season_verified": (
                season_verified and verified_season in SEASONS
            ),
            "season_review_status": (
                "reviewed"
                if season_verified and verified_season in SEASONS
                else "needs_review"
            ),
            "season_match_required": season_match_required,
            "manual_season_override": (
                season_verified and verified_season in SEASONS
            ),
            "season_review_note": season_review_note,
            "start_time": candidate.start_time,
            "end_time": candidate.end_time,
            "duration": round(
                candidate.end_time - candidate.start_time,
                3,
            ),
            "representative_frame_time": (
                candidate.representative_frame_time
            ),
            "description": (
                candidate.source_description
                or "품질 및 계절 필터를 통과한 중요 장면"
            ),
            "selection_score": candidate.total_score,
            "scene_change_confidence": (
                candidate.scene_change_confidence
            ),
            "quality_components": candidate.quality_components,
            "selection_reason": (
                "확실한 장면 경계에서 전환부를 제거한 뒤, "
                "여러 프레임의 선명도와 노출을 검사하고 "
                "입력 계절 시각 단서가 일치한 장면만 선별"
            ),
            "clip_path": clip_path.relative_to(output_root).as_posix(),
            "keyframe_path": frame_path.relative_to(output_root).as_posix(),
            "time_verified": False,
            "review_status": "needs_review",
        })

    for index, candidate in enumerate(all_rejected, 1):
        frame_path = (
            rejected_frames_dir
            / f"{safe_name(video_id)}_REJECTED_{index:03d}.jpg"
        )
        try:
            extract_keyframe(
                video_path,
                frame_path,
                candidate.representative_frame_time,
            )
            rejected_sheet_items.append(
                (
                    frame_path,
                    " / ".join(candidate.rejection_reasons)[:60],
                )
            )
        except RuntimeError:
            pass

    for candidate in all_candidates:
        quality_rows.append({
            "video_id": video_id,
            "youtube_id": youtube_id,
            "drama_title": record.get("drama_title", ""),
            "candidate_start": candidate.start_time,
            "candidate_end": candidate.end_time,
            "accepted": candidate in selected,
            "total_score": candidate.total_score,
            "sharpness_score": candidate.sharpness_score,
            "expected_season": (
                verified_season
                if season_verified and verified_season in SEASONS
                else candidate.expected_season
            ),
            "season_score": (
                candidate.season_scores.get(
                    verified_season,
                    candidate.season_score,
                )
                if season_verified and verified_season in SEASONS
                else candidate.season_score
            ),
            "detected_season": (
                verified_season
                if season_verified and verified_season in SEASONS
                else candidate.overall_detected_season
            ),
            "auto_detected_season": candidate.overall_detected_season,
            "verified_season": (
                verified_season
                if season_verified and verified_season in SEASONS
                else ""
            ),
            "season_verified": (
                season_verified and verified_season in SEASONS
            ),
            "season_match_required": season_match_required,
            "season_review_note": season_review_note,
            "rejection_reasons": " / ".join(candidate.rejection_reasons),
        })

    accepted_sheet = sheets_dir / f"{safe_name(video_id)}_ACCEPTED.jpg"
    rejected_sheet = sheets_dir / f"{safe_name(video_id)}_REJECTED.jpg"
    make_contact_sheet(accepted_sheet_items, accepted_sheet)
    make_contact_sheet(rejected_sheet_items, rejected_sheet)

    result = {
        "video_id": video_id,
        "youtube_id": youtube_id,
        "source_url": record.get("source_url", ""),
        "source_type": record.get("source_type", ""),
        "channel_name": record.get("channel_name", ""),
        "raw_video_path": video_path.relative_to(output_root).as_posix(),
        "video_duration": round(info.duration, 3),
        "video_resolution": {
            "width": info.width,
            "height": info.height,
        },
        "quality_profile": "quality_filtered",
        "expected_seasons": expected_seasons,
        "verified_season": (
            verified_season
            if season_verified and verified_season in SEASONS
            else ""
        ),
        "season_verified": (
            season_verified and verified_season in SEASONS
        ),
        "season_review_status": (
            "reviewed"
            if season_verified and verified_season in SEASONS
            else "needs_review"
        ),
        "season_match_required": season_match_required,
        "season_review_note": season_review_note,
        "used_scene_thresholds": thresholds,
        "candidate_scene_count": len(all_candidates),
        "accepted_scene_count": len(selected_segments),
        "rejected_scene_count": len(all_rejected),
        "accepted_contact_sheet": (
            accepted_sheet.relative_to(output_root).as_posix()
            if accepted_sheet.exists()
            else ""
        ),
        "rejected_contact_sheet": (
            rejected_sheet.relative_to(output_root).as_posix()
            if rejected_sheet.exists()
            else ""
        ),
        "processing_status": "completed",
        "review_status": "needs_review",
        "segments": selected_segments,
        "rejected_candidates": [
            candidate_to_report(
                candidate,
                verified_season=verified_season,
                season_verified=season_verified,
                season_review_note=season_review_note,
            )
            for candidate in all_rejected
        ],
    }
    return result, quality_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "확실한 장면 전환, 계절 일치, 선명도 검사를 모두 통과한 "
            "유튜브 관광 영상 장면만 추출"
        )
    )
    parser.add_argument(
        "--manifest",
        default="preprocessing_manifest.json",
    )
    parser.add_argument(
        "--output",
        default="preprocessed_output",
    )
    parser.add_argument(
        "--rights-confirmed",
        action="store_true",
    )
    parser.add_argument(
        "--cookies-from-browser",
        default="",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
    )
    parser.add_argument(
        "--video-id",
        default="",
    )
    parser.add_argument(
        "--youtube-id",
        default="",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="완료된 영상도 기존 결과를 교체하며 다시 처리",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.rights_confirmed and not args.list_only:
        raise PermissionError(
            "사용 권한을 확인한 영상만 처리해야 합니다. "
            "확인했다면 --rights-confirmed를 추가하세요."
        )

    manifest_path = Path(args.manifest).resolve()
    output_root = Path(args.output).resolve()
    manifest = load_json(manifest_path)
    rules = manifest.get("quality_rules")
    if not rules:
        raise ValueError(
            "매니페스트에 quality_rules가 없습니다. "
            "preprocessing_manifest.json을 사용하세요."
        )

    records = [
        record
        for record in manifest.get("records", [])
        if record.get("youtube_id")
    ]

    if args.video_id:
        records = [
            record
            for record in records
            if record.get("video_id") == args.video_id
        ]
    if args.youtube_id:
        records = [
            record
            for record in records
            if record.get("youtube_id") == args.youtube_id
        ]
    if args.limit > 0:
        records = records[:args.limit]

    print(f"전처리 대상: {len(records)}개")
    for index, record in enumerate(records, 1):
        print(
            f"{index:02d}. {record.get('video_id')} | "
            f"{record.get('drama_title')} | "
            f"계절={record.get('expected_seasons', record.get('season'))}"
        )

    if args.list_only:
        return

    check_dependencies()
    output_root.mkdir(parents=True, exist_ok=True)

    results_path = output_root / "preprocessed_segments.json"
    rejected_path = output_root / "rejected_candidates.json"
    quality_csv_path = output_root / "quality_report.csv"

    if results_path.exists():
        results = load_json(results_path)
        if not isinstance(results, list):
            results = []
    else:
        results = []

    completed_ids = {
        item.get("youtube_id")
        for item in results
        if item.get("processing_status") == "completed"
    }
    all_quality_rows = read_quality_csv(quality_csv_path)

    for index, record in enumerate(records, 1):
        youtube_id = record.get("youtube_id")
        video_id = record.get("video_id")
        print("\n" + "=" * 78)
        print(f"[{index}/{len(records)}] {video_id} | {youtube_id}")

        if youtube_id in completed_ids and not args.force:
            print("이미 완료된 영상이라 건너뜁니다.")
            continue

        if args.force:
            results = [
                item
                for item in results
                if item.get("youtube_id") != youtube_id
            ]
            all_quality_rows = [
                row
                for row in all_quality_rows
                if row.get("youtube_id") != youtube_id
            ]
            completed_ids.discard(youtube_id)

            safe_video_id = safe_name(str(video_id))
            processed_video_root = preferred_existing_dir(
                output_root,
                ("preprocessed_video", "clips"),
            )
            for directory in (
                processed_video_root / safe_video_id,
                output_root / "keyframes" / safe_video_id,
                output_root / "rejected_keyframes" / safe_video_id,
            ):
                shutil.rmtree(directory, ignore_errors=True)

            for sheet_name in (
                f"{safe_video_id}_ACCEPTED.jpg",
                f"{safe_video_id}_REJECTED.jpg",
            ):
                sheet_path = output_root / "contact_sheets" / sheet_name
                sheet_path.unlink(missing_ok=True)

            print("기존 결과와 영상별 출력 파일을 제거하고 다시 처리합니다.")

        try:
            result, quality_rows = process_record(
                record=record,
                output_root=output_root,
                rules=rules,
                cookies_from_browser=(
                    args.cookies_from_browser or None
                ),
                skip_download=args.skip_download,
                top_k_override=args.top_k or None,
            )
            all_quality_rows.extend(quality_rows)
        except Exception as error:
            result = {
                "video_id": video_id,
                "youtube_id": youtube_id,
                "source_url": record.get("source_url", ""),
                "processing_status": "failed",
                "review_status": "needs_review",
                "error": f"{type(error).__name__}: {error}",
                "segments": [],
            }
            print(f"실패: {result['error']}")

        results.append(result)
        save_json(results_path, results)

        rejected = [
            {
                "video_id": item.get("video_id"),
                "youtube_id": item.get("youtube_id"),
                "rejected_candidates": item.get(
                    "rejected_candidates", []
                ),
            }
            for item in results
            if item.get("rejected_candidates")
        ]
        save_json(rejected_path, rejected)
        write_quality_csv(quality_csv_path, all_quality_rows)

    print("\n영상 전처리가 완료되었습니다.")
    print(f"통과 장면 JSON: {results_path}")
    print(f"제외 장면 JSON: {rejected_path}")
    print(f"품질 검사 CSV: {quality_csv_path}")
    print("contact_sheets의 ACCEPTED와 REJECTED 이미지를 최종 확인하세요.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n사용자가 작업을 중단했습니다.")
        sys.exit(130)
    except Exception as error:
        print(f"\n실행 실패: {type(error).__name__}: {error}")
        sys.exit(1)
