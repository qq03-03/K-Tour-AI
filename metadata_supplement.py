import sys
import io
import os
import re
import json
import subprocess
from typing import List, Literal, get_args
from pydantic import BaseModel, Field, field_validator
import ollama
from youtube_transcript_api import YouTubeTranscriptApi
import cv2
import yt_dlp

# ====================================================
# 윈도우 터미널 UTF-8 출력 강제 설정
# ====================================================
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ====================================================
# imageio-ffmpeg를 이용한 FFmpeg 자동 경로 연결
# ====================================================
FFMPEG_PATH = None
try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
    ffmpeg_dir = os.path.dirname(FFMPEG_PATH)
    os.environ["PATH"] += os.pathsep + ffmpeg_dir
    print(f"✅ FFmpeg 경로 자동 연결 완료: {FFMPEG_PATH}")
except ImportError:
    print("⚠️ 'imageio-ffmpeg' 모듈이 없습니다. 필요 시 터미널에서 'pip install imageio-ffmpeg'를 실행하세요.")

# ====================================================
# 드라마 + 영화 (drama + movie)
# ====================================================

LOVESTRUCK_IN_THE_CITY = {
    "video_id_prefix": "V014",
    "drama_title": "도시남녀의 사랑법",
    "places": [
        {
            "place_id": "P021",
            "place_name": "청계천",
            "region": "seoul",
            "youtube_id": "DGRMHeI8Wt8",
            "source_url": "https://www.youtube.com/watch?v=DGRMHeI8Wt8",
            "segments": [
                {
                    "segment_id": "V014_P021_S001",
                    "start_time": 275.0,
                    "end_time": 346.0,
                    "keyframe_path": "keyframes/V014_P021_S001.jpg",
                    "season": "",
                    "time_of_day": "저녁, 밤",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "청계천 야경"
                }
            ]
        }
    ]
}

CASTAWAY_DIVA = {
    "video_id_prefix": "V013",
    "drama_title": "무인도의 디바",
    "places": [
        {
            "place_id": "P019",
            "place_name": "상주 함창역",
            "region": "gyeongsang",
            "youtube_id": "dI3Z5u9N0ew",
            "source_url": "https://www.youtube.com/watch?v=dI3Z5u9N0ew",
            "segments": [
                {
                    "segment_id": "V013_P019_S001",
                    "start_time": 0.0,
                    "end_time": 31.0,
                    "keyframe_path": "keyframes/V013_P019_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "함창역"
                }
            ]
        },
        {
            "place_id": "P029",
            "place_name": "상주 경천섬 공원",
            "region": "gyeongsang",
            "youtube_id": "n6_TzBPBYUU",
            "source_url": "https://www.youtube.com/watch?v=n6_TzBPBYUU",
            "segments": [
                {
                    "segment_id": "V013_P029_S001",
                    "start_time": 0.0,
                    "end_time": 17.0,
                    "keyframe_path": "keyframes/V013_P029_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "경천섬 공원"
                }
            ]
        },
        {
            "place_id": "P020",
            "place_name": "서천",
            "region": "chungcheong",
            "youtube_id": "oetlLeT3dmo",
            "source_url": "https://www.youtube.com/watch?v=oetlLeT3dmo",
            "segments": [
                {
                    "segment_id": "V013_P020_S001",
                    "start_time": 30.0,
                    "end_time": 30.0,
                    "keyframe_path": "keyframes/V013_P020_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "장항스카이워크"
                }
            ]
        }
    ]
}

WHEN_THE_WEATHER_IS_FINE = {
    "video_id_prefix": "V012",
    "drama_title": "날씨가 좋으면 찾아가겠어요",
    "places": [
        {
            "place_id": "P018",
            "place_name": "영월 주천강",
            "region": "seoul",
            "youtube_id": "m1hv20znDdU",
            "source_url": "https://www.youtube.com/watch?v=m1hv20znDdU",
            "segments": [
                {
                    "segment_id": "V012_P018_S001",
                    "start_time": 0.0,
                    "end_time": 15.0,
                    "keyframe_path": "keyframes/V012_P018_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "영월 주천강"
                }
            ]
        },
        {
            "place_id": "P018",
            "place_name": "영월 주천강",
            "region": "seoul",
            "youtube_id": "bU-dyF_Gsk8",
            "source_url": "https://www.youtube.com/watch?v=bU-dyF_Gsk8",
            "segments": [
                {
                    "segment_id": "V012_P018_S002",
                    "start_time": 0.0,
                    "end_time": 17.0,
                    "keyframe_path": "keyframes/V012_P018_S002.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "영월 주천강"
                }
            ]
        },
        {
            "place_id": "P018",
            "place_name": "영월 주천강",
            "region": "seoul",
            "youtube_id": "7oeOss6ffuw",
            "source_url": "https://www.youtube.com/watch?v=7oeOss6ffuw", # 1:39까지만 참고
            "segments": [
                {
                    "segment_id": "V012_P018_S003",
                    "start_time": 0.0,
                    "end_time": 98.0,
                    "keyframe_path": "keyframes/V012_P018_S003.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "영월 주천강"
                }
            ]
        }
    ]
}

KINGDOM = {
    "video_id_prefix": "V011",
    "drama_title": "킹덤",
    "places": [
        {
            "place_id": "P016",
            "place_name": "경복궁",
            "region": "seoul",
            "youtube_id": "yZeNfaIK7Nw",
            "source_url": "https://youtu.be/yZeNfaIK7Nw",
            "segments": [
                {
                    "segment_id": "V011_P016_S001",
                    "start_time": 0.0,
                    "end_time": 137.0,
                    "keyframe_path": "keyframes/V011_P016_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후, 저녁, 밤",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "경복궁"
                }
            ]
        },
        {
            "place_id": "P016",
            "place_name": "경복궁",
            "region": "seoul",
            "youtube_id": "Nba1McqxPEo",
            "source_url": "https://www.youtube.com/watch?v=Nba1McqxPEo",
            "segments": [
                {
                    "segment_id": "V011_P016_S002",
                    "start_time": 0.0,
                    "end_time": 34.0,
                    "keyframe_path": "keyframes/V011_P016_S002.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후, 저녁, 밤",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "경복궁"
                }
            ]
        },
        {
            "place_id": "P017",
            "place_name": "창덕궁",
            "region": "seoul",
            "youtube_id": "i2ZuU6szFWE",
            "source_url": "https://youtu.be/i2ZuU6szFWE",
            "segments": [
                {
                    "segment_id": "V011_P017_S001",
                    "start_time": 0.0,
                    "end_time": 85.0,
                    "keyframe_path": "keyframes/V011_P017_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후, 저녁, 밤",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "창덕궁"
                }
            ]
        },
        {
            "place_id": "P017",
            "place_name": "창덕궁",
            "region": "seoul",
            "youtube_id": "c4OOEsGS7Cc",
            "source_url": "https://www.youtube.com/watch?v=c4OOEsGS7Cc",
            "segments": [
                {
                    "segment_id": "V011_P017_S002",
                    "start_time": 0.0,
                    "end_time": 28.0,
                    "keyframe_path": "keyframes/V011_P017_S002.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후, 저녁, 밤",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "창덕궁"
                }
            ]
        }
    ]
}

WHEN_LIFE_GIVES_YOU_TANGERINES = {
    "video_id_prefix": "V002",
    "drama_title": "폭싹 속았수다",
    "places": [
        {
            "place_id": "P004",
            "place_name": "고창 학원농장",
            "region": "jeolla",
            "youtube_id": "Q6qUEvQfjRs",
            "source_url": "https://www.youtube.com/watch?v=Q6qUEvQfjRs",
            "segments": [
                {
                    "segment_id": "V002_P004_S001",
                    "start_time": 0.0,
                    "end_time": 10.0,
                    "keyframe_path": "keyframes/V002_P004_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "고창 학원농장 유채꽃"
                }
            ]
        },
        {
            "place_id": "P004",
            "place_name": "고창 학원농장",
            "region": "jeolla",
            "youtube_id": "rFJT5hNx2AQ",
            "source_url": "https://www.youtube.com/watch?v=rFJT5hNx2AQ",
            "segments": [
                {
                    "segment_id": "V002_P004_S002",
                    "start_time": 10.0,
                    "end_time": 15.0,
                    "keyframe_path": "keyframes/V002_P004_S002.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "드라마속 고창 학원농장 유채꽃"
                }
            ]
        },
        {
            "place_id": "P004",
            "place_name": "고창 학원농장",
            "region": "jeolla",
            "youtube_id": "zY81V4VOA44",
            "source_url": "https://www.youtube.com/watch?v=zY81V4VOA44",
            "segments": [
                {
                    "segment_id": "V002_P004_S003",
                    "start_time": 0.0,
                    "end_time": 23.0,
                    "keyframe_path": "keyframes/V002_P004_S003.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "고창 청보리밭"
                }
            ]
        }
    ]
}

LITTLE_FOREST = {
    "video_id_prefix": "V015",
    "drama_title": "리틀 포레스트",
    "places": [
        {
            "place_id": "P030",
            "place_name": "혜원의 집",
            "region": "gyeongsang",
            "youtube_id": "_MgVRjFcTWE",
            "source_url": "https://www.youtube.com/watch?v=_MgVRjFcTWE",
            "segments": [
                {
                    "segment_id": "V015_P030_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V015_P030_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P030",
            "place_name": "혜원의 집",
            "region": "gyeongsang",
            "youtube_id": "W1rm_FwMh58",
            "source_url": "https://www.youtube.com/watch?v=W1rm_FwMh58",
            "segments": [
                {
                    "segment_id": "V015_P030_S002",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V015_P030_S002.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "내부"
                }
            ]
        },
        {
            "place_id": "P087",
            "place_name": "화본역",
            "region": "gyeongsang",
            "youtube_id": "YIHH8uhM6R8",
            "source_url": "https://www.youtube.com/watch?v=YIHH8uhM6R8",
            "segments": [
                {
                    "segment_id": "V015_P087_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V015_P087_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

CRASH_LANDING_ON_YOU = {
    "video_id_prefix": "V007",
    "drama_title": "사랑의 불시착",
    "places": [
        {
            "place_id": "P012",
            "place_name": "비내섬",
            "region": "chungcheong",
            "youtube_id": "VNXXMn8pgiE",
            "source_url": "https://www.youtube.com/watch?v=VNXXMn8pgiE",
            "segments": [
                {
                    "segment_id": "V007_P012_S001",
                    "start_time": 0.0,
                    "end_time": 60.0,
                    "keyframe_path": "keyframes/V007_P012_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "갈대숲"
                }
            ]
        },
        {
            "place_id": "P012",
            "place_name": "비내섬",
            "region": "chungcheong",
            "youtube_id": "yb4qs4kRVG4",
            "source_url": "https://www.youtube.com/watch?v=yb4qs4kRVG4",
            "segments": [
                {
                    "segment_id": "V007_P012_S002",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V007_P012_S002.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "설경"
                }
            ]
        },
        {
            "place_id": "P031",
            "place_name": "충주 중앙탑공원",
            "region": "chungcheong",
            "youtube_id": "hIlkwdkXAPE",
            "source_url": "https://www.youtube.com/watch?v=hIlkwdkXAPE",
            "segments": [
                {
                    "segment_id": "V007_P031_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V007_P031_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P031",
            "place_name": "충주 중앙탑공원",
            "region": "chungcheong",
            "youtube_id": "Z7u5SNDq0jw",
            "source_url": "https://www.youtube.com/watch?v=Z7u5SNDq0jw",
            "segments": [
                {
                    "segment_id": "V007_P031_S002",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V007_P031_S002.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

LOVELY_RUNNER_BY_PLACE = {
    "video_id_prefix": "V001",
    "drama_title": "선재 업고 튀어",
    "places": [
        {
            "place_id": "P001",
            "place_name": "수원 화성", # 예시 장소 이름
            "region": "gyeonggi", # seoul, gyeonggi, gangwon, jeju 등
            "youtube_id": "nypQChEVN0c",
            "source_url": "https://www.youtube.com/watch?v=nypQChEVN0c",
            "segments": [
                {
                    "segment_id": "V001_P001_S001",
                    "start_time": 0.0,
                    "end_time": 19.0,
                    "keyframe_path": "keyframes/V001_P001_S001.jpg",
                    "season": "", # 봄, 여름, 가을, 겨울, 사계절
                    "time_of_day": "새벽, 오전, 오후", # 새벽, 오전, 오후, 저녁, 밤
                    "mood": [], # "감성적인", "힐링", "로맨틱한"
                    "scene_elements": [], # "벚꽃", "화성", "수원"
                    "k_culture_elements": [], # "한복 체험", "벚꽃 축제", "한옥 스테이"
                    "activity": [], # "꽃밭을 배경으로 산책하기", "사진 찍기", "자연 풍경 감상하기"
                    "description": "수원 화성 동문 행궁동 벚꽃"
                }
            ]
        },
        {
            "place_id": "P002",
            "place_name": "여의도 한강",
            "region": "seoul",
            "youtube_id": "-0MpUmWNN_k",
            "source_url": "https://www.youtube.com/watch?v=-0MpUmWNN_k",
            "segments": [
                {
                    "segment_id": "V001_P002_S001",
                    "start_time": 0.0,
                    "end_time": 124.0,
                    "keyframe_path": "keyframes/V001_P002_S001.jpg",
                    "season": "",
                    "time_of_day": "저녁, 밤",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "여의도 한강 벚꽃"
                }
            ]
        },
        {
            "place_id": "P003",
            "place_name": "수원대학교",
            "region": "gyeonggi",
            "youtube_id": "rbNbOuhhVT0",
            "source_url": "https://www.youtube.com/watch?v=rbNbOuhhVT0",
            "segments": [
                {
                    "segment_id": "V001_P003_S001",
                    "start_time": 0.0,
                    "end_time": 147.0,
                    "keyframe_path": "keyframes/V001_P003_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "수원대학교 캠퍼스 봄 풍경"
                }
            ]
        },
        {
            "place_id": "P032",
            "place_name": "화홍문",
            "region": "gyeonggi",
            "youtube_id": "UMpIdjhxYPQ",
            "source_url": "https://www.youtube.com/watch?v=UMpIdjhxYPQ",
            "segments": [
                {
                    "segment_id": "V001_P032_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V001_P032_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P063",
            "place_name": "수원천 일대",
            "region": "gyeonggi",
            "youtube_id": "-vFzATqn5CA",
            "source_url": "https://www.youtube.com/watch?v=-vFzATqn5CA",
            "segments": [
                {
                    "segment_id": "V001_P063_S001",
                    "start_time": 0.0,
                    "end_time": 57.0,
                    "keyframe_path": "keyframes/V001_P063_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P063",
            "place_name": "수원천 일대",
            "region": "gyeonggi",
            "youtube_id": "dOqvC5nA2wI",
            "source_url": "https://www.youtube.com/watch?v=dOqvC5nA2wI",
            "segments": [
                {
                    "segment_id": "V001_P063_S002",
                    "start_time": 0.0,
                    "end_time": 10.0,
                    "keyframe_path": "keyframes/V001_P063_S002.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P063",
            "place_name": "수원천 일대",
            "region": "gyeonggi",
            "youtube_id": "iJ-IHQ7tvOQ",
            "source_url": "https://www.youtube.com/watch?v=iJ-IHQ7tvOQ",
            "segments": [
                {
                    "segment_id": "V001_P063_S003",
                    "start_time": 0.0,
                    "end_time": 53.0,
                    "keyframe_path": "keyframes/V001_P063_S003.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P064",
            "place_name": "수원 화홍문",
            "region": "gyeonggi",
            "youtube_id": "nypQChEVN0c",
            "source_url": "https://www.youtube.com/watch?v=nypQChEVN0c",
            "segments": [
                {
                    "segment_id": "V001_P064_S001",
                    "start_time": 0.0,
                    "end_time": 19.0,
                    "keyframe_path": "keyframes/V001_P064_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P064",
            "place_name": "수원 화홍문",
            "region": "gyeonggi",
            "youtube_id": "C04KHPUcpd8",
            "source_url": "https://www.youtube.com/watch?v=C04KHPUcpd8",
            "segments": [
                {
                    "segment_id": "V001_P064_S002",
                    "start_time": 0.0,
                    "end_time": 11.0,
                    "keyframe_path": "keyframes/V001_P064_S002.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

VINCENZO = {
    "video_id_prefix": "V016",
    "drama_title": "빈센조",
    "places": [
        {
            "place_id": "P033",
            "place_name": "서울로7017",
            "region": "seoul",
            "youtube_id": "b19nDceyqss",
            "source_url": "https://www.youtube.com/watch?v=b19nDceyqss",
            "segments": [
                {
                    "segment_id": "V016_P033_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V016_P033_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P033",
            "place_name": "서울로7017",
            "region": "seoul",
            "youtube_id": "Kp2ZsTXh8LQ",
            "source_url": "https://www.youtube.com/watch?v=Kp2ZsTXh8LQ",
            "segments": [
                {
                    "segment_id": "V016_P033_S002",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V016_P033_S002.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

ITAEWON_CLASS = {
    "video_id_prefix": "V017",
    "drama_title": "이태원 클라스",
    "places": [
        {
            "place_id": "P034",
            "place_name": "이태원 녹사평 육교",
            "region": "seoul",
            "youtube_id": "rjwgCJQbjik",
            "source_url": "https://www.youtube.com/watch?v=rjwgCJQbjik",
            "segments": [
                {
                    "segment_id": "V017_P034_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V017_P034_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

STRANGERS = {
    "video_id_prefix": "V018",
    "drama_title": "남남",
    "places": [
        {
            "place_id": "P035",
            "place_name": "여수 소호동동다리",
            "region": "jeolla",
            "youtube_id": "MC1PVA9_Ho0",
            "source_url": "https://www.youtube.com/watch?v=MC1PVA9_Ho0",
            "segments": [
                {
                    "segment_id": "V018_P035_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V018_P035_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P035",
            "place_name": "여수 소호동동다리",
            "region": "jeolla",
            "youtube_id": "N8zr4el85GE",
            "source_url": "https://www.youtube.com/watch?v=N8zr4el85GE",
            "segments": [
                {
                    "segment_id": "V018_P035_S002",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V018_P035_S002.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

NOW_WE_ARE_BREAKING_UP = {
    "video_id_prefix": "V019",
    "drama_title": "지금, 헤어지는 중입니다",
    "places": [
        {
            "place_id": "P036",
            "place_name": "부산 더베이101·마린시티",
            "region": "busan",
            "youtube_id": "0FKs6qVKGDE",
            "source_url": "https://www.youtube.com/watch?v=0FKs6qVKGDE",
            "segments": [
                {
                    "segment_id": "V019_P036_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V019_P036_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P036",
            "place_name": "부산 더베이101·마린시티",
            "region": "busan",
            "youtube_id": "qto_FhBvaJI",
            "source_url": "https://www.youtube.com/watch?v=qto_FhBvaJI",
            "segments": [
                {
                    "segment_id": "V019_P036_S002",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V019_P036_S002.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

MY_NAME = {
    "video_id_prefix": "V020",
    "drama_title": "마이 네임",
    "places": [
        {
            "place_id": "P037",
            "place_name": "부산항대교·영도",
            "region": "busan",
            "youtube_id": "w_VwCBHdfH0",
            "source_url": "https://www.youtube.com/watch?v=w_VwCBHdfH0",
            "segments": [
                {
                    "segment_id": "V020_P037_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V020_P037_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P037",
            "place_name": "부산항대교·영도",
            "region": "busan",
            "youtube_id": "A7rRUj2PaAc",
            "source_url": "https://www.youtube.com/watch?v=A7rRUj2PaAc",
            "segments": [
                {
                    "segment_id": "V020_P037_S002",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V020_P037_S002.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

DECISION_TO_LEAVE = {
    "video_id_prefix": "V021",
    "drama_title": "헤어질 결심",
    "places": [
        {
            "place_id": "P038",
            "place_name": "부산 광안대교",
            "region": "busan",
            "youtube_id": "25lLgdRxiGY",
            "source_url": "https://www.youtube.com/watch?v=25lLgdRxiGY",
            "segments": [
                {
                    "segment_id": "V021_P038_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V021_P038_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P038",
            "place_name": "부산 광안대교",
            "region": "busan",
            "youtube_id": "EzIh2EN_QM0",
            "source_url": "https://www.youtube.com/watch?v=EzIh2EN_QM0",
            "segments": [
                {
                    "segment_id": "V021_P038_S002",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V021_P038_S002.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P048",
            "place_name": "부남해변",
            "region": "gangwon",
            "youtube_id": "6Fowfd9CIoM",
            "source_url": "https://www.youtube.com/watch?v=6Fowfd9CIoM",
            "segments": [
                {
                    "segment_id": "V021_P048_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V021_P048_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

TWENTYTH_CENTURY_GIRL = {
    "video_id_prefix": "V022",
    "drama_title": "20세기 소녀",
    "places": [
        {
            "place_id": "P039",
            "place_name": "청주 중앙공원·수암골 일대",
            "region": "chungcheong",
            "youtube_id": "rSGIVEtNrJs",
            "source_url": "https://www.youtube.com/watch?v=rSGIVEtNrJs",
            "segments": [
                {
                    "segment_id": "V022_P039_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V022_P039_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P039",
            "place_name": "청주 중앙공원·수암골 일대",
            "region": "chungcheong",
            "youtube_id": "SjFU0igyWAk",
            "source_url": "https://www.youtube.com/watch?v=SjFU0igyWAk",
            "segments": [
                {
                    "segment_id": "V022_P039_S002",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V022_P039_S002.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

DESTINED_WITH_YOU = {
    "video_id_prefix": "V023",
    "drama_title": "이 연애는 불가항력",
    "places": [
        {
            "place_id": "P040",
            "place_name": "포항 스페이스워크",
            "region": "gyeongsang",
            "youtube_id": "MDE56HAySSU",
            "source_url": "https://www.youtube.com/watch?v=MDE56HAySSU",
            "segments": [
                {
                    "segment_id": "V023_P040_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V023_P040_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P040",
            "place_name": "포항 스페이스워크",
            "region": "gyeongsang",
            "youtube_id": "VP4ZKW5YhrM",
            "source_url": "https://www.youtube.com/watch?v=VP4ZKW5YhrM",
            "segments": [
                {
                    "segment_id": "V023_P040_S002",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V023_P040_S002.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P040",
            "place_name": "포항 스페이스워크",
            "region": "gyeongsang",
            "youtube_id": "GtHPZwo4h9c",
            "source_url": "https://www.youtube.com/watch?v=GtHPZwo4h9c",
            "segments": [
                {
                    "segment_id": "V023_P040_S003",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V023_P040_S003.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

HOMETOWN_CHA_CHA_CHA = {
    "video_id_prefix": "V005",
    "drama_title": "갯마을 차차차",
    "places": [
        {
            "place_id": "P010",
            "place_name": "포항 영일만항",
            "region": "gyeongsang",
            "youtube_id": "UjxY3jz0znE",
            "source_url": "https://www.youtube.com/watch?v=UjxY3jz0znE",
            "segments": [
                {
                    "segment_id": "V005_P010_S001",
                    "start_time": 305.0,
                    "end_time": 430.0,
                    "keyframe_path": "keyframes/V005_P010_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "영일만항 홍두식 배 있는 사방기념공원"
                }
            ]
        },
        {
            "place_id": "P023",
            "place_name": "포항 구룡포 석병리",
            "region": "gyeongsang",
            "youtube_id": "ch9bdaofYxM",
            "source_url": "https://www.youtube.com/watch?v=ch9bdaofYxM",
            "segments": [
                {
                    "segment_id": "V005_P023_S001",
                    "start_time": 0.0,
                    "end_time": 179.0,
                    "keyframe_path": "keyframes/V005_P023_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "드라마 속 구룡포 석병리 어촌마을 풍경"
                }
            ]
        },
        {
            "place_id": "P024",
            "place_name": "포항 청하 공진시장",
            "region": "gyeongsang",
            "youtube_id": "wi11R_vDBmE",
            "source_url": "https://www.youtube.com/watch?v=wi11R_vDBmE",
            "segments": [
                {
                    "segment_id": "V005_P024_S001",
                    "start_time": 0.0,
                    "end_time": 29.0,
                    "keyframe_path": "keyframes/V005_P024_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "청하 공진시장"
                }
            ]
        },
        {
            "place_id": "P041",
            "place_name": "사방기념공원",
            "region": "gyeongsang",
            "youtube_id": "kbQigOKSMuk",
            "source_url": "https://www.youtube.com/watch?v=kbQigOKSMuk",
            "segments": [
                {
                    "segment_id": "V005_P041_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V005_P041_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P023",
            "place_name": "구룡포 석병리",
            "region": "gyeongsang",
            "youtube_id": "NjwqtXvGbw0",
            "source_url": "https://www.youtube.com/watch?v=NjwqtXvGbw0",
            "segments": [
                {
                    "segment_id": "V005_P023_S002",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V005_P023_S002.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

OUR_BLUES = {
    "video_id_prefix": "V006",
    "drama_title": "우리들의 블루스",
    "places": [
        {
            "place_id": "P011",
            "place_name": "제주도 고성오일시장",
            "region": "jeju",
            "youtube_id": "1r7a5mLNGRQ",
            "source_url": "https://www.youtube.com/watch?v=1r7a5mLNGRQ",
            "segments": [
                {
                    "segment_id": "V006_P011_S001",
                    "start_time": 0.0,
                    "end_time": 81.0,
                    "keyframe_path": "keyframes/V006_P011_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "70% 분량 촬영지 모음"
                }
            ]
        },
        {
            "place_id": "P025",
            "place_name": "제주도 청굴물",
            "region": "jeju",
            "youtube_id": "Oeme18IdNzw",
            "source_url": "https://www.youtube.com/watch?v=Oeme18IdNzw",
            "segments": [
                {
                    "segment_id": "V006_P025_S001",
                    "start_time": 0.0,
                    "end_time": 11.0,
                    "keyframe_path": "keyframes/V006_P025_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "청굴물"
                }
            ]
        },
        {
            "place_id": "P026",
            "place_name": "제주도 태봉왓",
            "region": "jeju",
            "youtube_id": "e6FvfWF4uVg",
            "source_url": "https://www.youtube.com/watch?v=e6FvfWF4uVg",
            "segments": [
                {
                    "segment_id": "V006_P026_S001",
                    "start_time": 118.0,
                    "end_time": 298.0,
                    "keyframe_path": "keyframes/V006_P026_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "태봉왓"
                }
            ]
        },
        {
            "place_id": "P027",
            "place_name": "제주도",
            "region": "jeju",
            "youtube_id": "Lb3DGOdPafU",
            "source_url": "https://www.youtube.com/watch?v=Lb3DGOdPafU",
            "segments": [
                {
                    "segment_id": "V006_P027_S001",
                    "start_time": 0.0,
                    "end_time": 15.0,
                    "keyframe_path": "keyframes/V006_P027_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "금능리"
                }
            ]
        },
        {
            "place_id": "P028",
            "place_name": "제주도",
            "region": "jeju",
            "youtube_id": "fr03aYy-ZfI",
            "source_url": "https://www.youtube.com/watch?v=fr03aYy-ZfI",
            "segments": [
                {
                    "segment_id": "V006_P028_S001",
                    "start_time": 0.0,
                    "end_time": 406.0,
                    "keyframe_path": "keyframes/V006_P028_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "금능포구 주변"
                }
            ]
        },
        {
            "place_id": "P042",
            "place_name": "쿠키 가파도",
            "region": "jeju",
            "youtube_id": "7vU46xk0VeU",
            "source_url": "https://www.youtube.com/watch?v=7vU46xk0VeU",
            "segments": [
                {
                    "segment_id": "V006_P042_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V006_P042_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P043",
            "place_name": "신촌 앞바다",
            "region": "jeju",
            "youtube_id": "3EmLhiFVntw",
            "source_url": "https://www.youtube.com/watch?v=3EmLhiFVntw",
            "segments": [
                {
                    "segment_id": "V006_P043_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V006_P043_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

GOBLIN = {
    "video_id_prefix": "V008",
    "drama_title": "도깨비",
    "places": [
        {
            "place_id": "P013",
            "place_name": "강릉 주문진",
            "region": "gangwon",
            "youtube_id": "mCeMgl6rR-U",
            "source_url": "https://www.youtube.com/watch?v=mCeMgl6rR-U",
            "segments": [
                {
                    "segment_id": "V008_P013_S001",
                    "start_time": 198.0,
                    "end_time": 207.0,
                    "keyframe_path": "keyframes/V008_P013_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "영진해변 처음으로 메밀꽃을 주고받는 장면"
                }
            ]
        },
        {
            "place_id": "P013",
            "place_name": "강릉 주문진",
            "region": "gangwon",
            "youtube_id": "vzS5MqlN-wU",
            "source_url": "https://www.youtube.com/watch?v=vzS5MqlN-wU",
            "segments": [
                {
                    "segment_id": "V008_P013_S002",
                    "start_time": 0.0,
                    "end_time": 18.0,
                    "keyframe_path": "keyframes/V008_P013_S002.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "영진해변 방파제"
                }
            ]
        },
        {
            "place_id": "P014",
            "place_name": "평창 월정사",
            "region": "gangwon",
            "youtube_id": "2jiJ9CCzclg",
            "source_url": "https://www.youtube.com/watch?v=2jiJ9CCzclg",
            "segments": [
                {
                    "segment_id": "V008_P014_S001",
                    "start_time": 0.0,
                    "end_time": 28.0,
                    "keyframe_path": "keyframes/V008_P014_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "오대산 월정사 전나무 숲길"
                }
            ]
        },
        {
            "place_id": "P014",
            "place_name": "평창 월정사",
            "region": "gangwon",
            "youtube_id": "89CfEae8uRI",
            "source_url": "https://www.youtube.com/watch?v=89CfEae8uRI",
            "segments": [
                {
                    "segment_id": "V008_P014_S002",
                    "start_time": 0.0,
                    "end_time": 139.0,
                    "keyframe_path": "keyframes/V008_P014_S002.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "오대산 월정사 전나무 숲길"
                }
            ]
        },
        {
            "place_id": "P044",
            "place_name": "주문진 방파제",
            "region": "gangwon",
            "youtube_id": "oWyqws_5cbs",
            "source_url": "https://www.youtube.com/watch?v=oWyqws_5cbs",
            "segments": [
                {
                    "segment_id": "V008_P044_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V008_P044_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

HOTEL_DEL_LUNA = {
    "video_id_prefix": "V009",
    "drama_title": "호텔 델루나",
    "places": [
        {
            "place_id": "P015",
            "place_name": "동해 망상",
            "region": "gangwon",
            "youtube_id": "7ir6-MekfHU",
            "source_url": "https://www.youtube.com/watch?v=7ir6-MekfHU",
            "segments": [
                {
                    "segment_id": "V009_P015_S001",
                    "start_time": 0.0,
                    "end_time": 44.0,
                    "keyframe_path": "keyframes/V009_P015_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "동해 망상"
                }
            ]
        },
        {
            "place_id": "P022",
            "place_name": "파라다이스시티",
            "region": "incheon",
            "youtube_id": "ju15D1xTvVU",
            "source_url": "https://www.youtube.com/watch?v=ju15D1xTvVU",
            "segments": [
                {
                    "segment_id": "V009_P022_S001",
                    "start_time": 0.0,
                    "end_time": 53.0,
                    "keyframe_path": "keyframes/V009_P022_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후, 저녁",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "호텔 델루나 속 파라다이스시티"
                }
            ]
        },
        {
            "place_id": "P015",
            "place_name": "망상해변",
            "region": "gangwon",
            "youtube_id": "Uiu32MwpDjU",
            "source_url": "https://www.youtube.com/watch?v=Uiu32MwpDjU",
            "segments": [
                {
                    "segment_id": "V009_P015_S002",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V009_P015_S002.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

ARCHITECTURE_101 = {
    "video_id_prefix": "V024",
    "drama_title": "건축학개론",
    "places": [
        {
            "place_id": "P045",
            "place_name": "올레길5코스",
            "region": "jeju",
            "youtube_id": "R1rTRNm2DkI",
            "source_url": "https://www.youtube.com/watch?v=R1rTRNm2DkI",
            "segments": [
                {
                    "segment_id": "V024_P045_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V024_P045_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

WHEN_THE_CAMELLIA_BLOOMS = {
    "video_id_prefix": "V025",
    "drama_title": "동백꽃 필 무렵",
    "places": [
        {
            "place_id": "P046",
            "place_name": "오천항",
            "region": "chungcheong",
            "youtube_id": "FbK7RYLfOik",
            "source_url": "https://www.youtube.com/watch?v=FbK7RYLfOik",
            "segments": [
                {
                    "segment_id": "V025_P046_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V025_P046_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P047",
            "place_name": "구룡포 일본인가옥거리",
            "region": "gyeongsang",
            "youtube_id": "tiwAynjoXEo",
            "source_url": "https://www.youtube.com/watch?v=tiwAynjoXEo",
            "segments": [
                {
                    "segment_id": "V025_P047_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V025_P047_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

HAEUNDAE = {
    "video_id_prefix": "V026",
    "drama_title": "해운대",
    "places": [
        {
            "place_id": "P049",
            "place_name": "이기대 해안산책로",
            "region": "busan",
            "youtube_id": "upSPnITbUEk",
            "source_url": "https://www.youtube.com/watch?v=upSPnITbUEk",
            "segments": [
                {
                    "segment_id": "V026_P049_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V026_P049_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

AUTUMN_IN_MY_HEART = {
    "video_id_prefix": "V027",
    "drama_title": "가을동화",
    "places": [
        {
            "place_id": "P050",
            "place_name": "화진포 해수욕장",
            "region": "gangwon",
            "youtube_id": "XCpPaB9UIVo",
            "source_url": "https://www.youtube.com/watch?v=XCpPaB9UIVo",
            "segments": [
                {
                    "segment_id": "V027_P050_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V027_P050_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P051",
            "place_name": "아바이마을",
            "region": "gangwon",
            "youtube_id": "PmjeJjhmYPU",
            "source_url": "https://www.youtube.com/watch?v=PmjeJjhmYPU",
            "segments": [
                {
                    "segment_id": "V027_P051_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V027_P051_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

PARASITE = {
    "video_id_prefix": "V028",
    "drama_title": "기생충",
    "places": [
        {
            "place_id": "P052",
            "place_name": "자하문터널",
            "region": "seoul",
            "youtube_id": "fbjFq_we3YY",
            "source_url": "https://www.youtube.com/watch?v=fbjFq_we3YY",
            "segments": [
                {
                    "segment_id": "V028_P052_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V028_P052_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

BOYFRIEND = {
    "video_id_prefix": "V029",
    "drama_title": "남자친구",
    "places": [
        {
            "place_id": "P053",
            "place_name": "사천진 해변",
            "region": "gangwon",
            "youtube_id": "U08IEuce6QM",
            "source_url": "https://www.youtube.com/watch?v=U08IEuce6QM",
            "segments": [
                {
                    "segment_id": "V029_P053_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V029_P053_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

REVENANT = {
    "video_id_prefix": "V043",
    "drama_title": "악귀",
    "places": [
        {
            "place_id": "P054",
            "place_name": "영인산 자연휴양림",
            "region": "chungcheong",
            "youtube_id": "UPmSKo82HAI",
            "source_url": "https://www.youtube.com/watch?v=UPmSKo82HAI",
            "segments": [
                {
                    "segment_id": "V043_P054_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V030_P054_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

TWENTY_FIVE_TWENTY_ONE = {
    "video_id_prefix": "V004",
    "drama_title": "스물다섯 스물하나",
    "places": [
        {
            "place_id": "P007",
            "place_name": "한벽굴",
            "region": "jeolla",
            "youtube_id": "lod4cPrl-yc",
            "source_url": "https://www.youtube.com/watch?v=lod4cPrl-yc",
            "segments": [
                {
                    "segment_id": "V004_P007_S001",
                    "start_time": 195.0,
                    "end_time": 230.0,
                    "keyframe_path": "keyframes/V004_P007_S001.jpg",
                    "season": "",
                    "time_of_day": "저녁, 밤",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "청춘터널"
                }
            ]
        },
        {
            "place_id": "P008",
            "place_name": "명진 책 대여점",
            "region": "jeolla",
            "youtube_id": "flZSgw7pP4U",
            "source_url": "https://www.youtube.com/watch?v=flZSgw7pP4U",
            "segments": [
                {
                    "segment_id": "V004_P008_S001",
                    "start_time": 382.0,
                    "end_time": 410.0,
                    "keyframe_path": "keyframes/V004_P008_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "드라마 내 책방"
                }
            ]
        },
        {
            "place_id": "P007",
            "place_name": "한벽굴",
            "region": "jeolla",
            "youtube_id": "ljRH65gLa3A",
            "source_url": "https://www.youtube.com/watch?v=ljRH65gLa3A",
            "segments": [
                {
                    "segment_id": "V004_P007_S002",
                    "start_time": 0.0,
                    "end_time": 34.0,
                    "keyframe_path": "keyframes/V004_P007_S002.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "청춘터널"
                }
            ]
        },
        {
            "place_id": "P009",
            "place_name": "전주 오목대",
            "region": "jeolla",
            "youtube_id": "6EiESTfjT_0",
            "source_url": "https://youtu.be/6EiESTfjT_0",
            "segments": [
                {
                    "segment_id": "V004_P009_S001",
                    "start_time": 0.0,
                    "end_time": 107.0,
                    "keyframe_path": "keyframes/V004_P009_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "한옥마을 전경이 한눈에 들어오는 정자"
                }
            ]
        },
        {
            "place_id": "P007",
            "place_name": "한벽굴",
            "region": "jeolla",
            "youtube_id": "Gxc73dM1Nro",
            "source_url": "https://www.youtube.com/watch?v=Gxc73dM1Nro",
            "segments": [
                {
                    "segment_id": "V004_P007_S003",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V004_P007_S003.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

EXTRAORDINARY_ATTORNEY_WOO = {
    "video_id_prefix": "V030",
    "drama_title": "이상한 변호사 우영우",
    "places": [
        {
            "place_id": "P055",
            "place_name": "동부마을 팽나무",
            "region": "gyeongsang",
            "youtube_id": "NKPNXyPV2T4",
            "source_url": "https://www.youtube.com/watch?v=NKPNXyPV2T4",
            "segments": [
                {
                    "segment_id": "V030_P055_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V030_P055_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

LIGHT_SHOP = {
    "video_id_prefix": "V032",
    "drama_title": "조명가게",
    "places": [
        {
            "place_id": "P056",
            "place_name": "강화 전등사",
            "region": "incheon",
            "youtube_id": "g7jXCiGr0sE",
            "source_url": "https://www.youtube.com/watch?v=g7jXCiGr0sE",
            "segments": [
                {
                    "segment_id": "V032_P056_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V032_P056_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

THE_GLORY = {
    "video_id_prefix": "V033",
    "drama_title": "더 글로리",
    "places": [
        {
            "place_id": "P057",
            "place_name": "청라호수공원",
            "region": "incheon",
            "youtube_id": "i1MTeS2L2G0",
            "source_url": "https://www.youtube.com/watch?v=i1MTeS2L2G0",
            "segments": [
                {
                    "segment_id": "V033_P057_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V033_P057_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

MY_SASSY_GIRL = {
    "video_id_prefix": "V034",
    "drama_title": "엽기적인 그녀",
    "places": [
        {
            "place_id": "P058",
            "place_name": "부평역",
            "region": "incheon",
            "youtube_id": "PxX26_pJrQY",
            "source_url": "https://www.youtube.com/watch?v=PxX26_pJrQY",
            "segments": [
                {
                    "segment_id": "V034_P058_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V034_P058_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

SOMETHING_IN_THE_RAIN = {
    "video_id_prefix": "V035",
    "drama_title": "밥 잘 사주는 예쁜 누나",
    "places": [
        {
            "place_id": "P059",
            "place_name": "원대리 자작나무숲",
            "region": "gangwon",
            "youtube_id": "kuk4mdMZtZc",
            "source_url": "https://www.youtube.com/watch?v=kuk4mdMZtZc",
            "segments": [
                {
                    "segment_id": "V035_P059_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V035_P059_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

KINGDOM2 = {
    "video_id_prefix": "V036",
    "drama_title": "킹덤 시즌2",
    "places": [
        {
            "place_id": "P059",
            "place_name": "원대리 자작나무숲",
            "region": "gangwon",
            "youtube_id": "kuk4mdMZtZc",
            "source_url": "https://www.youtube.com/watch?v=kuk4mdMZtZc",
            "segments": [
                {
                    "segment_id": "V036_P059_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V036_P059_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

OKJA = {
    "video_id_prefix": "V040",
    "drama_title": "옥자",
    "places": [
        {
            "place_id": "P061",
            "place_name": "용화산",
            "region": "gangwon",
            "youtube_id": "tJ43uFpNJwI",
            "source_url": "https://www.youtube.com/watch?v=tJ43uFpNJwI",
            "segments": [
                {
                    "segment_id": "V040_P061_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V040_P061_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

THE_BATTLESHIP_ISLAND = {
    "video_id_prefix": "V041",
    "drama_title": "군함도",
    "places": [
        {
            "place_id": "P061",
            "place_name": "용화산",
            "region": "gangwon",
            "youtube_id": "tJ43uFpNJwI",
            "source_url": "https://www.youtube.com/watch?v=tJ43uFpNJwI",
            "segments": [
                {
                    "segment_id": "V041_P061_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V041_P061_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

MR_SUNSHINE = {
    "video_id_prefix": "V042",
    "drama_title": "미스터 션샤인",
    "places": [
        {
            "place_id": "P062",
            "place_name": "선샤인스튜디오",
            "region": "chungcheong",
            "youtube_id": "i-5Aozd4ITM",
            "source_url": "https://www.youtube.com/watch?v=i-5Aozd4ITM",
            "segments": [
                {
                    "segment_id": "V042_P062_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V042_P062_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P065",
            "place_name": "서산유기방가옥",
            "region": "chungcheong",
            "youtube_id": "y8UzDeGjDbA",
            "source_url": "https://www.youtube.com/watch?v=y8UzDeGjDbA",
            "segments": [
                {
                    "segment_id": "V042_P065_S001",
                    "start_time": 0.0,
                    "end_time": 31.0,
                    "keyframe_path": "keyframes/V042_P065_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P066",
            "place_name": "안동 만휴정",
            "region": "gyeongsang",
            "youtube_id": "NvBIt1uoGXM",
            "source_url": "https://www.youtube.com/watch?v=NvBIt1uoGXM",
            "segments": [
                {
                    "segment_id": "V042_P066_S001",
                    "start_time": 0.0,
                    "end_time": 26.0,
                    "keyframe_path": "keyframes/V042_P066_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P066",
            "place_name": "안동 만휴정",
            "region": "gyeongsang",
            "youtube_id": "k9vNz1ms7lw",
            "source_url": "https://youtu.be/k9vNz1ms7lw",
            "segments": [
                {
                    "segment_id": "V042_P066_S002",
                    "start_time": 0.0,
                    "end_time": 27.0,
                    "keyframe_path": "keyframes/V042_P066_S002.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

OUR_BELOVED_SUMMER = {
    "video_id_prefix": "V003",
    "drama_title": "그 해 우리는",
    "places": [
        {
            "place_id": "P005",
            "place_name": "전주 한옥마을",
            "region": "jeolla",
            "youtube_id": "nK3ge3jQrXc",
            "source_url": "https://www.youtube.com/watch?v=nK3ge3jQrXc",
            "segments": [
                {
                    "segment_id": "V003_P005_S001",
                    "start_time": 262.0,
                    "end_time": 290.0,
                    "keyframe_path": "keyframes/V003_P005_S001.jpg",
                    "season": "",
                    "time_of_day": "오후, 저녁, 밤",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "연수가 걸었던 거리"
                }
            ]
        },
        {
            "place_id": "P001",
            "place_name": "수원 화성",
            "region": "gyeonggi",
            "youtube_id": "tJqIDVFhsNU",
            "source_url": "https://www.youtube.com/watch?v=tJqIDVFhsNU",
            "segments": [
                {
                    "segment_id": "V003_P001_S001",
                    "start_time": 0.0,
                    "end_time": 204.0,
                    "keyframe_path": "keyframes/V003_P001_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후, 저녁, 밤",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "수원 촬영지"
                }
            ]
        },
        {
            "place_id": "P006",
            "place_name": "논산 은빛자연휴양림",
            "region": "chungcheong",
            "youtube_id": "7xQmeawhiX8",
            "source_url": "https://www.youtube.com/watch?v=7xQmeawhiX8",
            "segments": [
                {
                    "segment_id": "V003_P006_S001",
                    "start_time": 0.0,
                    "end_time": 12.0,
                    "keyframe_path": "keyframes/V003_P006_S001.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "한국의 스위스"
                }
            ]
        },
        {
            "place_id": "P006",
            "place_name": "논산 은빛자연휴양림",
            "region": "chungcheong",
            "youtube_id": "cbINxfGIbKU",
            "source_url": "https://www.youtube.com/watch?v=cbINxfGIbKU",
            "segments": [
                {
                    "segment_id": "V003_P006_S002",
                    "start_time": 0.0,
                    "end_time": 16.0,
                    "keyframe_path": "keyframes/V003_P006_S002.jpg",
                    "season": "",
                    "time_of_day": "오전, 오후",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": "주황빛 메타세콰이어"
                }
            ]
        },
        {
            "place_id": "P006",
            "place_name": "은빛자연휴양림",
            "region": "chungcheong",
            "youtube_id": "s6qXNAExf7o",
            "source_url": "https://www.youtube.com/watch?v=s6qXNAExf7o",
            "segments": [
                {
                    "segment_id": "V003_P006_S003",
                    "start_time": 0.0,
                    "end_time": 16.0,
                    "keyframe_path": "keyframes/V003_P006_S003.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

LOVE_RAIN = {
    "video_id_prefix": "V044",
    "drama_title": "사랑비",
    "places": [
        {
            "place_id": "P067",
            "place_name": "계명대",
            "region": "daegu",
            "youtube_id": "nlhrr-2PZRY",
            "source_url": "https://www.youtube.com/watch?v=nlhrr-2PZRY",
            "segments": [
                {
                    "segment_id": "V044_P067_S001",
                    "start_time": 0.0,
                    "end_time": 31.0,
                    "keyframe_path": "keyframes/V044_P067_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P067",
            "place_name": "계명대",
            "region": "daegu",
            "youtube_id": "9B4fmTx1ido",
            "source_url": "https://www.youtube.com/watch?v=9B4fmTx1ido",
            "segments": [
                {
                    "segment_id": "V044_P067_S002",
                    "start_time": 0.0,
                    "end_time": 57.0,
                    "keyframe_path": "keyframes/V044_P067_S002.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P068",
            "place_name": "춘천 제이드가든",
            "region": "gangwon",
            "youtube_id": "LCBgFfm0r7M",
            "source_url": "https://www.youtube.com/watch?v=LCBgFfm0r7M",
            "segments": [
                {
                    "segment_id": "V044_P068_S001",
                    "start_time": 0.0,
                    "end_time": 59.0,
                    "keyframe_path": "keyframes/V044_P068_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

WINTER_SONATA = {
    "video_id_prefix": "V045",
    "drama_title": "겨울연가",
    "places": [
        {
            "place_id": "P069",
            "place_name": "남이섬",
            "region": "gangwon",
            "youtube_id": "5YeMx8-mMwY",
            "source_url": "https://www.youtube.com/watch?v=5YeMx8-mMwY",
            "segments": [
                {
                    "segment_id": "V045_P069_S001",
                    "start_time": 0.0,
                    "end_time": 41.0,
                    "keyframe_path": "keyframes/V045_P069_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P070",
            "place_name": "남이섬 겹벚나무길",
            "region": "gangwon",
            "youtube_id": "KzYaRBjORWU",
            "source_url": "https://www.youtube.com/watch?v=KzYaRBjORWU",
            "segments": [
                {
                    "segment_id": "V045_P070_S001",
                    "start_time": 0.0,
                    "end_time": 8.0,
                    "keyframe_path": "keyframes/V045_P070_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P071",
            "place_name": "남이섬 메타세쿼이아길",
            "region": "gangwon",
            "youtube_id": "Ad5Uw8oVWkc",
            "source_url": "https://www.youtube.com/watch?v=Ad5Uw8oVWkc",
            "segments": [
                {
                    "segment_id": "V045_P071_S001",
                    "start_time": 0.0,
                    "end_time": 7.0,
                    "keyframe_path": "keyframes/V045_P071_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P071",
            "place_name": "남이섬 메타세쿼이아길",
            "region": "gangwon",
            "youtube_id": "_fmhzDFTIH8",
            "source_url": "https://www.youtube.com/watch?v=_fmhzDFTIH8",
            "segments": [
                {
                    "segment_id": "V045_P071_S002",
                    "start_time": 0.0,
                    "end_time": 22.0,
                    "keyframe_path": "keyframes/V045_P071_S002.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

THE_RED_STAINED_SLEEVE_CUFF = {
    "video_id_prefix": "V046",
    "drama_title": "옷소매 붉은 끝동",
    "places": [
        {
            "place_id": "P072",
            "place_name": "아침고요수목원 서화연",
            "region": "gyeonggi",
            "youtube_id": "ZIstO6o3fjA",
            "source_url": "https://www.youtube.com/watch?v=ZIstO6o3fjA",
            "segments": [
                {
                    "segment_id": "V046_P072_S001",
                    "start_time": 0.0,
                    "end_time": 45.0,
                    "keyframe_path": "keyframes/V046_P072_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P072",
            "place_name": "아침고요수목원 서화연",
            "region": "gyeonggi",
            "youtube_id": "2o0mGsKjBcc",
            "source_url": "https://www.youtube.com/watch?v=2o0mGsKjBcc",
            "segments": [
                {
                    "segment_id": "V046_P072_S002",
                    "start_time": 0.0,
                    "end_time": 9.0,
                    "keyframe_path": "keyframes/V046_P072_S002.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P073",
            "place_name": "전주향교",
            "region": "jeolla",
            "youtube_id": "PvvtSJFBgnA",
            "source_url": "https://www.youtube.com/watch?v=PvvtSJFBgnA",
            "segments": [
                {
                    "segment_id": "V046_P073_S001",
                    "start_time": 0.0,
                    "end_time": 144.0,
                    "keyframe_path": "keyframes/V046_P073_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P073",
            "place_name": "전주향교",
            "region": "jeolla",
            "youtube_id": "4ttI0vsN_Bc",
            "source_url": "https://www.youtube.com/watch?v=4ttI0vsN_Bc",
            "segments": [
                {
                    "segment_id": "V046_P073_S002",
                    "start_time": 0.0,
                    "end_time": 7.0,
                    "keyframe_path": "keyframes/V046_P073_S002.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

TRACES_OF_LOVE = {
    "video_id_prefix": "V047",
    "drama_title": "가을로",
    "places": [
        {
            "place_id": "P074",
            "place_name": "영월 선돌",
            "region": "gangwon",
            "youtube_id": "gvt9UwFfdH0",
            "source_url": "https://www.youtube.com/watch?v=gvt9UwFfdH0",
            "segments": [
                {
                    "segment_id": "V047_P074_S001",
                    "start_time": 0.0,
                    "end_time": 38.0,
                    "keyframe_path": "keyframes/V047_P074_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

THE_KINGS_AFFECTION = {
    "video_id_prefix": "V048",
    "drama_title": "연모",
    "places": [
        {
            "place_id": "P073",
            "place_name": "전주향교",
            "region": "jeolla",
            "youtube_id": "Zn6nfri9tzs",
            "source_url": "https://www.youtube.com/watch?v=Zn6nfri9tzs",
            "segments": [
                {
                    "segment_id": "V048_P073_S001",
                    "start_time": 0.0,
                    "end_time": 144.0,
                    "keyframe_path": "keyframes/V048_P073_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        },
        {
            "place_id": "P073",
            "place_name": "전주향교",
            "region": "jeolla",
            "youtube_id": "lqS0xAtpKVQ",
            "source_url": "https://www.youtube.com/watch?v=lqS0xAtpKVQ",
            "segments": [
                {
                    "segment_id": "V048_P073_S002",
                    "start_time": 0.0,
                    "end_time": 46.0,
                    "keyframe_path": "keyframes/V048_P073_S002.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

# ====================================================
# 테마 (theme)
# ====================================================

THEME_TRADITIONAL_001 = {
    "video_id_prefix": "V051",
    "drama_title": "경복궁",
    "places": [
        {
            "place_id": "P016",
            "place_name": "경복궁",
            "region": "seoul",
            "youtube_id": "6OyPkPe5Le0",
            "source_url": "https://www.youtube.com/watch?v=6OyPkPe5Le0",
            "segments": [
                {
                    "segment_id": "V051_P016_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V051_P016_S001.jpg",
                    "season": "사계절",
                    "time_of_day": "낮",
                    "mood": ["웅장한", "고즈넉한", "운치있는"],
                    "scene_elements": ["궁궐", "전통건축"],
                    "k_culture_elements": ["한국 전통문화"],
                    "activity": ["관광", "산책"],
                    "description": "조선 왕조의 대표 궁궐인 경복궁의 고즈넉하고 웅장한 목조 건축 및 전각 풍경"
                }
            ]
        }
    ]
}

THEME_TRADITIONAL_002 = {
    "video_id_prefix": "V052",
    "drama_title": "전주 한옥마을",
    "places": [
        {
            "place_id": "P005",
            "place_name": "전주 한옥마을",
            "region": "jeolla",
            "youtube_id": "URa5-lfWhII",
            "source_url": "https://www.youtube.com/watch?v=URa5-lfWhII",
            "segments": [
                {
                    "segment_id": "V052_P005_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V052_P005_S001.jpg",
                    "season": "사계절",
                    "time_of_day": "낮",
                    "mood": ["정겨운", "고즈넉한", "아늑한"],
                    "scene_elements": ["한옥", "전통거리"],
                    "k_culture_elements": ["한국 전통문화"],
                    "activity": ["관광", "산책"],
                    "description": "고풍스러운 한옥 지붕과 돌담길이 이어지는 전주 한옥마을의 전통적인 골목 풍경"
                }
            ]
        }
    ]
}

THEME_TRADITIONAL_003 = {
    "video_id_prefix": "V053",
    "drama_title": "안동 하회마을",
    "places": [
        {
            "place_id": "P075",
            "place_name": "안동 하회마을",
            "region": "gyeongsang",
            "youtube_id": "Dw1hu5ADanI",
            "source_url": "https://www.youtube.com/watch?v=Dw1hu5ADanI",
            "segments": [
                {
                    "segment_id": "V053_P075_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V053_P075_S001.jpg",
                    "season": "사계절",
                    "time_of_day": "낮",
                    "mood": ["평화로운", "고즈넉한"],
                    "scene_elements": ["전통마을", "한옥"],
                    "k_culture_elements": ["한국 전통문화"],
                    "activity": ["관광", "산책"],
                    "description": "낙동강이 감싸 안은 유네스코 세계유산 안동 하회마을의 고즈넉한 한옥 경관"
                }
            ]
        }
    ]
}

THEME_TRADITIONAL_004 = {
    "video_id_prefix": "V054",
    "drama_title": "남산골한옥마을",
    "places": [
        {
            "place_id": "P076",
            "place_name": "남산골한옥마을",
            "region": "seoul",
            "youtube_id": "EPExT6UDYFs",
            "source_url": "https://www.youtube.com/watch?v=EPExT6UDYFs",
            "segments": [
                {
                    "segment_id": "V054_P076_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V054_P076_S001.jpg",
                    "season": "사계절",
                    "time_of_day": "낮",
                    "mood": ["고즈넉한", "아늑한"],
                    "scene_elements": ["한옥", "전통정원"],
                    "k_culture_elements": ["한국 전통문화"],
                    "activity": ["관광", "산책"],
                    "description": "도심 속에서 한국 전통 가옥의 아늑함과 분위기를 느낄 수 있는 남산골한옥마을"
                }
            ]
        }
    ]
}

THEME_TRADITIONAL_005 = {
    "video_id_prefix": "V055",
    "drama_title": "경주 교촌마을",
    "places": [
        {
            "place_id": "P077",
            "place_name": "경주 교촌마을",
            "region": "gyeongsang",
            "youtube_id": "2qkleu8Tl2w",
            "source_url": "https://www.youtube.com/watch?v=2qkleu8Tl2w",
            "segments": [
                {
                    "segment_id": "V055_P077_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V055_P077_S001.jpg",
                    "season": "사계절",
                    "time_of_day": "낮",
                    "mood": ["고즈넉한", "정겨운"],
                    "scene_elements": ["한옥", "전통마을"],
                    "k_culture_elements": ["한국 전통문화"],
                    "activity": ["관광", "산책"],
                    "description": "경주 최부자 고택과 돌담길이 조화를 이루는 고즈넉한 전통 한옥마을 풍경"
                }
            ]
        }
    ]
}

THEME_FIELD_001 = {
    "video_id_prefix": "V056",
    "drama_title": "고창 학원농장",
    "places": [
        {
            "place_id": "P004",
            "place_name": "고창 학원농장",
            "region": "jeolla",
            "youtube_id": "fznVy5NzqVI",
            "source_url": "https://www.youtube.com/watch?v=fznVy5NzqVI",
            "segments": [
                {
                    "segment_id": "V056_P004_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V056_P004_S001.jpg",
                    "season": "봄",
                    "time_of_day": "낮",
                    "mood": ["청량한", "푸르른", "탁트인"],
                    "scene_elements": ["들판", "농촌"],
                    "k_culture_elements": [],
                    "activity": ["관광", "산책"],
                    "description": "끝없이 펼쳐진 청보리밭과 메밀밭이 만들어내는 탁 트인 이국적인 농촌 경관"
                }
            ]
        }
    ]
}

THEME_FIELD_002 = {
    "video_id_prefix": "V057",
    "drama_title": "순천만습지",
    "places": [
        {
            "place_id": "P078",
            "place_name": "순천만습지",
            "region": "jeolla",
            "youtube_id": "cq9KDwdfhDc",
            "source_url": "https://www.youtube.com/watch?v=cq9KDwdfhDc",
            "segments": [
                {
                    "segment_id": "V057_P078_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V057_P078_S001.jpg",
                    "season": "가을",
                    "time_of_day": "낮",
                    "mood": ["서정적인", "웅장한", "운치있는"],
                    "scene_elements": ["갈대밭", "습지", "들판"],
                    "k_culture_elements": [],
                    "activity": ["관광", "산책"],
                    "description": "황금빛 갈대물결이 광활하게 펼쳐진 생태의 보고 순천만습지의 서정적인 풍경"
                }
            ]
        }
    ]
}

THEME_FIELD_003 = {
    "video_id_prefix": "V058",
    "drama_title": "보령 청라은행마을",
    "places": [
        {
            "place_id": "P079",
            "place_name": "보령 청라은행마을",
            "region": "chungcheong",
            "youtube_id": "n1zwfG5Zu70",
            "source_url": "https://www.youtube.com/watch?v=n1zwfG5Zu70",
            "segments": [
                {
                    "segment_id": "V058_P079_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V058_P079_S001.jpg",
                    "season": "가을",
                    "time_of_day": "낮",
                    "mood": ["따뜻한", "정겨운", "운치있는"],
                    "scene_elements": ["농촌", "들판", "은행나무"],
                    "k_culture_elements": [],
                    "activity": ["관광", "산책"],
                    "description": "마을 전체가 노랗게 물드는 은행나무 커뮤니티의 따뜻하고 정겨운 가을 풍경"
                }
            ]
        }
    ]
}

THEME_FIELD_004 = {
    "video_id_prefix": "V059",
    "drama_title": "하늘공원",
    "places": [
        {
            "place_id": "P080",
            "place_name": "하늘공원",
            "region": "seoul",
            "youtube_id": "j2oyUQiqy7g",
            "source_url": "https://www.youtube.com/watch?v=j2oyUQiqy7g",
            "segments": [
                {
                    "segment_id": "V059_P080_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V059_P080_S001.jpg",
                    "season": "가을",
                    "time_of_day": "낮",
                    "mood": ["탁트인", "낭만적인", "청량한"],
                    "scene_elements": ["억새밭", "초원"],
                    "k_culture_elements": [],
                    "activity": ["관광", "산책"],
                    "description": "도심 정상부에서 한강과 함께 은빛 억새물결이 일렁이는 탁 트인 생태공원"
                }
            ]
        }
    ]
}

THEME_FIELD_005 = {
    "video_id_prefix": "V060",
    "drama_title": "황매산 억새평원",
    "places": [
        {
            "place_id": "P081",
            "place_name": "황매산 억새평원",
            "region": "gyeongsang",
            "youtube_id": "6YDTLJcvX8g",
            "source_url": "https://www.youtube.com/watch?v=6YDTLJcvX8g",
            "segments": [
                {
                    "segment_id": "V060_P081_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V060_P081_S001.jpg",
                    "season": "가을",
                    "time_of_day": "낮",
                    "mood": ["웅장한", "신비로운", "탁트인"],
                    "scene_elements": ["억새", "초원", "산"],
                    "k_culture_elements": [],
                    "activity": ["관광", "산책"],
                    "description": "산 능선을 따라 광활하게 펼쳐진 은빛 억새와 탁 트인 산세가 자아내는 웅장한 자연 경관"
                }
            ]
        }
    ]
}

SAEMANGEUM_DRIVE = {
    "video_id_prefix": "V061",
    "drama_title": "새만금방조제·고군산군도 드라이브",
    "places": [
        {
            "place_id": "P082",
            "place_name": "새만금방조제·고군산군도 드라이브",
            "region": "jeolla",
            "youtube_id": "KbLnPZ7DdPQ",
            "source_url": "https://www.youtube.com/watch?v=KbLnPZ7DdPQ",
            "segments": [
                {
                    "segment_id": "V061_P082_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V061_P082_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

BUKHANGANG_ROAD = {
    "video_id_prefix": "V062",
    "drama_title": "북한강길",
    "places": [
        {
            "place_id": "P083",
            "place_name": "북한강길",
            "region": "gyeonggi",
            "youtube_id": "Q8rcwJ2I5GM",
            "source_url": "https://www.youtube.com/watch?v=Q8rcwJ2I5GM",
            "segments": [
                {
                    "segment_id": "V062_P083_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V062_P083_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

GWACHEON_GINKGO_ROAD = {
    "video_id_prefix": "V063",
    "drama_title": "과천 교육원로·관문로 은행나무길",
    "places": [
        {
            "place_id": "P084",
            "place_name": "과천 교육원로·관문로 은행나무길",
            "region": "gyeonggi",
            "youtube_id": "YKXwHtx-ZeQ",
            "source_url": "https://www.youtube.com/watch?v=YKXwHtx-ZeQ",
            "segments": [
                {
                    "segment_id": "V063_P084_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V063_P084_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

JONGDALRI_HYDRANGEA_ROAD = {
    "video_id_prefix": "V064",
    "drama_title": "종달리 수국길",
    "places": [
        {
            "place_id": "P085",
            "place_name": "종달리 수국길",
            "region": "jeju",
            "youtube_id": "EGqlMO-gT4Y",
            "source_url": "https://www.youtube.com/watch?v=EGqlMO-gT4Y",
            "segments": [
                {
                    "segment_id": "V064_P085_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V064_P085_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

SINCHANG_WINDMILL_COASTAL_ROAD = {
    "video_id_prefix": "V065",
    "drama_title": "신창풍차해안도로",
    "places": [
        {
            "place_id": "P086",
            "place_name": "신창풍차해안도로",
            "region": "jeju",
            "youtube_id": "6WP8sOqHwSc",
            "source_url": "https://www.youtube.com/watch?v=6WP8sOqHwSc",
            "segments": [
                {
                    "segment_id": "V065_P086_S001",
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "keyframe_path": "keyframes/V065_P086_S001.jpg",
                    "season": "",
                    "time_of_day": "",
                    "mood": [],
                    "scene_elements": [],
                    "k_culture_elements": [],
                    "activity": [],
                    "description": ""
                }
            ]
        }
    ]
}

# ====================================================
# 0. 설정 및 표준 태그 풀(Pool) 정의
# ====================================================
VISION_MODEL = "llava"

VALID_MOODS = Literal[
    "청량한", "푸르른", "웅장한", "탁트인", "평화로운", "운치있는", 
    "세련된", "모던한", "화려한", "활기찬", "아늑한", "낭만적인", 
    "서정적인", "신비로운", "정겨운", "따뜻한", "고즈넉한", "아름다운"
]

VALID_K_CULTURE = Literal[
    "K드라마성지", "드라마촬영지", "한옥체험", "K푸드", "길거리음식",
    "전통시장", "한복체험", "K팝성지", "포토존", "성지순례",
    "야경명소", "복합문화공간", "골목길투어", "전통문화", "로컬맛집",
    "카페거리", "감성스팟", "역사탐방", "지역축제", "쇼핑명소"
]

VALID_ACTIVITIES = Literal[
    "산책", "야경감상", "사진촬영", "명소탐방", "드라이브", "데이트", 
    "피크닉", "카페투어", "자전거타기", "휴식", "문화체험", "식도락"
]

VALID_SEASONS = Literal["봄", "여름", "가을", "겨울", "사계절"]
VALID_TIME_OF_DAY = Literal["오전", "오후", "저녁", "밤"]

# 🚫 시스템 단어 및 자막 예외 문구 블랙리스트
BANNED_KEYWORDS = [
    "화면", "이미지", "자막", "대사", "드라마", "영상", "캡처", "사진",
    "데이터", "음성"
]

BANNED_DESC_PHRASES = [
    "자막 데이터 없음", "대사 내용 자막 데이터 없음", "실제 음성자막",
    "화면 이미지", "자막 데이터", "대사 내용"
]

# ====================================================
# 1. 반환받을 JSON 구조 정의 (Pydantic Schema)
# ====================================================
class SegmentMetadata(BaseModel):
    mood: List[VALID_MOODS] = Field(description="제시된 분위기 항목 중 1~3개 선택")
    scene_elements: List[str] = Field(description="화면에 보이는 시각적 사물/풍경 명소 (명사)")
    k_culture_elements: List[VALID_K_CULTURE] = Field(description="제시된 K-컬처/관광 키워드 중 1~3개 선택")
    activity: List[VALID_ACTIVITIES] = Field(description="제시된 관광 활동 중 1~3개 선택")
    season: List[VALID_SEASONS] = Field(description="화면 속 풍경과 장소에 어울리는 계절 선택")
    time_of_day: List[VALID_TIME_OF_DAY] = Field(description="화면 속 풍경의 시간대 선택 (오전, 오후, 저녁, 밤 중 1~2개 선택)")
    description: str = Field(description="장면 및 장소에 대한 1-2문장의 요약 설명")

    # 🛡️ LLM이 지정된 목록 외의 단어를 생성했을 때 자동으로 허용 목록만 남김
    @field_validator('mood', mode='before')
    def filter_mood(cls, v):
        if isinstance(v, list):
            valid_set = set(get_args(VALID_MOODS))
            return [item for item in v if item in valid_set]
        return v

    @field_validator('k_culture_elements', mode='before')
    def filter_k_culture(cls, v):
        if isinstance(v, list):
            valid_set = set(get_args(VALID_K_CULTURE))
            return [item for item in v if item in valid_set]
        return v

    @field_validator('activity', mode='before')
    def filter_activity(cls, v):
        if isinstance(v, list):
            valid_set = set(get_args(VALID_ACTIVITIES))
            return [item for item in v if item in valid_set]
        return v

    @field_validator('season', mode='before')
    def filter_season(cls, v):
        valid_set = set(get_args(VALID_SEASONS))
        if isinstance(v, list):
            return [item for item in v if item in valid_set]
        elif isinstance(v, str):
            return [v] if v in valid_set else []
        return v

    @field_validator('time_of_day', mode='before')
    def filter_time_of_day(cls, v):
        valid_set = set(get_args(VALID_TIME_OF_DAY))
        if isinstance(v, list):
            return [item for item in v if item in valid_set]
        elif isinstance(v, str):
            return [v] if v in valid_set else []
        return v

# ====================================================
# 2. 유틸리티 함수 (캡처, 자막 추출, 텍스트 정제, 저장)
# ====================================================
def capture_youtube_frame(youtube_id: str, target_time: float, output_path: str) -> bool:
    try:
        dir_name = os.path.dirname(output_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
            
        youtube_url = f"https://www.youtube.com/watch?v={youtube_id}"
        
        # 1차 시도: yt-dlp CLI로 1프레임 추출
        cmd = [
            sys.executable, '-m', 'yt_dlp',
            '--ss', str(target_time),
            '-f', 'bestvideo[ext=mp4]/best[ext=mp4]/best',
            '--frames', '1',
            '-o', output_path,
            '--no-warnings',
            youtube_url
        ]
        
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True

        # 2차 시도: OpenCV FFMPEG 사용
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        stream_url = None
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            if info:
                stream_url = info.get('url')

        if not stream_url:
            return False

        cap = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)
        try:
            if not cap.isOpened():
                return False

            cap.set(cv2.CAP_PROP_POS_MSEC, target_time * 1000)
            ret, frame = cap.read()
            
            if ret and frame is not None:
                cv2.imwrite(output_path, frame)
                return True
        finally:
            cap.release()
            
        return False
        
    except Exception as e:
        print(f" (캡처 오류: {e})", end="")
        return False

def get_segment_transcript(youtube_id: str, start_time: float, end_time: float) -> str:
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(
            youtube_id, 
            languages=['ko', 'en']
        )
        
        script_texts = []
        for item in transcript_list:
            item_end = item['start'] + item.get('duration', 0)
            
            if start_time == 0.0 and end_time == 0.0:
                script_texts.append(item['text'])
            else:
                if item_end >= start_time and item['start'] <= end_time:
                    script_texts.append(item['text'])
        
        full_script = " ".join(script_texts).strip()
        return full_script if full_script else "자막 데이터 없음"
    except Exception:
        return "자막 데이터 없음"

def clean_to_pure_korean(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r'[^가-힣0-9\s]', ' ', text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def is_clean_scene_element(element: str) -> bool:
    cleaned = clean_to_pure_korean(element)
    if not cleaned:
        return False
    
    for banned in BANNED_KEYWORDS:
        if banned in cleaned:
            return False
            
    return True

def remove_duplicates(lst: list) -> list:
    return list(dict.fromkeys(lst))

def save_checkpoint_atomic(data: list, filepath: str):
    """임시 파일에 작성 후 덮어쓰는 안전한 Atomic 중간 저장 방식"""
    temp_filepath = f"{filepath}.tmp"
    with open(temp_filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    os.replace(temp_filepath, filepath)

# ====================================================
# 3. Vision 태깅 함수
# ====================================================
def auto_tag_segment_vision(drama_title: str, place_name: str, region: str, script: str, keyframe_path: str = None) -> SegmentMetadata:
    prompt = f"""
    당신은 K-콘텐츠 관광 메타데이터 구축 전문가입니다.
    제공된 이미지와 정보를 종합하여 정확한 JSON 객체를 생성하세요.

    [기본 정보]
    - 드라마 제목: {drama_title}
    - 촬영 장소명: {place_name} ({region})
    - 대사 내용: "{script}"

    [필수 스키마 및 선택 항목 규칙]
    1. mood: ["청량한", "푸르른", "웅장한", "탁트인", "평화로운", "운치있는", "세련된", "모던한", "화려한", "활기찬", "아늑한", "낭만적인", "서정적인", "신비로운", "정겨운", "따뜻한", "고즈넉한", "아름다운"] 중 1~3개 선택 (리스트 형태)
    2. k_culture_elements: ["K드라마성지", "드라마촬영지", "한옥체험", "K푸드", "길거리음식", "전통시장", "한복체험", "K팝성지", "포토존", "성지순례", "야경명소", "복합문화공간", "골목길투어", "전통문화", "로컬맛집", "카페거리", "감성스팟", "역사탐방", "지역축제", "쇼핑명소"] 중 1~3개 선택 (리스트 형태)
    3. activity: ["산책", "야경감상", "사진촬영", "명소탐방", "드라이브", "데이트", "피크닉", "카페투어", "자전거타기", "휴식", "문화체험", "식도락"] 중 1~3개 선택 (리스트 형태)
    4. season: ["봄", "여름", "가을", "겨울", "사계절"] 중 1개 선택 (반드시 리스트 형태 [ "여름" ])
    5. time_of_day: ["오전", "오후", "저녁", "밤"] 중 1~2개 선택 (리스트 형태)
       - 오전: 산뜻한 아침 햇살
       - 오후: 강렬한 낮 햇빛, 또렷한 그림자
       - 저녁: 노을, 일몰, 붉은색/주황색 하늘
       - 밤: 어두운 배경, 인공 조명 위주
    6. scene_elements: 화면에 직접 보이는 시각적 사물 및 자연 풍경 명사 리스트 ('화면', '이미지', '자막' 단어 금지)
    7. description: 장소와 분위기를 설명하는 1~2문장의 완결된 한글 요약문

    응답은 오직 지정된 JSON 객체 형태이어야 합니다.
    """

    message_payload = {
        'role': 'user',
        'content': prompt
    }

    if keyframe_path and os.path.exists(keyframe_path):
        message_payload['images'] = [keyframe_path]
        print(f" [🖼️ 이미지 전달됨]", end="")
    else:
        print(f" [⚠️ 텍스트 전용 추론]", end="")

    response = ollama.chat(
        model=VISION_MODEL,
        messages=[message_payload],
        format="json",
        options={
            'temperature': 0.2, 
            'top_p': 0.9,
            'num_predict': 1536,
            'seed': 42
        }
    )

    raw_content = response['message']['content']

    # 마크다운 블록 기호 제거 및 JSON 정제 파싱
    clean_content = re.sub(r'```json\s*|\s*```', '', raw_content).strip()
    json_match = re.search(r'\{.*\}', clean_content, re.DOTALL)
    clean_json_str = json_match.group(0).strip() if json_match else clean_content

    # 💡 Pydantic 검증 로직 보완 (JSON 파싱 fallback 추가)
    try:
        return SegmentMetadata.model_validate_json(clean_json_str)
    except Exception:
        try:
            # 1차 구원: json.loads로 딕셔너리 변환 후 전달
            parsed_dict = json.loads(clean_json_str)
            return SegmentMetadata.model_validate(parsed_dict)
        except Exception:
            # 2차 구원: 닫는 괄호 보완
            fixed = clean_json_str
            if not fixed.endswith("}"):
                if not fixed.endswith('"'):
                    fixed += '"'
                fixed += "}"
            return SegmentMetadata.model_validate_json(fixed)

# ====================================================
# 4. 전체 드라마 데이터 처리 실행 (체크포인트 저장)
# ====================================================
if __name__ == "__main__":
    all_videos = [
        LOVESTRUCK_IN_THE_CITY,
        CASTAWAY_DIVA,
        WHEN_THE_WEATHER_IS_FINE,
        KINGDOM,
        WHEN_LIFE_GIVES_YOU_TANGERINES,
        LITTLE_FOREST,
        CRASH_LANDING_ON_YOU,
        LOVELY_RUNNER_BY_PLACE,
        VINCENZO,
        ITAEWON_CLASS,
        STRANGERS,
        NOW_WE_ARE_BREAKING_UP,
        MY_NAME,
        DECISION_TO_LEAVE,
        TWENTYTH_CENTURY_GIRL,
        DESTINED_WITH_YOU,
        HOMETOWN_CHA_CHA_CHA,
        OUR_BLUES,
        GOBLIN,
        HOTEL_DEL_LUNA,
        ARCHITECTURE_101,
        WHEN_THE_CAMELLIA_BLOOMS,
        HAEUNDAE,
        AUTUMN_IN_MY_HEART,
        PARASITE,
        BOYFRIEND,
        REVENANT,
        TWENTY_FIVE_TWENTY_ONE,
        EXTRAORDINARY_ATTORNEY_WOO,
        LIGHT_SHOP,
        THE_GLORY,
        MY_SASSY_GIRL,
        SOMETHING_IN_THE_RAIN,
        KINGDOM2,
        OKJA,
        THE_BATTLESHIP_ISLAND,
        MR_SUNSHINE,
        OUR_BELOVED_SUMMER,
        LOVE_RAIN,
        WINTER_SONATA,
        THE_RED_STAINED_SLEEVE_CUFF,
        TRACES_OF_LOVE,
        THE_KINGS_AFFECTION,
        THEME_TRADITIONAL_001,
        THEME_TRADITIONAL_002,
        THEME_TRADITIONAL_003,
        THEME_TRADITIONAL_004,
        THEME_TRADITIONAL_005,
        THEME_FIELD_001,
        THEME_FIELD_002,
        THEME_FIELD_003,
        THEME_FIELD_004,
        THEME_FIELD_005,
        SAEMANGEUM_DRIVE,
        BUKHANGANG_ROAD,
        GWACHEON_GINKGO_ROAD,
        JONGDALRI_HYDRANGEA_ROAD,
        SINCHANG_WINDMILL_COASTAL_ROAD
    ]

    total_dramas = len(all_videos)
    output_filename = "drama_video_data_tagged.json"

    print(f"🚀 총 {total_dramas}개의 드라마 데이터 자동 태깅 시작 (Vision 모델: {VISION_MODEL})\n")

    for drama_idx, drama in enumerate(all_videos, 1):
        title = drama.get("drama_title", "제목 없음")
        places = drama.get("places", [])
        
        print(f"[{drama_idx}/{total_dramas}] 드라마: '{title}' (장소 {len(places)}개 처리 시작)")
        
        for place_idx, place in enumerate(places, 1):
            p_name = place.get("place_name", "장소명 없음")
            region = place.get("region", "지역 없음")
            yt_id = place.get("youtube_id", "")
            segments = place.get("segments", [])
            
            print(f"  └─ ({place_idx}/{len(places)}) [{p_name}] - 총 {len(segments)}개 구간 태깅 시작...")
            
            for seg_idx, seg in enumerate(segments, 1):
                start = seg.get("start_time", 0.0)
                end = seg.get("end_time", 0.0)
                keyframe_path = seg.get("keyframe_path", f"keyframes/{yt_id}_{seg_idx}.jpg")
                
                # 이미지가 없으면 유튜브에서 자동 캡처
                if not os.path.exists(keyframe_path):
                    if start == 0.0 and end == 0.0:
                        mid_time = 3.0
                    else:
                        mid_time = (start + end) / 2.0
                        
                    print(f"\n    └─ 📸 키프레임 자동 캡처 중 ({mid_time:.1f}초 시점)...", end="", flush=True)
                    captured = capture_youtube_frame(yt_id, mid_time, keyframe_path)
                    if captured:
                        print(" 성공!", end="")
                    else:
                        print(" 실패!", end="")

                script = get_segment_transcript(yt_id, start, end)
                print(f"    └─ 구간 [{seg_idx}/{len(segments)}] ({start}초~{end}초) 비전 분석 중...", end="", flush=True)
                
                max_retries = 3
                success = False
                generated_tags = None
                
                for attempt in range(max_retries):
                    try:
                        generated_tags = auto_tag_segment_vision(
                            drama_title=title, 
                            place_name=p_name, 
                            region=region, 
                            script=script,
                            keyframe_path=keyframe_path
                        )
                        success = True
                        break
                    except Exception as e:
                        if attempt < max_retries - 1:
                            print(f" (재시도 {attempt+1}/{max_retries})...", end="", flush=True)
                        else:
                            print(f" -> ⚠️ 최종 오류: {e}")

                if not success or not generated_tags:
                    print(" -> ⚠️ 분석 실패 (기본 표준 값 적용)")
                    seg["mood"] = ["아름다운"]
                    seg["scene_elements"] = [clean_to_pure_korean(p_name)] if p_name else ["촬영지"]
                    seg["k_culture_elements"] = ["K드라마성지"]
                    seg["activity"] = ["산책", "사진촬영"]
                    seg["season"] = ["사계절"]
                    seg["time_of_day"] = ["오후"]
                    seg["description"] = f"{p_name} 관련 드라마 촬영 장면입니다."
                    continue

                seg["mood"] = remove_duplicates(generated_tags.mood)
                seg["k_culture_elements"] = remove_duplicates(generated_tags.k_culture_elements)
                seg["activity"] = remove_duplicates(generated_tags.activity)
                seg["season"] = remove_duplicates(generated_tags.season)
                seg["time_of_day"] = remove_duplicates(generated_tags.time_of_day)
                
                seg["scene_elements"] = remove_duplicates([
                    clean_to_pure_korean(s) for s in generated_tags.scene_elements 
                    if is_clean_scene_element(s)
                ])

                pure_p_name = clean_to_pure_korean(p_name)
                if not seg["mood"]:
                    seg["mood"] = ["아름다운"]
                if not seg["scene_elements"]:
                    seg["scene_elements"] = [pure_p_name] if pure_p_name else ["풍경"]
                if not seg["k_culture_elements"]:
                    seg["k_culture_elements"] = ["K드라마성지"]
                if not seg["activity"]:
                    seg["activity"] = ["산책", "사진촬영"]
                if not seg["season"]:
                    seg["season"] = ["사계절"]
                if not seg["time_of_day"]:
                    seg["time_of_day"] = ["오후"]

                clean_desc = generated_tags.description.replace("\n", " ").strip()
                for phrase in BANNED_DESC_PHRASES:
                    clean_desc = clean_desc.replace(phrase, "")
                
                clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()
                seg["description"] = clean_desc if clean_desc else f"{p_name} 관련 드라마 촬영 장면입니다."
                
                print(" -> 정확히 완료! ✅")

        # 드라마 1개 완료될 때마다 안전하게 아토믹 덮어쓰기 저장
        save_checkpoint_atomic(all_videos, output_filename)
        print(f"  💾 [{title}] 처리 완료 및 중간 파일 저장 완료!\n")

    print("\n--------------------------------------------------")
    print("✅ 모든 태그 작업 완료 및 최종 파일 저장 완료!")
    print(f"💾 최종 결과 저장 위치: '{output_filename}'")