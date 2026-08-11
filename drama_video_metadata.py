import sys
import io
import os
import re
import json
import subprocess
from typing import Literal
from pydantic import BaseModel, Field
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
    print("⚠️ 'imageio-ffmpeg' 모듈이 없습니다. 터미널에서 'pip install imageio-ffmpeg'를 실행하세요.")

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

# 🚫 시스템 단어 및 자막 예외 문구 블랙리스트
BANNED_KEYWORDS = {
    "화면", "이미지", "화면 이미지", "실제 음성자막", "음성자막", 
    "자막", "대사", "드라마", "영상", "캡처", "사진",
    "자막 데이터 없음", "대사 내용 자막 데이터 없음", "자막 데이터", "대사 내용", "데이터"
}

# 문장(description) 세척용 구문 레벨 블랙리스트
BANNED_DESC_PHRASES = [
    "자막 데이터 없음", "대사 내용 자막 데이터 없음", "실제 음성자막",
    "화면 이미지", "자막 데이터", "대사 내용"
]

# ====================================================
# 1. 반환받을 JSON 구조 정의 (Pydantic Schema)
# ====================================================
class SegmentMetadata(BaseModel):
    mood: list[VALID_MOODS] = Field(description="제시된 분위기 항목 중 1~3개 선택")
    scene_elements: list[str] = Field(description="화면에 보이는 시각적 사물/풍경 명소 (명사)")
    k_culture_elements: list[VALID_K_CULTURE] = Field(description="제시된 K-컬처/관광 키워드 중 1~3개 선택")
    activity: list[VALID_ACTIVITIES] = Field(description="제시된 관광 활동 중 1~3개 선택")
    season: list[VALID_SEASONS] = Field(description="화면 속 풍경과 장소에 어울리는 계절 선택")
    description: str = Field(description="장면 및 장소에 대한 1-2문장의 요약 설명")

# ====================================================
# 2. 유튜브 키프레임 자동 캡처 함수
# ====================================================
def capture_youtube_frame(youtube_id: str, target_time: float, output_path: str) -> bool:
    try:
        dir_name = os.path.dirname(output_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
            
        youtube_url = f"https://www.youtube.com/watch?v={youtube_id}"
        
        # 1차 시도: python -m yt_dlp CLI로 1프레임 즉시 추출
        cmd = [
            sys.executable, '-m', 'yt_dlp',
            '--ss', str(target_time),
            '-f', 'bestvideo[ext=mp4]/best[ext=mp4]/best',
            '--frames', '1',
            '-o', output_path,
            '--no-warnings',
            youtube_url
        ]
        
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True

        # 2차 시도: yt-dlp 파이썬 API로 URL 추출 후 OpenCV FFMPEG 백엔드 사용
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            stream_url = info.get('url')

        if not stream_url:
            return False

        cap = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            return False

        cap.set(cv2.CAP_PROP_POS_MSEC, target_time * 1000)
        ret, frame = cap.read()
        
        if ret and frame is not None:
            cv2.imwrite(output_path, frame)
            cap.release()
            return True
            
        cap.release()
        return False
        
    except Exception as e:
        print(f" (캡처 오류: {e})", end="")
        return False

# ====================================================
# 3. 텍스트 세척 및 자막 추출 함수
# ====================================================
def get_segment_transcript(youtube_id: str, start_time: float, end_time: float) -> str:
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(
            youtube_id, 
            languages=['ko', 'en']
        )
        
        script_texts = []
        for item in transcript_list:
            item_end = item['start'] + item.get('duration', 0)
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

def remove_duplicates(lst: list) -> list:
    return list(dict.fromkeys(lst))

# ====================================================
# 4. Ollama Vision 멀티모달 자동 태깅 함수
# ====================================================
def auto_tag_segment_vision(drama_title: str, place_name: str, region: str, script: str, keyframe_path: str = None) -> SegmentMetadata:
    prompt = f"""
    당신은 K-콘텐츠 관광 메타데이터 구축 전문가입니다.
    촬영 장소의 풍경과 대사 맥락, 그리고 장소의 특성을 종합 분석하여 관광 메타데이터를 작성하세요.

    - 드라마 제목: {drama_title}
    - 촬영 장소명: {place_name} ({region})
    - 대사 내용: "{script}"

    [🚨 필수 규칙]
    1. mood, k_culture_elements, activity, season 항목은 반드시 지정된 JSON Schema의 선택지(Literal) 목록 안에서만 골라 작성하세요.
       - 임의의 다른 단어나 생소한 단어를 절대로 만들어내지 마세요.
    2. 모든 항목은 절대로 빈 리스트로 남기지 말고 최소 1개 이상 선택하세요.
    3. scene_elements: 화면에 직접 보이는 사물, 건물, 풍경 등의 명사만 추출하세요. (예: 한옥, 돌담길, 바다, 카페 등)
       - 절대로 '화면', '이미지', '자막', '대사', '자막 데이터 없음' 같은 표현을 포함하지 마세요.
    4. description: 장소와 분위기를 설명하는 1~2문장의 완결된 한글 요약문으로 작성하세요.
    5. 이모지, 특수문자, 영어를 사용하지 마세요. 모든 필드의 값은 반드시 한국어로 작성하세요.
    """

    message_payload = {
        'role': 'user',
        'content': prompt
    }

    if keyframe_path and os.path.exists(keyframe_path):
        message_payload['images'] = [keyframe_path]
        print(f" [🖼️ 이미지 전달됨: {keyframe_path}]", end="")
    else:
        print(f" [⚠️ 이미지 없음! 텍스트로만 추론 중 (경로: {keyframe_path})]", end="")

    response = ollama.chat(
        model=VISION_MODEL,
        messages=[message_payload],
        format=SegmentMetadata.model_json_schema(),
        options={
            'temperature': 0.3, 
            'top_p': 0.9,
            'num_predict': 1024,
            'seed': 42
        }
    )

    raw_content = response['message']['content']

    json_match = re.search(r'\{.*\}', raw_content, re.DOTALL)
    if json_match:
        clean_json_str = json_match.group(0).strip()
    else:
        clean_json_str = raw_content.strip()

    try:
        return SegmentMetadata.model_validate_json(clean_json_str)
    except Exception:
        fixed = clean_json_str
        if not fixed.endswith("}"):
            if not fixed.endswith('"'):
                fixed += '"'
            fixed += "}"
        return SegmentMetadata.model_validate_json(fixed)

# ====================================================
# 5. 전체 드라마 데이터 처리 실행
# ====================================================
all_dramas = [
    LOVELY_RUNNER_BY_PLACE,
    WHEN_LIFE_GIVES_YOU_TANGERINES,
    OUR_BELOVED_SUMMER,
    TWENTY_FIVE_TWENTY_ONE,
    HOMETOWN_CHA_CHA_CHA,
    OUR_BLUES,
    CRASH_LANDING_ON_YOU,
    GOBLIN,
    HOTEL_DEL_LUNA,
    KINGDOM,
    WHEN_THE_WEATHER_IS_FINE,
    CASTAWAY_DIVA,
    LOVESTRUCK_IN_THE_CITY
]

total_dramas = len(all_dramas)
print(f"🚀 총 {total_dramas}개의 드라마 데이터 자동 태깅 시작 (Vision 모델: {VISION_MODEL})\n")

for drama_idx, drama in enumerate(all_dramas, 1):
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
                seg["description"] = f"{p_name} 관련 드라마 촬영 장면입니다."
                continue

            seg["mood"] = remove_duplicates(generated_tags.mood)
            seg["k_culture_elements"] = remove_duplicates(generated_tags.k_culture_elements)
            seg["activity"] = remove_duplicates(generated_tags.activity)
            seg["season"] = remove_duplicates(generated_tags.season)
            
            seg["scene_elements"] = remove_duplicates([
                clean_to_pure_korean(s) for s in generated_tags.scene_elements 
                if clean_to_pure_korean(s) and clean_to_pure_korean(s) not in BANNED_KEYWORDS
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

            clean_desc = generated_tags.description.replace("\n", " ").strip()
            for phrase in BANNED_DESC_PHRASES:
                clean_desc = clean_desc.replace(phrase, "")
            
            clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()
            seg["description"] = clean_desc if clean_desc else f"{p_name} 관련 드라마 촬영 장면입니다."
            
            print(" -> 정확히 완료! ✅")

print("\n--------------------------------------------------")
print("✅ 모든 태그 작업 완료!")

# ====================================================
# 6. 저장
# ====================================================
output_filename = "drama_video_data_tagged.json"

with open(output_filename, "w", encoding="utf-8") as f:
    json.dump(all_dramas, f, ensure_ascii=False, indent=4)

print(f"💾 결과가 '{output_filename}' 파일로 깔끔하게 저장되었습니다.")