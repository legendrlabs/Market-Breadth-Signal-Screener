# v0.1.2: NYSE 관측 확보와 신호 상태 구분

## 추가로 확인한 범위

[McClellan 무료 페이지](https://www.mcoscillator.com/market_breadth_data/)가 연결하는 [공개 XLS](https://www.mcoscillator.com/data/osc_data/OSC-DATA.xls)를 다시 다운로드했다. 179,712바이트, SHA256 `7d920a680bb89c3d374806a5a8269307ddb341473a088543e958125799a0fe5b`이며 A 시트의 DATE / NYSE ADV. / NYSE DEC. 열을 확인했다. 실제 관측은 2026-03-31~2026-10-16의 139거래일, 마지막 상승 1,152·하락 1,569다. 미래 날짜의 빈 입력란과 계산된 Oscillator/Volume 열을 종목 수로 읽지 않는다.

[공급원 설명](https://www.mcoscillator.com/learning_center/kb/market_data/a-d_data_composite_or_operating_companies_only/)은 일반 composite와 Common Only 시계열을 구분하고, 자신의 최종 값은 WSJ/Barron's를 기준으로 삼는다고 설명한다. Common Only의 과거 구성 규칙도 바뀌었다고 설명한다. 이 설명은 A/D 정의 차이를 밝히는 증거지만 모든 2026년 포함 종목 정책·과거 시점별 구성과 NDR 동일성을 확정하는 계약은 아니다. 필요한 universe 필드를 임의로 True로 채우지 않는다.

무료 최근 자료는 일일 수집에 연결했다. 장기 archive가 유료로 제공된다는 사실은 무료 전체 자료를 확보했다는 뜻이 아니다. 기존 Unicorn 자료와는 겹치는 검증 구간과 연속 구간이 없어 이어 붙이지 않는다. 과거 연구에서 발견한 2020~2026 공백은 해결되지 않았다.

NYSE Daily U.S. Equity Market Statistics 소개와 Nasdaq market-activity/summary 정의도 추가로 조회했으나, 이들은 동일한 NYSE 장기 A/D 원자료 경로를 제공한 근거가 되지 못했다. 검증되지 않은 URL이나 검색 결과를 완료한 수집원으로 등록하지 않는다. 이번 변경은 전체 19/19·8/8 재현을 완료하지 않는다.

## 보류와 현재 상태

수집 접근 실패/관측 없음은 SOURCE_UNAVAILABLE, 필요한 계산 행 수 부족은 INSUFFICIENT_HISTORY, 날짜·수치·출처·범위·원전 비교 실패는 VALIDATION_FAILED로 구분한다. 유효한 과거 자료가 최신 완료 거래일에 도달하지 못하면 STALE_DATA를 별도로 기록한다. 각 범주의 구체 원인은 기존 flags와 함께 보존한다.

현재 활성 신호가 없으면 NO_SIGNAL이다. 과거 유효 신호의 관찰기간 종료는 LAST_SIGNAL_STATUS=EXPIRED다. 신호를 한 번도 탐지하지 못한 경우 LAST_SIGNAL_DATE/STATUS는 null이다. 중간선거 6개월 구간의 활성 여부는 SEASONALITY_STATUS로 분리한다. 데이터 품질 보류가 이보다 우선하며 SAFE_TO_ACT=False는 유지한다.

최근 NYSE 관측에 대한 ratio, EMA10, 최근 10일 적격일 수는 UNVERIFIED_REFERENCE_ONLY로 계산한다. 모든 결측·잘못된 수치는 거래일 달력의 공백으로 남겨 EMA와 10일 창을 재시작한다. 이러한 진단값은 공식 신호 탐지·복합 신호·백테스트 표본에 입력하지 않는다.

## 장중 S&P500 참고값

사용자가 제시한 32%는 [MarketWatch 원문](https://www.marketwatch.com/livecoverage/stock-market-today-dow-s-p-500-nasdaq-bounce-back-teach-earnings-third-quarter/card/tech-is-rallying-but-overall-market-breadth-is-weak-lWrouMgZJNctbATqR2qh)에서 S&P500 구성 종목 중 상승 161개·약 32%라는 FactSet 인용으로 확인했다. NYSE 전체가 아니며, 해당 장중 스냅샷의 정확한 관측시각은 조회 내용에서 확보하지 못했다. 전 거래일 SPX/SMA200과 동일 시점이라고 표시하지 않는다.

선택적 입력 `external_context.json` 예시(형식만 설명하며 자동 입력하지 않음):

```json
[
  {
    "metric": "sp500_advancing_share_reported",
    "value": 0.32,
    "universe": "S&P 500",
    "session_type": "INTRADAY",
    "observed_at": null,
    "retrieval_timestamp": "2026-10-19T15:00:00Z",
    "source": "https://example.org/source-article"
  }
]
```

정확한 시각을 모르면 null을 그대로 보존하고 OBSERVATION_TIME_UNKNOWN으로 표시한다. 관측·수집시각이 as-of보다 미래면 해당 오류를 표시한다. 입력이 어떤 eligible_for_signal 값을 주장해도 출력은 False다. 이 입력은 공식 지표나 통계 검증 자료가 아니며, S&P500 일별 시계열 자동 수집과도 구분한다.


## 수집 보존·파서 검수

실제 XLS에는 마지막 계산 행의 날짜와 설명 문구가 있는 footer가 있었다. count 숫자가 전혀 없는 이런 설명 행은 관측치에서 제외하고 parser_notes.non_observation_note_rows에 집계한다. 한쪽만 숫자가 있는 불완전 행은 삭제하지 않고 검증으로 넘긴다. 실제 파일 재파싱은 139관측·설명 행 1개다.

기존 breadth.csv가 수동/검토 입력이면 수집기가 교체하지 않는다. 새 자료는 breadth_candidate.csv와 breadth_candidate_metadata.json으로 격리한다. 같은 출처의 collector_managed=true, 미검토 파일만 자동 새로고침한다. 숫자나 표본을 맞추려고 서로 다른 공급원 파일을 합치지 않는다.
