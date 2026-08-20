"""실제 임베딩 모델을 대신하는 결정론적 키워드 임베더."""

from __future__ import annotations

import numpy as np


# 같은 의미로 취급할 한국어 표현을 하나의 벡터 차원으로 묶는다.
# 실제 모델의 성능을 흉내 내려는 목적이 아니라 검색 흐름을 검증하기 위한 규칙이다.
CONCEPTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    # 계절
    ("spring", ("봄",)),
    ("summer", ("여름",)),
    ("autumn", ("가을",)),
    ("winter", ("겨울",)),
    # 시간대
    ("dawn", ("새벽", "일출")),
    ("morning", ("아침",)),
    ("daytime", ("낮",)),
    ("sunset", ("해질녘", "노을")),
    ("night", ("밤", "야경", "네온")),
    # 감성
    ("calm", ("고요", "조용", "차분", "평화", "한적", "잔잔")),
    ("lively", ("활기", "즐거", "역동", "빠르게")),
    ("romantic", ("낭만", "따뜻", "화사")),
    ("majestic", ("웅장", "장엄")),
    ("mysterious", ("신비", "안개")),
    ("lonely", ("쓸쓸", "홀로", "흐린")),
    ("fresh", ("상쾌", "시원", "산뜻", "싱그")),
    # 장소·풍경. 한옥, 궁궐, 성곽은 검색에서 서로 구분되도록 분리한다.
    ("hanok", ("한옥", "한옥마을", "북촌", "하회마을")),
    ("palace", ("궁궐", "경복궁", "동궁", "월지")),
    ("fortress", ("성곽", "수원 화성")),
    ("heritage", ("전통", "문화유산")),
    ("sea", ("바다", "해변", "해안", "모래사장", "파도", "해운대", "다대포", "안목")),
    ("mountain", ("설악산", "설산", "산악", "등산", "오름", "계곡", "대관령")),
    ("forest", ("대나무", "숲", "녹차", "차밭", "초록")),
    ("wetland", ("습지", "갈대", "물길", "생태")),
    ("flower", ("꽃", "벚꽃", "유채")),
    ("autumn_leaves", ("단풍",)),
    ("snow", ("눈", "설경", "눈밭")),
    ("urban", ("도심", "도시", "네온", "빌딩", "쇼핑", "명동", "송도")),
    # 활동
    ("walking", ("산책", "걷", "걸으며")),
    ("photo", ("사진",)),
    ("viewing", ("감상", "관람", "구경", "바라보")),
    ("market", ("시장", "먹거리")),
    ("cycling", ("자전거",)),
    ("water_activity", ("수영",)),
    ("winter_sport", ("스키", "눈놀이")),
    # 지역. 실제 모델에서는 별도 차원 없이 의미 임베딩으로 처리할 수 있다.
    ("region_seoul", ("서울", "북촌", "경복궁", "명동")),
    ("region_busan", ("부산", "해운대", "다대포")),
    ("region_jeju", ("제주", "성산일출봉", "산굼부리")),
    ("region_jeonju", ("전주",)),
    ("region_gyeongju", ("경주",)),
    ("region_gangwon", ("강릉", "속초", "평창", "설악산", "대관령")),
    ("region_jeonnam", ("담양", "순천", "보성")),
    ("region_gyeonggi", ("수원",)),
    ("region_incheon", ("인천", "송도")),
    ("region_andong", ("안동",)),
)


class DummyTextEmbedder:
    """키워드 포함 여부를 0과 1로 표현하는 간단한 텍스트 임베더."""

    @property
    def dimension(self) -> int:
        """생성되는 벡터의 차원 수."""

        return len(CONCEPTS)

    def encode(self, text: str) -> np.ndarray:
        """텍스트를 고정 길이의 float 벡터로 변환한다."""

        if not isinstance(text, str):
            raise TypeError("text는 문자열이어야 합니다.")

        normalized = text.strip().lower()
        # 키워드가 하나라도 포함되면 해당 개념 차원을 1로 표시한다.
        # 따라서 이 벡터는 실제 의미 임베딩이 아니라 다중 핫 벡터다.
        return np.asarray(
            [
                1.0 if any(keyword in normalized for keyword in keywords) else 0.0
                for _, keywords in CONCEPTS
            ],
            dtype=float,
        )

    def matched_concepts(self, text: str) -> list[str]:
        """설명과 오류 분석을 위해 텍스트에서 인식한 개념 이름을 반환한다."""

        vector = self.encode(text)
        # 값이 1인 차원의 영문 개념명을 실패 분석 보고서에 사용한다.
        return [name for (name, _), value in zip(CONCEPTS, vector, strict=True) if value > 0]
