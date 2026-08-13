K-콘텐츠 통합 영상 전처리 최종 패키지
=====================================

이 패키지는 현재 수정 데이터와 우리가 정리한 필터/분류 기준을 합친 실행본입니다.

입력 데이터
- data_inbox/drama_video_data_tagged_최종.json
- 총 125개 segment / 고유 원본 125개
- 현재 segment_id 중복 0개
- start_time < end_time 구조 오류 0개

길이별 처리 기준
1) 60초 이하
   - 전체 범위를 실제 장면 전환 위주로 분석
   - 고정 초 단위로 억지 분할하지 않음
   - 짧아도 독립 장면이면 유지

2) 60~120초
   - 모든 장면을 전수 분할하지 않음
   - 전체를 빠르게 훑고 약 20초 대표 하이라이트를 최대 3개 선정

3) 2~10분
   - coarse scan 후 약 35초 대표 구간을 최대 3개 선정

4) 10~30분
   - 10초 간격 coarse scan 후 약 60초 대표 구간을 최대 4개 선정

5) 30분 이상 / 1시간 영상 포함
   - 전체 장면별 분석 금지
   - 20초 간격 coarse scan 후 약 90초 큰 대표 구간을 최대 5개 선정

시간 처리
- JSON의 start_time/end_time을 우선 사용
- 다운로드 후 실제 영상 duration을 확인
- end_time이 실제 길이보다 길면 실제 영상 끝으로 자동 보정
- start/end가 뒤집히거나 무효면 해당 원본 전체 범위로 자동 전환
- 시간 보정 내역은 preprocessed_output/_internal/processing_diagnostics.json에만 기록

계절
- 사람 검수값 > 입력 JSON season > 자동판정
- 계절 자동판정이 다르다는 이유로 영상 제외 금지
- 꽃/벚꽃 신호는 자동 계절 판정에서 봄을 강하게 우선
- 흰색만으로 겨울 판정 금지
- 겨울 자동판정은 눈/얼음/서리 성격의 근거가 필요

대분류
- 봄
- 여름
- 가을
- 겨울

소분류 8개
- 꽃
- 단풍
- 전통
- 들판
- 등산
- 숲
- 드라이브
- 바다

대표 theme_category
- 장면 개수가 아니라 출현 시간 비율 기준
- 60초 이하: 실제 통과 장면들의 duration 합산
- 긴 영상: 전체 처리범위를 coarse scan하여 시간 비율을 근사
- 가장 오래 나온 테마를 해당 영상의 대표 theme_category로 사용

야경
- night_view는 테마와 별도 boolean
- 단순히 어둡다는 이유만으로 야경 처리하지 않음
- 밤/야경 메타데이터 또는 저녁+조명+실제 어두운 화면을 함께 참고

필터
- 후보 확보는 여유롭게
- 약간 흐림/어두움/흔들림/부분 과노출은 유지
- 디코딩 실패, 거의 전체 암전/과노출, 장면 식별 불가능 수준의 심한 흐림만 제외
- 정상 재생 가능한 원본 기준 usable clip+keyframe 95% 이상 확보 목표
- 품질/계절/테마 점수는 메타데이터 담당자에게 노출하지 않음

대표 이미지
- 구간 중간 프레임 고정 사용 아님
- 여러 프레임을 비교해 선명도/노출/정보량이 좋은 프레임을 선택

최종 전달 파일
- preprocessed_output/preprocessed_segments.json
  메타데이터 담당자용 간단 결과
- preprocessed_output/preprocessed_video/
  전처리 영상
- preprocessed_output/keyframes/
  대표 이미지

내부 전용
- preprocessed_output/processing_results.json
- preprocessed_output/_internal/processing_diagnostics.json
- preprocessed_output/_internal/acquisition_report.json

최초 1회 설치
PowerShell에서 패키지 폴더로 이동 후:

  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  .\실행.ps1 setup

설정/대상 확인
  .\실행.ps1 check
  .\실행.ps1 list

전체 전처리
  .\실행.ps1 run -RightsConfirmed

Chrome 로그인 쿠키가 필요한 영상이 있을 때
  .\실행.ps1 run -RightsConfirmed -CookiesFromBrowser chrome

이미 원본 영상이 preprocessed_output/original_videos에 있을 때
  .\실행.ps1 run -RightsConfirmed -SkipDownload

한 개만 테스트
  .\실행.ps1 one -SourceSegmentId "V001_P001_S001" -RightsConfirmed

테스트 3개만 실행하고 싶으면
  .\실행.ps1 run -RightsConfirmed -Limit 3

중단 후 다시 실행
- 완료된 source_segment_id는 자동으로 건너뜁니다.
- 같은 항목을 다시 만들려면 -Force를 추가하세요.


최신 필터 변경사항
===============================
1. 야경
- time_of_day=밤이면 무조건 night_view=true
- 조명 유무와 관계없이 상단 하늘 후보 영역이 충분히 어두우면 야경
- 저녁+어두운 하늘도 야경
- 전체 화면이 단순히 어둡다는 이유만으로는 야경 처리하지 않음

2. 드라이브
- 자동차 자체보다 도로/차도/로드/차선/가드레일/터널 등 도로 구조를 우선
- 자동차/차량/대교/교량은 보조 신호
- 산책로/등산로/보행 골목만 있는 경우 드라이브 억제

3. 품질 필터
- 정상 재생 가능한 원본에서 95% 이상 usable clip+keyframe 확보 목표
- 품질 기준을 더 느슨하게 조정
- 암전/과노출/심한 흐림은 여러 극단 조건이 동시에 충족될 때만 제외

기존 결과를 지우고 전체 재전처리:
  .\실행.ps1 fresh -RightsConfirmed


야경은 상위 테마와 별도로 night_view=true/false로 관리합니다.
- time_of_day=밤: 무조건 true
- 어두운 하늘: true
- 저녁 + 어두운 하늘: true
- 어두운 분위기 + 화려한 조명: true
- 단순히 화면 전체가 어두운 것만으로는 true 처리하지 않음

드라이브:
- 도로/차도/로드/차선/가드레일/터널/로드브이로그 우선
- 자동차/차량/대교/교량은 보조
- 산책로/등산로/보행 골목은 억제

기존 전처리 결과를 지우고 전체 다시 실행:
  .\실행.ps1 fresh -RightsConfirmed

