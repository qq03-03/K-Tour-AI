from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

VIDEO_EXTENSIONS = (".mp4", ".mkv", ".webm", ".mov", ".m4v")
SEASONS = ("봄", "여름", "가을", "겨울")
THEMES = ("꽃이랑 단풍 위주", "전통, 들판", "등산, 숲", "드라이브", "바다, 비")
THEME_DETAILS = ("꽃", "단풍", "전통", "들판", "숲", "도로", "바다, 비")

DETAIL_TO_THEME = {
    "꽃": "꽃이랑 단풍 위주",
    "단풍": "꽃이랑 단풍 위주",
    "전통": "전통, 들판",
    "들판": "전통, 들판",
    "숲": "등산, 숲",
    "도로": "드라이브",
    "바다, 비": "바다, 비",
}


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
    brightness: float
    contrast: float
    saturation: float
    dark_ratio: float
    overexposed_ratio: float
    green_ratio: float
    yellow_ratio: float
    pink_ratio: float
    warm_ratio: float
    brown_ratio: float
    blue_ratio: float
    white_ratio: float
    white_upper_ratio: float
    white_lower_ratio: float
    white_largest_component_ratio: float
    white_edge_ratio: float
    low_saturation_ratio: float
    edge_density: float
    upper_brightness: float
    upper_dark_ratio: float
    upper_low_saturation_ratio: float
    upper_edge_density: float
    upper_blue_ratio: float
    lower_blue_ratio: float
    lower_green_ratio: float
    lower_yellow_ratio: float
    lower_brown_ratio: float
    lower_low_saturation_mid_ratio: float
    lower_edge_density: float


@dataclass
class Candidate:
    start: float
    end: float
    representative_time: float
    quality_status: str
    reject_reasons: list[str]
    final_season: str
    season_score: float
    theme_category: str
    theme_confidence: float
    theme_detail: str
    theme_season_hint: str
    night_view: bool
    total_score: float
    mode: str


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def safe_name(value: str) -> str:
    result = re.sub(r"[^0-9A-Za-z가-힣_-]+", "_", str(value)).strip("_")
    return result or "video"


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def median(values: list[float], default: float = 0.0) -> float:
    if not values:
        return default
    return float(np.median(np.asarray(values, dtype=np.float32)))


def percentile(values: list[float], q: float, default: float = 0.0) -> float:
    if not values:
        return default
    return float(np.percentile(np.asarray(values, dtype=np.float32), q))


def get_ffmpeg_executable() -> str:
    system = shutil.which("ffmpeg")
    if system:
        return system
    try:
        import imageio_ffmpeg
        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and Path(bundled).exists():
            return str(bundled)
    except Exception:
        pass
    raise RuntimeError("FFmpeg를 찾지 못했습니다. 먼저 .\\실행.ps1 setup 을 실행하세요.")


def check_dependencies(need_download: bool = True) -> None:
    get_ffmpeg_executable()
    if need_download:
        result = subprocess.run([sys.executable, "-m", "yt_dlp", "--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if result.returncode != 0:
            raise RuntimeError("yt-dlp가 설치되지 않았습니다. .\\실행.ps1 setup 을 실행하세요.")


def run_command(command: list[str]) -> None:
    print("실행:", " ".join(command))
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(result.stdout[-5000:])


def find_downloaded_video(raw_dir: Path, youtube_id: str) -> Path | None:
    if not raw_dir.exists():
        return None
    items=[]
    for pattern in (f"{safe_name(youtube_id)}.*", f"*{safe_name(youtube_id)}*"):
        items.extend(p for p in raw_dir.glob(pattern) if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS)
    if not items:
        return None
    return max(set(items), key=lambda p: p.stat().st_size)


def download_video(record: dict[str, Any], raw_dir: Path, cookies: str | None) -> Path:
    yt = str(record.get("youtube_id") or "")
    existing = find_downloaded_video(raw_dir, yt)
    if existing:
        print("기존 원본 재사용:", existing.name)
        return existing
    url = str(record.get("source_url") or "").strip()
    if not url:
        raise ValueError(f"source_url 없음: {record.get('source_segment_id')}")
    raw_dir.mkdir(parents=True, exist_ok=True)
    template = raw_dir / f"{safe_name(yt)}.%(ext)s"
    command=[sys.executable,"-m","yt_dlp","--no-playlist","--no-overwrites","--merge-output-format","mp4","-f","bv*[height<=1080]+ba/b[height<=1080]/b","-o",str(template)]
    if cookies:
        command += ["--cookies-from-browser", cookies]
    command.append(url)
    run_command(command)
    found=find_downloaded_video(raw_dir,yt)
    if not found:
        raise RuntimeError(f"다운로드 후 원본을 찾지 못함: {yt}")
    return found


def probe_video(path: Path) -> VideoInfo:
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"영상을 열 수 없습니다: {path}")
    fps=float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    count=float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
    width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    cap.release()
    duration=count/fps if fps>0 else 0.0
    if duration<=0:
        raise RuntimeError(f"영상 길이 확인 실패: {path}")
    return VideoInfo(duration,fps,width,height)


def read_frame(path: Path, time_sec: float) -> np.ndarray | None:
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_POS_MSEC,max(0.0,time_sec)*1000.0)
    ok,frame=cap.read()
    cap.release()
    return frame if ok and frame is not None else None


def resize_analysis(frame: np.ndarray, width: int=360) -> np.ndarray:
    h,w=frame.shape[:2]
    if w<=width:
        return frame
    scale=width/float(w)
    return cv2.resize(frame,(width,max(1,int(h*scale))),interpolation=cv2.INTER_AREA)


def frame_metrics(frame: np.ndarray, time_sec: float) -> FrameMetrics:
    img=resize_analysis(frame)
    gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    hsv=cv2.cvtColor(img,cv2.COLOR_BGR2HSV)
    h,s,v=cv2.split(hsv)
    lap=float(cv2.Laplacian(gray,cv2.CV_64F).var())
    sharp=clamp(math.log1p(max(0.0,lap))/7.0)
    brightness=float(np.mean(v))
    contrast=float(np.std(gray))
    saturation=float(np.mean(s))/255.0
    dark=float(np.mean(v<24))
    over=float(np.mean(v>245))
    total=float(h.size or 1)
    def ratio(mask): return float(np.count_nonzero(mask))/total
    green=ratio((h>=35)&(h<=95)&(s>=45)&(v>=35))
    yellow=ratio((h>=20)&(h<=36)&(s>=55)&(v>=70))
    pink=ratio((h>=150)&(h<=179)&(s>=35)&(v>=75))
    warm=ratio((((h<=20)|(h>=165))&(s>=45)&(v>=42)))
    brown=ratio((h>=5)&(h<=25)&(s>=45)&(v>=25)&(v<=175))
    blue=ratio((h>=90)&(h<=135)&(s>=45)&(v>=45))
    white_mask=(s<=48)&(v>=185)
    white=ratio(white_mask)
    half=max(1,white_mask.shape[0]//2)
    white_upper=float(np.mean(white_mask[:half]))
    white_lower=float(np.mean(white_mask[half:]))
    mask_u8=(white_mask.astype(np.uint8)*255)
    n,_,stats,_=cv2.connectedComponentsWithStats(mask_u8,8)
    largest=0.0
    if n>1:
        largest=float(np.max(stats[1:,cv2.CC_STAT_AREA]))/total
    edges=cv2.Canny(gray,60,150)>0
    white_edge=float(np.mean(edges & white_mask))
    low_sat=float(np.mean(s<45))
    edge_density=float(np.mean(edges))

    # 화면 상단 약 40%를 '하늘 후보 영역'으로 본다.
    # 전체 화면이 어두운 것만으로 야경 판정하지 않고,
    # 상단이 실제 밤하늘처럼 어둡고 비교적 단순한지 함께 본다.
    upper_h=max(1,int(v.shape[0]*0.40))
    upper_v=v[:upper_h]
    upper_s=s[:upper_h]
    upper_hue=h[:upper_h]
    upper_gray=gray[:upper_h]
    upper_brightness=float(np.mean(upper_v))
    upper_dark_ratio=float(np.mean(upper_v<72))
    upper_low_sat=float(np.mean(upper_s<65))
    upper_edges=cv2.Canny(upper_gray,60,150)>0
    upper_edge_density=float(np.mean(upper_edges))
    upper_blue_ratio=float(np.mean((upper_hue>=90)&(upper_hue<=135)&(upper_s>=28)&(upper_v>=20)))

    # 화면 하단 약 55%는 물/들판/도로처럼 지면 성격을 판단하는 보조 영역으로 사용한다.
    lower_y0=max(0,int(v.shape[0]*0.45))
    lower_v=v[lower_y0:]
    lower_s=s[lower_y0:]
    lower_hue=h[lower_y0:]
    lower_gray=gray[lower_y0:]
    lower_blue_ratio=float(np.mean((lower_hue>=90)&(lower_hue<=135)&(lower_s>=35)&(lower_v>=35)))
    lower_green_ratio=float(np.mean((lower_hue>=35)&(lower_hue<=95)&(lower_s>=45)&(lower_v>=35)))
    lower_yellow_ratio=float(np.mean((lower_hue>=20)&(lower_hue<=36)&(lower_s>=50)&(lower_v>=55)))
    lower_brown_ratio=float(np.mean((lower_hue>=5)&(lower_hue<=25)&(lower_s>=35)&(lower_v>=25)&(lower_v<=175)))
    # 아스팔트/포장도로 후보: 저채도 중간 밝기. 단독으로는 도로 확정에 사용하지 않는다.
    lower_low_saturation_mid_ratio=float(np.mean((lower_s<=50)&(lower_v>=45)&(lower_v<=185)))
    lower_edges=cv2.Canny(lower_gray,60,150)>0
    lower_edge_density=float(np.mean(lower_edges))

    return FrameMetrics(
        time_sec,sharp,brightness,contrast,saturation,dark,over,green,yellow,pink,warm,brown,blue,
        white,white_upper,white_lower,largest,white_edge,low_sat,edge_density,
        upper_brightness,upper_dark_ratio,upper_low_sat,upper_edge_density,upper_blue_ratio,
        lower_blue_ratio,lower_green_ratio,lower_yellow_ratio,lower_brown_ratio,
        lower_low_saturation_mid_ratio,lower_edge_density
    )


def text_blob(record: dict[str,Any]) -> str:
    parts=[str(record.get("place_name") or ""),str(record.get("description") or "")]
    for field in ("scene_elements","k_culture_elements","activity","mood","time_of_day"):
        value=record.get(field) or []
        if isinstance(value,list): parts += [str(x) for x in value]
        else: parts.append(str(value))
    return " ".join(parts).lower()


def expected_season(record: dict[str,Any]) -> str:
    verified=str(record.get("verified_season") or "").strip()
    if bool(record.get("season_verified")) and verified in SEASONS:
        return verified
    values=record.get("expected_seasons") or record.get("season") or []
    if isinstance(values,str): values=[values]
    for value in values:
        value=str(value).strip()
        if value in SEASONS:
            return value
    return ""


def season_scores(metrics: list[FrameMetrics], record: dict[str,Any]) -> tuple[dict[str,float],dict[str,bool]]:
    text=text_blob(record)
    pink=max([m.pink_ratio for m in metrics] or [0.0])
    yellow=max([m.yellow_ratio for m in metrics] or [0.0])
    green=percentile([m.green_ratio for m in metrics],90)
    warm=percentile([m.warm_ratio for m in metrics],90)
    brown=percentile([m.brown_ratio for m in metrics],90)
    white=median([m.white_ratio for m in metrics])
    white_upper=percentile([m.white_upper_ratio for m in metrics],90)
    white_lower=median([m.white_lower_ratio for m in metrics])
    largest=median([m.white_largest_component_ratio for m in metrics])
    white_edge=percentile([m.white_edge_ratio for m in metrics],90)
    low_sat=median([m.low_saturation_ratio for m in metrics])
    scattered=max(0.0,white-largest)
    snow=clamp(0.60*clamp(white_lower/0.42)+0.40*clamp(largest/0.24))
    blossom=clamp(0.34*clamp(white_upper/0.28)+0.30*clamp(scattered/0.16)+0.18*clamp(white_edge/0.18)+0.10*clamp(green/0.25)+0.08*clamp(max(pink,yellow)/0.08)-0.55*snow)
    flower_text=any(x in text for x in ("벚꽃","꽃밭","꽃잎","꽃길","꽃나무","유채","개나리","진달래","매화","blossom","flower"))
    autumn_text=any(x in text for x in ("단풍","낙엽","은행","억새","autumn","maple","foliage"))
    snow_text=any(x in text for x in ("설경","적설","빙판","서리","snow"," ice "))
    # '겨울연가' 같은 작품명만으로 겨울 판정하지 않음.
    flower=flower_text or pink>=0.004 or blossom>=0.22 or (yellow>=0.018 and green>=0.07)
    autumn=autumn_text or (warm>=0.10 and brown>=0.08)
    snow_signal=snow_text or snow>=0.42 or (white_lower>=0.26 and low_sat>=0.55 and largest>=0.10)
    summer=green>=0.13 and not flower and not autumn and not snow_signal
    scores={
      "봄": clamp(0.45*clamp(pink/0.05)+0.35*blossom+0.12*clamp(yellow/0.10)+0.08*clamp(green/0.28)+(0.25 if flower_text else 0)-0.35*snow),
      "여름": clamp(0.72*clamp(green/0.32)+0.16*clamp(median([m.saturation for m in metrics])/0.55)+0.12*(1.0 if summer else 0)-0.30*snow),
      "가을": clamp(0.55*clamp(warm/0.24)+0.35*clamp(brown/0.20)+(0.22 if autumn_text else 0)-0.25*clamp(green/0.35)-0.35*snow),
      "겨울": clamp(0.78*snow+0.18*clamp(low_sat/0.75)+(0.20 if snow_text else 0)-0.55*blossom),
    }
    signals={"flower":bool(flower),"autumn":bool(autumn),"snow":bool(snow_signal),"summer":bool(summer)}
    return scores,signals


THEME_KEYWORDS={
 "꽃이랑 단풍 위주": ("벚꽃","꽃밭","꽃잎","꽃길","꽃나무","유채","개나리","진달래","매화","단풍","낙엽","은행","억새","메밀","blossom","flower","foliage","maple"),
 "전통, 들판": ("한옥","궁궐","경복궁","창덕궁","향교","사찰","전통","문화재","고궁","벽화","성곽","농장","농촌","들판","논","밭","초원","palace","temple","mural","field","farmland","meadow"),
 "등산, 숲": ("등산","산림","숲","자연휴양림","수목원","전나무","트레일","hiking","forest","trail","woods","mountain"),
 "드라이브": ("도로","차도","로드","차선","해안도로","산악도로","국도","지방도","고속도로","도로변","가드레일","교차로","터널","로드브이로그","road vlog","road","roadway","highway","street","lane"),
 "바다, 비": ("물","강","하천","계곡","호수","바다","해안","해변","파도","항구","섬","비 ","빗길","우산","water","river","stream","lake","sea","ocean","beach","coast","wave","rain","umbrella"),
}

FLOWER_WORDS=("벚꽃","꽃밭","꽃잎","꽃길","꽃나무","유채","개나리","진달래","매화","장미","수국","코스모스","blossom","flower")
FOLIAGE_WORDS=("단풍","낙엽","은행","억새","foliage","maple","autumn leaves")
TRADITION_WORDS=("한옥","궁궐","궁 ","경복궁","창덕궁","향교","사찰","전통","문화재","고궁","벽화","성곽","기와","한복","palace","temple","mural","traditional")
FIELD_WORDS=("들판","논","밭","초원","평야","농장","농촌","억새밭","갈대밭","field","farmland","meadow","plain")
FOREST_WORDS=("숲","산림","자연휴양림","수목원","전나무","등산","등산로","트레일","forest","woods","hiking","mountain")
WATER_WORDS=("물","강","하천","계곡","호수","바다","해안","해변","파도","항구","섬","water","river","stream","lake","sea","ocean","beach","coast","wave")
RAIN_WORDS=("비 ","빗길","우산","비가","비오는","우천","rain","rainy","umbrella")
DRIVE_STRONG_ROAD_WORDS=(
    "도로","차도","로드","차선","해안도로","산악도로","국도","지방도","고속도로","도로변",
    "가드레일","교차로","터널","로드브이로그","road vlog","road","roadway","highway","street","lane"
)
DRIVE_SUPPORT_WORDS=(
    "드라이브","주행","자동차","차량","차창","블랙박스","대교","교량",
    "drive","driving","vehicle","car","dashcam"
)
PEDESTRIAN_PATH_WORDS=(
    "산책로","산책길","등산로","보행로","보행자","오솔길","트레일","골목","골목길",
    "walkway","walking trail","footpath","pedestrian"
)


def keyword_hits(text: str, words: tuple[str,...]) -> int:
    return sum(1 for w in words if w.lower() in text)


def detail_scores(metrics: list[FrameMetrics], record: dict[str,Any], signals: dict[str,bool] | None=None) -> dict[str,float]:
    """
    장면 하나를 꽃/단풍/전통/들판/숲/도로/바다·비 중 무엇에 가까운지 점수화한다.
    최종 대표 분류는 이 장면 점수를 바로 쓰지 않고, 영상 전체에서 각 상세 테마가
    차지한 '재생시간 비율'을 누적해서 결정한다.
    """
    text=text_blob(record)
    signals=signals or season_scores(metrics,record)[1]
    scene=" ".join(str(x) for x in (record.get("scene_elements") or [])).lower()
    culture=" ".join(str(x) for x in (record.get("k_culture_elements") or [])).lower()
    activity=" ".join(str(x) for x in (record.get("activity") or [])).lower()
    place=str(record.get("place_name") or "").lower()
    context=" ".join((text,scene,culture,activity,place))

    scores={d:0.0 for d in THEME_DETAILS}

    # 시각 비율
    pink=max([m.pink_ratio for m in metrics] or [0.0])
    yellow=max([m.yellow_ratio for m in metrics] or [0.0])
    warm=median([m.warm_ratio for m in metrics])
    brown=median([m.brown_ratio for m in metrics])
    green=median([m.green_ratio for m in metrics])
    edge=median([m.edge_density for m in metrics])
    lower_blue=median([m.lower_blue_ratio for m in metrics])
    lower_green=median([m.lower_green_ratio for m in metrics])
    lower_yellow=median([m.lower_yellow_ratio for m in metrics])
    lower_brown=median([m.lower_brown_ratio for m in metrics])
    lower_gray=median([m.lower_low_saturation_mid_ratio for m in metrics])
    lower_edge=median([m.lower_edge_density for m in metrics])

    # 야간 여부는 단풍/꽃 색 오인 방지에만 사용. 야경 자체는 별도 night_view.
    tod=" ".join(str(x) for x in (record.get("time_of_day") or [])).lower()
    upper_brightness=median([m.upper_brightness for m in metrics],255.0)
    upper_dark=median([m.upper_dark_ratio for m in metrics],0.0)
    night_like=("밤" in tod) or any(x in text for x in ("야경","야간","밤하늘","nightscape")) or (upper_brightness<=78 and upper_dark>=0.55)

    # 1) 꽃 — 꽃이 실제로 많이 보이는 장면을 높게.
    flower_hits=keyword_hits(context,FLOWER_WORDS)
    if flower_hits:
        scores["꽃"] += 3.0 + min(2.0,0.45*flower_hits)
    if not night_like:
        if bool(signals.get("flower")) and (pink>=0.010 or (yellow>=0.028 and green>=0.07)):
            scores["꽃"] += 1.8
        scores["꽃"] += min(1.4, 8.0*pink + 3.0*max(0.0,yellow-0.02))

    # 2) 단풍 — 따뜻한 색/갈색이 높고 야간 조명이 아닐 때.
    foliage_hits=keyword_hits(context,FOLIAGE_WORDS)
    if foliage_hits:
        scores["단풍"] += 3.0 + min(2.0,0.45*foliage_hits)
    if not night_like:
        if bool(signals.get("autumn")) and warm>=0.10 and brown>=0.07:
            scores["단풍"] += 1.8
        scores["단풍"] += min(1.5, 3.2*warm + 3.0*brown + 1.2*lower_brown)

    # 3) 전통 — 한옥/궁/벽화 등 명시적 의미 단서가 최우선.
    trad_hits=keyword_hits(context,TRADITION_WORDS)
    if trad_hits:
        scores["전통"] += 3.2 + min(2.0,0.5*trad_hits)
    # 어두운 분위기 + 문화/건축 단서가 있으면 전통 쪽을 보강.
    dark_mood=median([m.brightness for m in metrics],255.0) < 92
    architecture_hint=any(x in context for x in ("건물","기와","문","담장","성곽","벽","궁","한옥","벽화"))
    if dark_mood and architecture_hint:
        scores["전통"] += 0.8

    # 4) 들판 — 하단에 초록/노랑/갈색의 넓고 비교적 단순한 면적이 많을 때.
    field_hits=keyword_hits(context,FIELD_WORDS)
    if field_hits:
        scores["들판"] += 3.0 + min(1.8,0.45*field_hits)
    field_color=max(lower_green,lower_yellow,lower_brown)
    if field_color>=0.28 and lower_edge<=0.12:
        scores["들판"] += 1.6 + min(1.2,(field_color-0.28)*5.0)

    # 5) 숲 — 초록 비율과 복잡한 나뭇가지/잎 엣지가 함께 높을 때.
    forest_hits=keyword_hits(context,FOREST_WORDS)
    if forest_hits:
        scores["숲"] += 3.0 + min(1.8,0.45*forest_hits)
    if green>=0.25 and edge>=0.06:
        scores["숲"] += 1.5 + min(1.2,(green-0.25)*4.5)

    # 6) 도로 — 자동차보다 실제 도로/로드 구조와 로드브이로그 신호 우선.
    strong_road_hits=keyword_hits(context,DRIVE_STRONG_ROAD_WORDS)
    support_hits=keyword_hits(context,DRIVE_SUPPORT_WORDS)
    pedestrian_hits=keyword_hits(context,PEDESTRIAN_PATH_WORDS)
    generic_road=("길" in context and pedestrian_hits==0)

    if strong_road_hits:
        scores["도로"] += 3.2 + min(1.8,0.45*strong_road_hits)
    if ("로드브이로그" in context or "road vlog" in context):
        scores["도로"] += 2.0
    if strong_road_hits and support_hits:
        scores["도로"] += min(1.0,0.25*support_hits)
    elif support_hits and generic_road:
        scores["도로"] += 0.8
    elif support_hits:
        scores["도로"] += 0.20

    # 하단 저채도 중간밝기 면적은 포장도로의 약한 보조 신호.
    if lower_gray>=0.42 and lower_edge>=0.035 and pedestrian_hits==0:
        scores["도로"] += 0.65
    if pedestrian_hits and not strong_road_hits:
        scores["도로"] *= 0.15

    # 7) 바다/비 — 물·바다·강이 화면 하단에 많이 보이거나 메타데이터가 명확할 때.
    water_hits=keyword_hits(context,WATER_WORDS)
    rain_hits=keyword_hits(context,RAIN_WORDS)
    if water_hits:
        scores["바다, 비"] += 3.0 + min(2.0,0.40*water_hits)
    if rain_hits:
        scores["바다, 비"] += 3.2 + min(1.5,0.4*rain_hits)
    # 하늘의 파란색을 물로 오인하지 않도록 하단 blue 비율만 강하게 사용.
    if lower_blue>=0.16:
        scores["바다, 비"] += 1.4 + min(1.2,(lower_blue-0.16)*5.0)

    # 강한 근거가 하나도 없을 때만 작은 fallback.
    if max(scores.values())<=0.05:
        if architecture_hint:
            scores["전통"]=0.35
        elif green>=0.20:
            scores["숲"]=0.30
        elif lower_gray>=0.40 and pedestrian_hits==0:
            scores["도로"]=0.28
        else:
            scores["전통"]=0.20

    return {k:round(v,5) for k,v in scores.items()}


def classify_theme_detail(metrics: list[FrameMetrics], record: dict[str,Any], signals: dict[str,bool] | None=None) -> tuple[str,str,float,dict[str,float]]:
    scores=detail_scores(metrics,record,signals)
    detail=max(THEME_DETAILS,key=lambda d:scores[d])
    theme=DETAIL_TO_THEME[detail]
    total=sum(max(0.0,v) for v in scores.values())
    confidence=(scores[detail]/total) if total>0 else 0.0
    return detail,theme,round(confidence,4),scores


def classify_theme(metrics: list[FrameMetrics], record: dict[str,Any], signals: dict[str,bool] | None=None) -> tuple[str,float,dict[str,float]]:
    # 기존 호출부 호환용: 상세 테마를 먼저 고른 뒤 5개 상위 테마로 매핑한다.
    detail,theme,confidence,detail_score_map=classify_theme_detail(metrics,record,signals)
    theme_scores={t:0.0 for t in THEMES}
    for d,v in detail_score_map.items():
        theme_scores[DETAIL_TO_THEME[d]] += v
    return theme,confidence,{k:round(v,4) for k,v in theme_scores.items()}


def classify_flower_foliage_detail(metrics: list[FrameMetrics], record: dict[str,Any], signals: dict[str,bool] | None=None) -> tuple[str,str]:
    # 이전 출력 스키마와의 호환. 대표 상세가 꽃/단풍일 때만 계절 힌트를 남긴다.
    detail,_,_,_=classify_theme_detail(metrics,record,signals)
    if detail=="꽃":
        return "꽃","봄"
    if detail=="단풍":
        return "단풍","가을"
    return detail,""



def detect_night(metrics: list[FrameMetrics], record: dict[str,Any]) -> bool:
    text=text_blob(record)
    tod=" ".join(str(x) for x in (record.get("time_of_day") or [])).lower()

    # 1) 메타데이터가 밤이면 무조건 야경
    night_words=("야경","야간","밤 시간","밤시간","밤하늘","심야","nightscape","night view","at night")
    if any(x in text for x in night_words) or "밤" in tod:
        return True

    if not metrics:
        return False

    upper_brightness=median([m.upper_brightness for m in metrics],255.0)
    upper_dark=median([m.upper_dark_ratio for m in metrics],0.0)
    upper_low_sat=median([m.upper_low_saturation_ratio for m in metrics],0.0)
    upper_edges=median([m.upper_edge_density for m in metrics],1.0)
    upper_blue=median([m.upper_blue_ratio for m in metrics],0.0)
    brightness=median([m.brightness for m in metrics],255.0)
    contrast=median([m.contrast for m in metrics],0.0)
    saturation=median([m.saturation for m in metrics],0.0)

    # 2) 조명 유무와 관계없이 상단 하늘 후보 영역이 밤처럼 충분히 어두우면 야경
    sky_like=(upper_low_sat>=0.42 or upper_blue>=0.04 or upper_edges<=0.17)
    dark_sky=(upper_brightness<=80 and upper_dark>=0.50 and sky_like)
    very_dark_sky=(upper_brightness<=50 and upper_dark>=0.72)

    if dark_sky or very_dark_sky:
        return True

    # 3) 저녁 + 어두운 하늘
    if "저녁" in tod and upper_brightness<=105 and upper_dark>=0.32:
        return True

    # 4) 어두운 분위기 + 조명이 화려한 장면
    lighting_words=("인공 조명","조명","네온","불빛","야간조명","램프","간판","city lights","neon","lights")
    lighting=any(x in text for x in lighting_words)
    colorful_lights = saturation>=0.34 and contrast>=35.0
    if brightness<=105 and (lighting or colorful_lights):
        return True

    # 단순히 전체 화면만 어두운 경우는 야경으로 보지 않는다.
    return False



def quality_score(m: FrameMetrics) -> float:
    exposure=clamp(1.0-abs(m.brightness-130.0)/130.0-m.dark_ratio*0.25-m.overexposed_ratio*0.25)
    info=clamp(0.55*clamp(m.edge_density/0.14)+0.25*clamp(m.contrast/62.0)+0.20*clamp(m.saturation/0.48))
    return clamp(0.50*m.sharpness+0.28*exposure+0.22*info)


def sample_times(start: float,end: float,count: int=7) -> list[float]:
    if end<=start: return []
    if count<=1: return [(start+end)/2]
    margin=min(0.15,(end-start)*0.06)
    a=start+margin; b=end-margin
    if b<=a: a,b=start,end
    return [float(x) for x in np.linspace(a,b,count)]


def evaluate_candidate(path: Path,start: float,end: float,record: dict[str,Any],rules: dict[str,Any],mode: str) -> Candidate:
    duration=max(0.0,end-start)
    count=max(3,min(11,int(math.ceil(duration/6.0))+3))
    samples=[]
    frames=[]
    for t in sample_times(start,end,count):
        f=read_frame(path,t)
        if f is None: continue
        m=frame_metrics(f,t)
        samples.append(m); frames.append((f,m))
    if not samples:
        return Candidate(round(start,3),round(end,3),round((start+end)/2,3),"rejected",["프레임 디코딩 실패"],expected_season(record),0.0,"등산, 숲",0.0,"","",False,0.0,mode)
    q=rules["quality_filter"]
    brightness=median([m.brightness for m in samples])
    dark=median([m.dark_ratio for m in samples])
    over=median([m.overexposed_ratio for m in samples])
    sharp=median([m.sharpness for m in samples])
    best=max(m.sharpness for m in samples)
    blurry=float(np.mean(np.asarray([m.sharpness for m in samples])<0.18))
    reasons=[]

    # 95%+ 확보 목표: 한 가지 수치가 조금 나쁘다는 이유로 제외하지 않는다.
    # 암전/과노출은 '밝기 + 화면 대부분의 픽셀 비율'이 동시에 극단적일 때만 하드 제외.
    if brightness<float(q["minimum_brightness"]) and dark>float(q["maximum_dark_pixel_ratio"]):
        reasons.append("거의 전체 암전")
    if brightness>float(q["maximum_brightness"]) and over>float(q["maximum_overexposed_pixel_ratio"]):
        reasons.append("거의 전체 과노출")

    # 흐림 역시 선명도뿐 아니라 정보량까지 거의 사라진 극단적인 경우만 제외.
    edge_med=median([m.edge_density for m in samples])
    contrast_med=median([m.contrast for m in samples])
    severe_blur=(
        sharp<float(q["minimum_median_sharpness"])
        and best<float(q["minimum_best_frame_sharpness"])
        and edge_med<0.006
        and contrast_med<5.0
    )
    if not reasons and severe_blur:
        reasons.append("장면 식별 불가능 수준의 심한 흐림")

    if not reasons and blurry>float(q["maximum_blurry_frame_ratio"]) and best<float(q["minimum_best_frame_sharpness"]) and edge_med<0.004:
        reasons.append("대부분 프레임이 심하게 흐림")
    scores,signals=season_scores(samples,record)
    exp=expected_season(record)
    auto=max(SEASONS,key=lambda s:scores[s])
    final=exp or auto
    season_score=float(scores.get(final,0.0))
    theme_detail,theme,theme_conf,_=classify_theme_detail(samples,record,signals)
    if theme_detail=="꽃":
        theme_season_hint="봄"
    elif theme_detail=="단풍":
        theme_season_hint="가을"
    else:
        theme_season_hint=""
    night=detect_night(samples,record)
    best_pair=max(frames,key=lambda fm: quality_score(fm[1])+0.18*float(scores.get(final,0.0)))
    rep=float(best_pair[1].time_sec)
    total=median([quality_score(m) for m in samples])+0.20*season_score+0.08*theme_conf
    return Candidate(round(start,3),round(end,3),round(rep,3),"accepted" if not reasons else "rejected",reasons,final,round(season_score,4),theme,theme_conf,theme_detail,theme_season_hint,night,round(total,5),mode)


def histogram_feature(frame: np.ndarray) -> tuple[np.ndarray,float,float]:
    img=resize_analysis(frame)
    hsv=cv2.cvtColor(img,cv2.COLOR_BGR2HSV)
    hist=cv2.calcHist([hsv],[0,1],None,[24,16],[0,180,0,256])
    cv2.normalize(hist,hist)
    gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    return hist,float(np.mean(gray))/255.0,float(np.std(gray))/128.0


def feature_diff(a,b) -> float:
    h1,m1,s1=a; h2,m2,s2=b
    d=float(cv2.compareHist(h1,h2,cv2.HISTCMP_BHATTACHARYYA))
    return 0.72*d+0.16*abs(m1-m2)+0.12*abs(s1-s2)


def detect_boundaries(path: Path,start: float,end: float,rules: dict[str,Any]) -> list[float]:
    sr=rules["scene_detection"]
    step=float(sr.get("sample_step_seconds",0.25))
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened(): return [start,end]
    features=[]; times=[]
    t=start
    while t<=end+1e-6:
        cap.set(cv2.CAP_PROP_POS_MSEC,t*1000.0)
        ok,frame=cap.read()
        if ok and frame is not None:
            features.append(histogram_feature(frame)); times.append(t)
        t+=step
    cap.release()
    if len(features)<3: return [start,end]
    diffs=[feature_diff(features[i-1],features[i]) for i in range(1,len(features))]
    med=float(np.median(diffs)); mad=float(np.median(np.abs(np.asarray(diffs)-med)))
    threshold=max(float(sr["base_cut_threshold"]),med+float(sr["adaptive_mad_multiplier"])*max(mad,0.005))
    gap=float(sr["minimum_cut_gap_seconds"])
    cuts=[]; last=start
    for i,d in enumerate(diffs):
        if d>=threshold:
            cut=times[i]
            if cut-last>=gap and end-cut>=0.20:
                cuts.append(cut); last=cut
    bounds=[start]+cuts+[end]
    merge=float(sr["micro_scene_merge_seconds"])
    changed=True
    while changed and len(bounds)>2:
        changed=False
        for i in range(len(bounds)-1):
            if bounds[i+1]-bounds[i]<merge:
                if i==0: del bounds[1]
                elif i==len(bounds)-2: del bounds[-2]
                else:
                    # 짧은 전환 조각만 인접 장면에 병합. 독립 장면은 gap 기준으로 최대한 보존.
                    del bounds[i+1]
                changed=True; break
    return sorted(set(round(x,3) for x in bounds))


def resolve_ranges(record: dict[str,Any],duration: float) -> tuple[list[dict[str,Any]],list[str]]:
    out=[]; notes=[]
    for item in record.get("candidate_ranges") or []:
        try: start=float(item.get("start_time",0.0))
        except: start=0.0
        try: end=float(item.get("end_time",duration))
        except: end=duration
        original=(start,end)
        start=max(0.0,min(duration,start))
        end=max(0.0,min(duration,end))
        if end<=start:
            start,end=0.0,duration
            notes.append(f"{record.get('source_segment_id')}: 잘못된 입력시간 {original} -> 전체 영상 0~{duration:.3f}")
        elif abs(original[0]-start)>0.001 or abs(original[1]-end)>0.001:
            notes.append(f"{record.get('source_segment_id')}: 입력시간 {original} -> 실제 길이에 맞게 {start:.3f}~{end:.3f}")
        out.append({"start_time":start,"end_time":end,"description":str(item.get("description") or record.get("description") or "")})
    if not out:
        out=[{"start_time":0.0,"end_time":duration,"description":str(record.get("description") or "")}]
        notes.append(f"{record.get('source_segment_id')}: 시간구간 없음 -> 전체 영상 사용")
    return out,notes


def mode_params(range_duration: float,rules: dict[str,Any]) -> tuple[str,dict[str,Any]]:
    ls=rules["length_strategy"]
    if range_duration<=float(ls["short_max_seconds"]): return "short_scene_change",ls["short"]
    if range_duration<=float(ls["medium_max_seconds"]): return "medium_highlight",ls["medium"]
    if range_duration<=float(ls["long_max_seconds"]): return "long_highlight",ls["long"]
    if range_duration<=float(ls["very_long_max_seconds"]): return "very_long_highlight",ls["very_long"]
    return "huge_coarse_highlight",ls["huge"]


def coarse_scan(path: Path,start: float,end: float,record: dict[str,Any],step: float) -> list[dict[str,Any]]:
    samples=[]
    t=start+min(step*0.5,max(0.0,(end-start)*0.1))
    if t>=end: t=(start+end)/2
    while t<end:
        f=read_frame(path,t)
        if f is not None:
            m=frame_metrics(f,t)
            scores,signals=season_scores([m],record)
            exp=expected_season(record)
            final=exp or max(SEASONS,key=lambda s:scores[s])
            detail,theme,conf,_=classify_theme_detail([m],record,signals)
            samples.append({"time":t,"metrics":m,"theme":theme,"detail":detail,"night":detect_night([m],record),"score":quality_score(m)+0.24*float(scores.get(final,0.0))+0.08*conf})
        t+=step
    if not samples:
        t=(start+end)/2
        f=read_frame(path,t)
        if f is not None:
            m=frame_metrics(f,t); scores,signals=season_scores([m],record); exp=expected_season(record); final=exp or max(SEASONS,key=lambda s:scores[s]); detail,theme,conf,_=classify_theme_detail([m],record,signals)
            samples=[{"time":t,"metrics":m,"theme":theme,"detail":detail,"night":detect_night([m],record),"score":quality_score(m)+0.24*float(scores.get(final,0.0))+0.08*conf}]
    return samples


def theme_ratio_from_coarse(samples: list[dict[str,Any]],start: float,end: float) -> tuple[dict[str,float],dict[str,float],str]:
    seconds={t:0.0 for t in THEMES}
    if not samples:
        return seconds,{t:0.0 for t in THEMES},THEMES[0]
    times=[x["time"] for x in samples]
    edges=[start]+[(times[i]+times[i+1])/2 for i in range(len(times)-1)]+[end]
    for i,s in enumerate(samples):
        seconds[s["theme"]]+=max(0.0,edges[i+1]-edges[i])
    total=sum(seconds.values()) or 1.0
    ratios={k:round(v/total,4) for k,v in seconds.items()}
    dominant=max(THEMES,key=lambda t:seconds[t])
    return {k:round(v,3) for k,v in seconds.items()},ratios,dominant

def detail_ratio_from_coarse(samples: list[dict[str,Any]],start: float,end: float) -> tuple[dict[str,float],dict[str,float],str]:
    seconds={d:0.0 for d in THEME_DETAILS}
    if not samples:
        return seconds,{d:0.0 for d in THEME_DETAILS},"전통"
    times=[x["time"] for x in samples]
    edges=[start]+[(times[i]+times[i+1])/2 for i in range(len(times)-1)]+[end]
    for i,s in enumerate(samples):
        detail=str(s.get("detail") or "전통")
        if detail not in seconds:
            detail="전통"
        seconds[detail]+=max(0.0,edges[i+1]-edges[i])
    total=sum(seconds.values()) or 1.0
    ratios={k:round(v/total,4) for k,v in seconds.items()}
    dominant=max(THEME_DETAILS,key=lambda d:seconds[d])
    return {k:round(v,3) for k,v in seconds.items()},ratios,dominant



def select_highlight_windows(samples: list[dict[str,Any]],start: float,end: float,window: float,max_windows: int) -> list[tuple[float,float]]:
    duration=end-start
    if duration<=window*1.15 or not samples:
        return [(start,end)]
    scored=[]
    half=window/2.0
    for s in samples:
        center=float(s["time"])
        vals=[float(x["score"]) for x in samples if abs(float(x["time"])-center)<=half]
        avg=float(np.mean(vals)) if vals else float(s["score"])
        a=max(start,center-half); b=min(end,a+window); a=max(start,b-window)
        scored.append((avg,a,b))
    selected=[]
    for score,a,b in sorted(scored,reverse=True):
        if any(max(a,x)<min(b,y) for x,y in selected):
            continue
        selected.append((a,b))
        if len(selected)>=max_windows: break
    if not selected:
        mid=(start+end)/2; selected=[(max(start,mid-half),min(end,mid+half))]
    return sorted((round(a,3),round(b,3)) for a,b in selected)


def extract_clip(src: Path,dst: Path,start: float,end: float) -> None:
    dst.parent.mkdir(parents=True,exist_ok=True)
    ff=get_ffmpeg_executable(); duration=max(0.05,end-start)
    cmd=[ff,"-y","-ss",f"{start:.3f}","-i",str(src),"-t",f"{duration:.3f}","-map","0:v:0","-map","0:a?","-c:v","libx264","-preset","veryfast","-crf","23","-c:a","aac","-b:a","128k","-movflags","+faststart",str(dst)]
    run_command(cmd)


def extract_keyframe(src: Path,dst: Path,time_sec: float) -> None:
    frame=read_frame(src,time_sec)
    if frame is None: raise RuntimeError(f"대표 프레임 추출 실패: {time_sec}")
    dst.parent.mkdir(parents=True,exist_ok=True)
    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok: raise RuntimeError(f"대표 이미지 인코딩 실패: {dst}")
    encoded.tofile(str(dst))


def process_record(record: dict[str,Any],output: Path,rules: dict[str,Any],skip_download: bool,cookies: str|None) -> tuple[dict[str,Any],list[dict[str,Any]],list[dict[str,Any]]]:
    yt=str(record.get("youtube_id") or ""); video_id=str(record.get("video_id") or safe_name(yt)); source_id=str(record.get("source_segment_id") or "")
    raw_dir=output/"original_videos"
    video=find_downloaded_video(raw_dir,yt)
    if video is None:
        if skip_download: raise FileNotFoundError(f"원본 영상 없음: {yt}")
        video=download_video(record,raw_dir,cookies)
    info=probe_video(video)
    ranges,time_notes=resolve_ranges(record,info.duration)
    all_candidates=[]; internal=[]; theme_seconds_total={t:0.0 for t in THEMES}; detail_seconds_total={d:0.0 for d in THEME_DETAILS}; night_weight=0.0; processed_weight=0.0; modes=[]
    for r in ranges:
        start=float(r["start_time"]); end=float(r["end_time"]); rd=end-start
        mode,params=mode_params(rd,rules); modes.append(mode)
        if mode=="short_scene_change":
            bounds=detect_boundaries(video,start,end,rules)
            candidates=[]
            for i in range(len(bounds)-1):
                a,b=bounds[i],bounds[i+1]
                c=evaluate_candidate(video,a,b,record,rules,mode)
                candidates.append(c)
            # 정확한 장면 지속시간 기반 테마 비율
            for c in candidates:
                if c.quality_status=="accepted":
                    d=max(0.0,c.end-c.start)
                    theme_seconds_total[c.theme_category]+=d
                    if c.theme_detail in detail_seconds_total:
                        detail_seconds_total[c.theme_detail]+=d
                    processed_weight+=d
                    night_weight+=d if c.night_view else 0.0
            all_candidates+=candidates
            internal.append({"range_start":start,"range_end":end,"mode":mode,"boundary_count":len(bounds),"highlight_windows":[]})
        else:
            step=float(params["coarse_step_seconds"]); window=float(params["window_seconds"]); maxw=int(params["max_windows"])
            samples=coarse_scan(video,start,end,record,step)
            secs,ratios,dominant=theme_ratio_from_coarse(samples,start,end)
            detail_secs,detail_ratios,detail_dominant=detail_ratio_from_coarse(samples,start,end)
            for k,v in secs.items(): theme_seconds_total[k]+=v
            for k,v in detail_secs.items(): detail_seconds_total[k]+=v
            processed_weight+=sum(secs.values())
            if samples:
                # night_view도 전체 coarse interval의 비중으로 추정
                times=[x["time"] for x in samples]; edges=[start]+[(times[i]+times[i+1])/2 for i in range(len(times)-1)]+[end]
                for i,s in enumerate(samples):
                    if s["night"]: night_weight+=max(0.0,edges[i+1]-edges[i])
            windows=select_highlight_windows(samples,start,end,window,maxw)
            candidates=[evaluate_candidate(video,a,b,record,rules,mode) for a,b in windows]
            all_candidates+=candidates
            internal.append({"range_start":start,"range_end":end,"mode":mode,"coarse_sample_count":len(samples),"theme_ratios":ratios,"detail_ratios":detail_ratios,"highlight_windows":[{"start":a,"end":b} for a,b in windows]})

    # 대표 상세 테마는 장면 개수가 아니라 실제 출현시간 비율이 가장 높은 항목으로 결정.
    if sum(detail_seconds_total.values())>0:
        dominant_detail=max(THEME_DETAILS,key=lambda d:detail_seconds_total[d])
        dominant=DETAIL_TO_THEME[dominant_detail]
    elif all_candidates:
        dominant_detail=all_candidates[0].theme_detail if all_candidates[0].theme_detail in THEME_DETAILS else "전통"
        dominant=DETAIL_TO_THEME[dominant_detail]
    else:
        dominant_detail="전통"
        dominant="전통, 들판"

    # 상위 테마 시간도 상세테마 최종 집계에 맞게 다시 계산해 일관성을 유지.
    theme_seconds_total={t:0.0 for t in THEMES}
    for detail,seconds in detail_seconds_total.items():
        theme_seconds_total[DETAIL_TO_THEME[detail]]+=seconds

    total_theme=sum(theme_seconds_total.values()) or 1.0
    theme_ratios={k:round(v/total_theme,4) for k,v in theme_seconds_total.items()}
    total_detail=sum(detail_seconds_total.values()) or 1.0
    detail_ratios={k:round(v/total_detail,4) for k,v in detail_seconds_total.items()}
    video_night=(night_weight/max(processed_weight,1e-6))>=0.50
    clips=[]; clean_segments=[]
    accepted=[c for c in all_candidates if c.quality_status=="accepted"]
    for idx,c in enumerate(accepted,1):
        seg_id=f"{source_id}_SCENE_{idx:03d}" if source_id else f"{safe_name(video_id)}_SCENE_{idx:03d}"
        clip=output/"preprocessed_video"/safe_name(video_id)/f"{seg_id}.mp4"
        frame=output/"keyframes"/safe_name(video_id)/f"{seg_id}.jpg"
        extract_clip(video,clip,c.start,c.end)
        extract_keyframe(video,frame,c.representative_time)
        item={
          "segment_id":seg_id,"source_segment_id":source_id,"video_id":video_id,"youtube_id":yt,"source_url":record.get("source_url",""),
          "drama_title":record.get("drama_title",""),"place_id":record.get("place_id",""),"place_name":record.get("place_name",""),"region":record.get("region",""),"city":record.get("city",""),
          "season":c.final_season,
          "theme_category":dominant,
          "theme_detail":dominant_detail,
          "theme_season_hint":"봄" if dominant_detail=="꽃" else ("가을" if dominant_detail=="단풍" else ""),
          "night_view":bool(c.night_view),
          "start_time":round(c.start,3),"end_time":round(c.end,3),"duration":round(c.end-c.start,3),
          "representative_frame_time":round(c.representative_time,3),"description":record.get("description","") or "영상 전처리 대표 구간",
          "scene_elements":record.get("scene_elements",[]),"mood":record.get("mood",[]),
          "clip_path":clip.relative_to(output).as_posix(),"keyframe_path":frame.relative_to(output).as_posix(),
        }
        clean_segments.append(item)
        clips.append({"segment_id":seg_id,"quality_score":c.total_score,"scene_theme_internal":c.theme_category,"scene_theme_confidence":c.theme_confidence,"theme_detail":c.theme_detail,"theme_season_hint":c.theme_season_hint,"night_view":c.night_view,"mode":c.mode})
    result={
      "source_segment_id":source_id,"video_id":video_id,"youtube_id":yt,"source_url":record.get("source_url",""),"video_duration":round(info.duration,3),
      "processing_modes":sorted(set(modes)),"processing_status":"completed" if clean_segments else "completed_no_usable_segment",
      "segment_count":len(clean_segments),"rejected_candidate_count":sum(1 for c in all_candidates if c.quality_status!="accepted"),
      "theme_category":dominant,"theme_detail":dominant_detail,"night_view":video_night,"processed_at":now_iso(),"raw_video_path":video.relative_to(output).as_posix(),
    }
    diag={"source_segment_id":source_id,"youtube_id":yt,"video_duration":round(info.duration,3),"time_adjustments":time_notes,"ranges":internal,"theme_duration_seconds":{k:round(v,3) for k,v in theme_seconds_total.items()},"theme_duration_ratios":theme_ratios,"detail_duration_seconds":{k:round(v,3) for k,v in detail_seconds_total.items()},"detail_duration_ratios":detail_ratios,"dominant_theme":dominant,"dominant_detail":dominant_detail,"night_ratio":round(night_weight/max(processed_weight,1e-6),4),"accepted_candidates":clips,"rejected_candidates":[{"start":c.start,"end":c.end,"reasons":c.reject_reasons,"mode":c.mode} for c in all_candidates if c.quality_status!="accepted"]}
    return result,clean_segments,[diag]


def parse_args():
    p=argparse.ArgumentParser(description="K-콘텐츠 길이별 자동 영상 전처리")
    p.add_argument("--manifest",default="preprocessing_manifest.json")
    p.add_argument("--output",default="preprocessed_output")
    p.add_argument("--rights-confirmed",action="store_true")
    p.add_argument("--skip-download",action="store_true")
    p.add_argument("--cookies-from-browser",default="")
    p.add_argument("--source-segment-id",default="")
    p.add_argument("--video-id",default="")
    p.add_argument("--list-only",action="store_true")
    p.add_argument("--dry-run",action="store_true")
    p.add_argument("--force",action="store_true")
    p.add_argument("--limit",type=int,default=0)
    return p.parse_args()


def main():
    args=parse_args(); manifest_path=Path(args.manifest).resolve(); output=Path(args.output).resolve(); manifest=load_json(manifest_path); rules=manifest["quality_rules"]
    records=[x for x in manifest.get("records",[]) if isinstance(x,dict)]
    if args.source_segment_id: records=[r for r in records if str(r.get("source_segment_id"))==args.source_segment_id]
    if args.video_id: records=[r for r in records if str(r.get("video_id"))==args.video_id]
    if args.limit>0: records=records[:args.limit]
    print(f"전처리 대상: {len(records)}개")
    for i,r in enumerate(records,1):
        cr=(r.get("candidate_ranges") or [{}])[0]; d=float(cr.get("end_time",0))-float(cr.get("start_time",0)); mode,_=mode_params(max(0,d),rules)
        print(f"{i:03d}. {r.get('source_segment_id')} | {r.get('drama_title')} | {r.get('place_name')} | 입력범위={d:.1f}s | {mode}")
    if args.list_only or args.dry_run: return
    if not args.rights_confirmed: raise PermissionError("영상 사용 권한을 확인한 뒤 -RightsConfirmed 옵션으로 실행하세요.")
    check_dependencies(need_download=not args.skip_download)
    output.mkdir(parents=True,exist_ok=True)
    results_path=output/"processing_results.json"; handoff_path=output/"preprocessed_segments.json"; diag_path=output/"_internal"/"processing_diagnostics.json"
    results=load_json(results_path) if results_path.exists() else []
    handoff=load_json(handoff_path) if handoff_path.exists() else []
    diagnostics=load_json(diag_path) if diag_path.exists() else []
    result_by_id={str(x.get("source_segment_id")):x for x in results if isinstance(x,dict)}
    for index,record in enumerate(records,1):
        sid=str(record.get("source_segment_id") or "")
        prev=result_by_id.get(sid)
        if prev and str(prev.get("processing_status","")).startswith("completed") and not args.force:
            print(f"[{index}/{len(records)}] {sid}: 이미 완료 -> 건너뜀")
            continue
        print("\n"+"="*72); print(f"[{index}/{len(records)}] {sid} | {record.get('source_url')}")
        results=[x for x in results if str(x.get("source_segment_id"))!=sid]
        handoff=[x for x in handoff if str(x.get("source_segment_id"))!=sid]
        diagnostics=[x for x in diagnostics if str(x.get("source_segment_id"))!=sid]
        try:
            result,segments,diags=process_record(record,output,rules,args.skip_download,args.cookies_from_browser or None)
            results.append(result); handoff.extend(segments); diagnostics.extend(diags)
            print(f"완료: {len(segments)}개 구간 | 테마={result.get('theme_category')} | night={result.get('night_view')}")
        except Exception as e:
            failed={"source_segment_id":sid,"video_id":record.get("video_id",""),"youtube_id":record.get("youtube_id",""),"source_url":record.get("source_url",""),"processing_status":"failed","error":f"{type(e).__name__}: {e}","segment_count":0,"processed_at":now_iso()}
            results.append(failed); print("실패:",failed["error"])
        save_json(results_path,results); save_json(handoff_path,handoff); save_json(diag_path,diagnostics)
        result_by_id={str(x.get("source_segment_id")):x for x in results if isinstance(x,dict)}
    total=len(records); success=sum(1 for r in results if str(r.get("source_segment_id")) in {str(x.get("source_segment_id")) for x in records} and int(r.get("segment_count",0))>0); no_result=sum(1 for r in results if str(r.get("source_segment_id")) in {str(x.get("source_segment_id")) for x in records} and r.get("processing_status")=="completed_no_usable_segment"); failed=sum(1 for r in results if str(r.get("source_segment_id")) in {str(x.get("source_segment_id")) for x in records} and r.get("processing_status")=="failed")
    report={"generated_at":now_iso(),"target_count":total,"with_usable_segments":success,"acquisition_rate":round(success/max(total,1),4),"completed_no_usable_segment":no_result,"failed":failed,"target_acquisition_rate":0.95,"note":"정상 재생 가능한 원본 기준 95% 이상 확보를 목표로 하되, 손상/디코딩 실패/사용 불가 화면은 억지로 살리지 않음."}
    save_json(output/"_internal"/"acquisition_report.json",report)
    print("\n전처리 완료")
    print("메타데이터 전달용:",handoff_path)
    print("내부 처리결과:",results_path)
    print("내부 획득률:",output/"_internal"/"acquisition_report.json")


if __name__=="__main__":
    try: main()
    except KeyboardInterrupt:
        print("\n사용자가 작업을 중단했습니다."); sys.exit(130)
    except Exception as e:
        print(f"\n실행 실패: {type(e).__name__}: {e}"); sys.exit(1)
