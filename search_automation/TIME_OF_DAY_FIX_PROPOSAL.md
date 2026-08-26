# time_of_day 로컬 검색 규칙 수정 제안

현재 자동 회귀 1,044건 중 8건이 실패합니다. OpenAI·DB 문제가 아니라
`D:\K-Tour-AI\search-service\src\query_parser.py`의 시간대 별칭과 최종
metadata canonical 값이 다르기 때문입니다.

## 현재 실패 표현

```text
오전, 오후, day, 저녁, evening, 야간, 야경
→ 필터를 추출하지 못함

morning
→ 아침으로 추출하지만 최종 metadata의 day와 연결되지 않음
```

최종 metadata 기준값은 다음 세 값입니다.

```text
day / evening / night
```

따라서 `query_parser.py`의 `_VALUE_ALIASES["time_of_day"]`도 아래처럼
canonical을 맞추는 것이 가장 단순합니다.

```python
"time_of_day": {
    "day": (
        "오전", "아침", "낮", "오후", "day", "daytime", "morning",
        "during the day", "朝", "昼", "上午", "白天",
    ),
    "evening": (
        "해질녘", "저녁", "evening", "sunset", "dusk",
        "夕暮れ", "日落", "黄昏",
    ),
    "night": (
        "밤", "야간", "야경", "night", "nighttime", "夜", "夜晚",
    ),
},
```

이 변경 후 `run_local_rule_regression.py --strict`로 1,044건을 다시 실행해야
합니다. 이 문서는 수정 제안일 뿐이며 실제 `D:\K-Tour-AI` 파일은 변경하지
않았습니다.
