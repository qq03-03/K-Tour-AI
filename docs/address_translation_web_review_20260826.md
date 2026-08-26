# 주소 표시언어 웹 교차검증 결과

- 검증일: 2026-08-26
- 대상: 한국어 원주소가 존재하는 장소 66건의 영어·일본어·중국어 주소
- 미번역: 한국어 원주소가 없는 P001~P007, P013 8건
- 원본 metadata 및 embedding: 변경하지 않음

## 반영한 수정

| place_id | 장소 | 수정 내용 |
|---|---|---|
| P009 | 전주 오목대 | 영문 `Girindae-ro`를 공식 표기 `Girin-daero`로 수정 |
| P021 | 청계천 | 영문 법정동 표기를 `Taepyeongno 1-ga`로 수정 |
| P053 | 사천진 해변 | 영문 `Jillihaebyeon-gil` 및 관광공사 방식의 일·중 주소 표기로 수정 |
| P054 | 영인산 자연휴양림 | 영문 도로명을 `Asanoncheon-ro`로 수정 |
| P066 | 안동 만휴정 | 영문 면 표기를 `Giran-myeon`으로 수정 |
| P072 | 아침고요수목원 서화연 | 관광지 공식 대표주소 `수목원로 432`와 영·일·중 주소로 수정. 기존 서화연 POI 좌표는 유지 |

## 확인했으나 변경하지 않은 항목

- P060 재인폭포의 `부곡리 산 235`는 문화재 지정 소재지로 유효하다. 방문자 안내 주소인 부곡리 192·193과 용도가 다르므로 기존 값을 유지한다.
- P050 화진포 해수욕장의 초도리 주소는 유효하지만 상세 도로명 없이 마을 단위로 표시된다.
- P034 녹사평 육교의 영문 `underground`는 의미상 맞지만 UI 문장으로는 다소 어색하다.
- 전남광주통합특별시, 인천 서해구·영종구는 2026년 행정구역 개편 명칭이므로 오류로 처리하지 않는다.

## 주요 근거

- 전주 오목대: https://english.visitkorea.or.kr/svc/contents/contentsView.do?vcontsId=182528
- 사천진 해변 일본어: https://japanese.visitkorea.or.kr/svc/contents/contentsView.do?vcontsId=189735
- 사천진 해변 중국어: https://chinese.visitkorea.or.kr/svc/contents/contentsView.do?vcontsId=189899
- 영인산 자연휴양림: https://english.visitkorea.or.kr/svc/whereToGo/locIntrdn/rgnContentsView.do?vcontsId=97428
- 안동 만휴정 영문: https://english.visitkorea.or.kr/svc/whereToGo/locIntrdn/rgnContentsView.do?vcontsId=14982
- 안동 만휴정 중국어: https://chinese.visitkorea.or.kr/svc/whereToGo/locIntrdn/rgnContentsView.do?vcontsId=113038
- 아침고요수목원: https://japanese.visitkorea.or.kr/svc/contents/contentsView.do?menuSn=351&vcontsId=71928
- 재인폭포 관광공사 연결 데이터: https://data.visitkorea.or.kr/linkedview/125496

## 판정 기준

공식 다국어 주소가 있는 경우 해당 표기를 우선했다. 공식 다국어 주소가 없는 지번 주소는 행정구역, 도로명 또는 리명, 건물번호가 한국어 원주소와 일치하는지를 기준으로 구성상 정상 여부를 판정했다.
