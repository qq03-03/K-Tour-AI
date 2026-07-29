import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

import json
from pydantic import BaseModel, Field
import ollama
from youtube_transcript_api import YouTubeTranscriptApi
import urllib.request
import re

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
                    "season": "봄", # 봄, 여름, 가을, 겨울, 사계절
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
                    "season": "봄",
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
                    "season": "봄",
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
                    "season": "봄",
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
                    "season": "봄",
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
                    "season": "봄",
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
                    "season": "가을",
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
                    "season": "여름, 가을, 겨울",
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
                    "season": "여름, 가을",
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
                    "season": "가을",
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
                    "season": "여름",
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
                    "season": "여름",
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
                    "season": "여름",
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
                    "season": "봄, 여름, 가을, 겨울",
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
            "place_name": "포항",
            "region": "gyeongsang",
            "youtube_id": "UjxY3jz0znE",
            "source_url": "https://www.youtube.com/watch?v=UjxY3jz0znE",
            "segments": [
                {
                    "segment_id": "V005_P010_S001",
                    "start_time": 305.0,
                    "end_time": 430.0,
                    "keyframe_path": "keyframes/V005_P010_S001.jpg",
                    "season": "여름",
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
            "place_id": "P010",
            "place_name": "포항",
            "region": "gyeongsang",
            "youtube_id": "ch9bdaofYxM",
            "source_url": "https://www.youtube.com/watch?v=ch9bdaofYxM",
            "segments": [
                {
                    "segment_id": "V005_P010_S002",
                    "start_time": 0.0,
                    "end_time": 179.0,
                    "keyframe_path": "keyframes/V005_P010_S002.jpg",
                    "season": "여름",
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
            "place_id": "P010",
            "place_name": "포항",
            "region": "gyeongsang",
            "youtube_id": "wi11R_vDBmE",
            "source_url": "https://www.youtube.com/watch?v=wi11R_vDBmE",
            "segments": [
                {
                    "segment_id": "V005_P010_S003",
                    "start_time": 0.0,
                    "end_time": 29.0,
                    "keyframe_path": "keyframes/V005_P010_S003.jpg",
                    "season": "여름",
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
            "place_name": "제주도",
            "region": "jeju",
            "youtube_id": "1r7a5mLNGRQ",
            "source_url": "https://www.youtube.com/watch?v=1r7a5mLNGRQ",
            "segments": [
                {
                    "segment_id": "V006_P011_S001",
                    "start_time": 0.0,
                    "end_time": 81.0,
                    "keyframe_path": "keyframes/V006_P011_S001.jpg",
                    "season": "여름",
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
            "place_id": "P011",
            "place_name": "제주도",
            "region": "jeju",
            "youtube_id": "Oeme18IdNzw",
            "source_url": "https://www.youtube.com/watch?v=Oeme18IdNzw",
            "segments": [
                {
                    "segment_id": "V006_P011_S002",
                    "start_time": 0.0,
                    "end_time": 11.0,
                    "keyframe_path": "keyframes/V006_P011_S002.jpg",
                    "season": "여름",
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
            "place_id": "P011",
            "place_name": "제주도",
            "region": "jeju",
            "youtube_id": "e6FvfWF4uVg",
            "source_url": "https://www.youtube.com/watch?v=e6FvfWF4uVg",
            "segments": [
                {
                    "segment_id": "V006_P011_S003",
                    "start_time": 118.0,
                    "end_time": 298.0,
                    "keyframe_path": "keyframes/V006_P011_S003.jpg",
                    "season": "봄, 여름",
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
            "place_id": "P011",
            "place_name": "제주도",
            "region": "jeju",
            "youtube_id": "Lb3DGOdPafU",
            "source_url": "https://www.youtube.com/watch?v=Lb3DGOdPafU",
            "segments": [
                {
                    "segment_id": "V006_P011_S004",
                    "start_time": 0.0,
                    "end_time": 15.0,
                    "keyframe_path": "keyframes/V006_P011_S004.jpg",
                    "season": "봄, 여름",
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
            "place_id": "P011",
            "place_name": "제주도",
            "region": "jeju",
            "youtube_id": "fr03aYy-ZfI",
            "source_url": "https://www.youtube.com/watch?v=fr03aYy-ZfI",
            "segments": [
                {
                    "segment_id": "V006_P011_S005",
                    "start_time": 0.0,
                    "end_time": 406.0,
                    "keyframe_path": "keyframes/V006_P011_S005.jpg",
                    "season": "봄, 여름",
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
                    "season": "봄",
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
                    "season": "겨울",
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
                    "season": "가을, 겨울",
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
                    "season": "가을, 겨울",
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
                    "season": "겨울",
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
                    "season": "겨울",
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
                    "season": "봄, 여름",
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
                    "season": "봄, 여름, 가을, 겨울",
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
                    "season": "봄, 여름, 가을, 겨울",
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
                    "season": "봄, 여름, 가을, 겨울",
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
                    "season": "봄, 여름, 가을, 겨울",
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
                    "season": "봄, 여름, 가을, 겨울",
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
                    "season": "겨울",
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
                    "season": "겨울",
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
                    "season": "겨울",
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
                    "season": "봄, 여름",
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
            "place_id": "P019",
            "place_name": "상주 경천섬 공원",
            "region": "gyeongsang",
            "youtube_id": "n6_TzBPBYUU",
            "source_url": "https://www.youtube.com/watch?v=n6_TzBPBYUU",
            "segments": [
                {
                    "segment_id": "V013_P019_S002",
                    "start_time": 0.0,
                    "end_time": 17.0,
                    "keyframe_path": "keyframes/V013_P019_S002.jpg",
                    "season": "봄, 여름",
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
                    "season": "봄, 여름",
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
                    "season": "봄, 여름, 가을, 겨울",
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

# ====================================================
# 2. 반환받을 JSON 구조 정의 (Pydantic Schema)
# ====================================================
class SegmentMetadata(BaseModel):
    mood: list[str] = Field(description="장면의 분위기를 나타내는 형용사 목록 (예: 고즈넉한, 청량한, 세련된 등)")
    scene_elements: list[str] = Field(description="화면에 등장하는 시각적 요소 목록 (예: 한옥, 돌담길, 바다 등)")
    k_culture_elements: list[str] = Field(description="한국 고유의 문화적/관광적 경험 키워드 (예: 한복, K-드라이브, 포장마차 등)")
    activity: list[str] = Field(description="관광객이 직접 할 수 있는 활동 (예: 산책, 야경 감상, 사진 촬영 등)")
    description: str = Field(description="장면 및 장소에 대한 1-2문장의 요약 설명")

def get_segment_transcript(youtube_id: str, start_time: float, end_time: float) -> str:
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(
            youtube_id, 
            languages=['ko', 'en']
        )
        
        script_texts = []
        for item in transcript_list:
            if start_time <= item['start'] <= end_time:
                script_texts.append(item['text'])
        
        full_script = " ".join(script_texts).strip()
        return full_script if full_script else "자막 데이터 없음"
    except Exception:
        return "자막 데이터 없음"

# ====================================================
# 3. Ollama 로컬 LLM을 활용한 자동 태깅 함수
# ====================================================
def auto_tag_segment(drama_title: str, place_name: str, region: str, script: str) -> SegmentMetadata:
    prompt = f"""
    당신은 K-콘텐츠 관광 메타데이터 구축 전문가입니다.
    다음 드라마 정보와 '실제 음성 자막(대사)'을 바탕으로 데이터베이스 검색용 키워드 및 요약 설명을 추출하세요.

    - 드라마 제목: {drama_title}
    - 촬영 장소명: {place_name} ({region})
    - 실제 대사/자막 내용: "{script}"

    [🚨 규칙]
    1. mood는 분위기를 잘 드러내는 형용사(예: 고즈넉한, 세련된)를 사용하세요.
    2. 모든 태그에 이모지(😄, 😊 등), 특수문자, 문장부호를 절대로 포함하지 마세요. (오직 한글 텍스트만 사용)
    3. scene_elements, k_culture_elements, activity는 서술어(~하기 좋음 등)를 절대 금지하며, 오직 '명사(단어)' 형태로만 작성하세요.
    4. 한자, 중국어, 영어, 외국어를 절대로 포함하지 마세요.
    5. description은 대사 맥락과 장소의 특징을 종합하여 1~2문장의 자연스러운 한글 요약문으로 작성하세요.
    """

    response = ollama.chat(
        model='qwen2.5:7b',
        messages=[{'role': 'user', 'content': prompt}],
        format=SegmentMetadata.model_json_schema(),
        options={
            'temperature': 0.0,
            'top_p': 0.1,    # 👈 엉뚱한 외국어 단어 튀어나옴 방지
            'seed': 42
        }
    )

    return SegmentMetadata.model_validate_json(response['message']['content'])

# 이모지 제거 함수
def remove_emojis(text: str) -> str:
    # 이모지 범주의 유니코드를 제거하는 정규식
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE
    )
    return emoji_pattern.sub(r'', text).strip()

def clean_to_pure_korean(text: str) -> str:
    """
    한글(가-힣), 숫자, 공백을 제외한 모든 문자를 제거합니다.
    (한자, 일어, 불어, 영어, 이모지, 특수문자 전부 삭제)
    """
    if not text:
        return ""
    # 완성형 한글, 숫자, 일반 공백만 허용
    cleaned = re.sub(r'[^가-힣0-9\s]', '', text)
    # 연속된 공백 하나로 줄이기
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

# ====================================================
# 4. 전체 데이터 처리 및 자동 태깅 실행
# ====================================================
total_dramas = len(all_dramas)
print(f"🚀 총 {total_dramas}개의 드라마 데이터 자동 태깅 시작\n")

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
            
            # ① 유튜브 해당 구간 자막 추출
            script = get_segment_transcript(yt_id, start, end)
            
            print(f"     └─ 구간 [{seg_idx}/{len(segments)}] ({start}초~{end}초) 자막 추출 및 태그 생성 중...", end="", flush=True)
            
            try:
                # AI 태그 생성
                generated_tags = auto_tag_segment(
                    drama_title=title, 
                    place_name=p_name, 
                    region=region, 
                    script=script
                )
                
                # 🧼 한글 세척 함수(clean_to_pure_korean) 적용 + 빈 값 제거
                seg["mood"] = [
                    clean_to_pure_korean(m) for m in generated_tags.mood 
                    if clean_to_pure_korean(m)
                ]
                seg["scene_elements"] = [
                    clean_to_pure_korean(s) for s in generated_tags.scene_elements 
                    if clean_to_pure_korean(s)
                ]
                seg["k_culture_elements"] = [
                    clean_to_pure_korean(k) for k in generated_tags.k_culture_elements 
                    if clean_to_pure_korean(k)
                ]
                seg["activity"] = [
                    clean_to_pure_korean(a) for a in generated_tags.activity 
                    if clean_to_pure_korean(a)
                ]
                
                # description도 한글 외 이상한 깨짐 문자가 있다면 정리
                if not seg.get("description"):
                    seg["description"] = generated_tags.description
                
                print(" -> 완료! ✅")
                
            except Exception as e:
                print(f" -> ⚠️ 오류 발생: {e}")
                continue

print("\n--------------------------------------------------")
print("✅ 모든 태그 작업 완료!")

# 5. 완성된 전체 결과를 JSON 파일로 저장
output_filename = "drama_video_data_tagged.json"
with open(output_filename, "w", encoding="utf-8") as f:
    json.dump(all_dramas, f, ensure_ascii=False, indent=4)

print(f"💾 결과가 '{output_filename}' 파일로 깔끔하게 저장되었습니다.")