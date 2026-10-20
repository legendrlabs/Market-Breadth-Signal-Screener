# 남은 Breadth 작업 검증 — 2026-10-20

## 범위와 판정

사용자가 승인한 남은 작업은 NYSE 장기 원천 검증, S&P500 보조 Breadth 수집, 외부 참고 JSON 두 오류 수정이다. 기존 수집/보고 흐름을 확장하며 A/C 정의·품질 승인·장기 투자 규칙은 변경하지 않는다.

공식 S&P500 전체 구성종목의 시점별 권한 있는 일봉 피드를 무료로 확보했다고 주장하지 않는다. 발행사 공개 SPY 보유종목 파일을 이용하는 **SPY traded-holdings proxy**만 구현했다. 잘못 해석할 비용은 펀드의 현금·특수 권리 또는 지수 구성 차이를 공식 Breadth로 오인하는 것이다. 따라서 공식 신호와 완전히 분리하고 분모·제외 행·날짜·커버리지를 공개한다.

## 공식 자료와 실제 접근

- NYSE Historical / TAQ는 거래·호가·종가 자료 제품을 설명한다. 이번 조사에서 2000~현재의 익명·키 없는 NYSE 일별 A/D 연속 CSV를 확보하지 못했다. 거래별 가격으로 NYSE Breadth를 추정하지 않았다.
  - https://www.nyse.com/market-data/historical
  - https://www.nyse.com/data-products/catalog/daily-taq/
- NYSE의 Daily U.S. Equity Market Statistics 소개는 S&P1500의 유동성·거래량·변동성 등을 설명한다. 이 자료를 장기 NYSE A/D 피드라고 간주하지 않았다.
  - https://www.nyse.com/data-insights/nyse-introduces-daily-us-equity-market-statistics-report
- McClellan의 원문은 composite와 common-only가 다르고 공급원별 A/D가 다를 수 있다고 설명한다. Common-only의 2005년 변경도 기술한다. 이 설명만으로 현대 전체 포함 종목 정책·PIT 구성·NDR 동등성이 입증되지는 않는다. 최근 무료 XLS와 별도로 장기 자료 구매를 안내한다. 구매하거나 유료 경로를 우회하지 않았다.
  - https://www.mcoscillator.com/learning_center/kb/market_data/a-d_data_composite_or_operating_companies_only/
  - https://www.mcoscillator.com/market_breadth_data/
- Unicorn 운영자는 여러 공개 공급원의 중앙값이며 범위와 정의가 다를 수 있고 2020년 갱신 중단이라고 명시한다. 기존에 발견한 2020년 이후 공백과 원문 비교 문제는 해소되지 않았다.
  - https://unicorn.us.com/advdec/about.php
- State Street 공식 SPY 페이지는 Fund Holdings와 Index Holdings를 분리한다. 공식 Daily 링크의 XLSX를 실제 다운로드했다. 2026-10-16 기준 지원 가능한 거래 티커 503개, 지원하지 않는 행 2개(현금 및 특수 권리)를 원문 그대로 별도 감사했다. 날짜가 최신 완료 거래일 2026-10-19와 달라 비율은 계산하지 않았다.
  - https://www.ssga.com/us/en/individual/etfs/state-street-spdr-sp-500-etf-trust-spy
  - https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx
- iShares IVV CSV 후보 URL은 이번 실제 요청에서 CSV 대신 HTML을 반환해 미채택했다. 공개 파일 경로로 보인다는 사실만으로 연결 성공으로 기록하지 않는다.
- Yahoo spark 3개 종목 시험 요청은 날짜별 배열을 반환했지만 최신 종가가 null이고 granularity=300이었다. 요청한 일봉임을 응답으로 확인하지 못했으므로 실시간/확장 거래가격으로 대체하지 않는다. 이 비공식 엔드포인트의 안정성·완전성은 보장되지 않으며 수집이 가능해도 품질 게이트를 통과해야 비율이 나온다.

## 구현 경계와 테스트

수집은 선택 옵션 `--aux-breadth`이며 일일 Actions에서 자동 시도한다. 기존 A/C 입력은 별도 NYSE breadth.csv만 사용한다. 같은 최신 완료일의 보유 목록과 직전/당일 일봉을 100% 확보했을 때만 보조 비율을 계산한다. 현재 목록으로 과거 2000년 이후를 채우지 않으며, 미관측치를 0이나 보합으로 바꾸지 않는다. 분모와 지원하지 않는 행을 공개한다.

외부 JSON 파싱 오류가 빈 입력처럼 표시되던 문제 및 값 누락/비유한 수치 문제는 회귀 테스트를 먼저 실패시킨 후 수정했다. 보조 지표 테스트는 날짜·전체 분모·중복 매핑·가격 누락·미래 검색시각·수집 완료시각·일봉 확인·수집 실패 후 과거 성공 재사용 방지·신호 격리·원자료 해시를 포함한다. 최초 실수집에서 달력 시작에 시각까지 전달한 문제를 발견했고 날짜 정규화 회귀를 RED→GREEN으로 수정했다.

완료 범위는 수집 시도·품질 판단·보고 분리와 오류 수정이다. 공식 S&P500 시점별 Breadth 데이터 확보, NYSE 연속 장기 데이터 검증, NDR 원문 동등성 및 100% 통계 독립 재현은 **미완료/UNVERIFIED**다. SAFE_TO_ACT=False를 유지한다.


## 추가 복원: 43개 보관본 모두 다운로드·파싱 성공

정확한 원본 XLS 주소의 CDX 색인을 재조회해 서로 다른 digest 43개를 찾고, 43개 전부의 원본 바이트·요청/실제 해석 URL·검색시각·SHA256을 저장했다. 잘못된 wildcard 조회가 반환한 홈페이지 목록은 XLS 관측치로 세지 않았다. 보관 시각은 관측일이 아니므로 파일 내부 날짜로 기간을 검증했다. 색인·다운로드·파싱·달력 대조 결과를 구분했다.

| 검증 항목 | 실제 결과 |
|---|---:|
| 파싱 성공 보관본 | 43/43 |
| 원본 관측 합계 | 5,057행 |
| 날짜 중복 제거 후 McClellan 관측 | 2,086거래일 |
| 관측 범위 | 2009-09-30~2026-10-19, 불연속 |
| 위 범위 안 미확보 거래일 | 2,203일 |
| 비거래일·비유효 카운트 날짜 | 각각 0 |
| 보관본 사이 수정이 확인된 날짜 | 2일 |
| Unicorn과 겹치는 관측 날짜 | 1,605일, 2009-09-30~2017-09-20 |
| 상승·하락 수가 둘 다 정확히 같은 날짜 | 455일, 28.35% |

최근 보관본 우선 선택은 비교를 위한 연구 가정이며 당시에 알 수 있었던 값이나 확정 정답을 뜻하지 않는다. 같은 공급원 안에서도 수정이 있었고, Unicorn 합성 집계와 McClellan 최종 집계는 겹치는 1,605일 중 1,150일에 최소 한 수가 다르다. 이것은 두 자료를 접합해 검증된 하나의 시계열로 취급할 수 없다는 근거다. 특정 공급원이 틀렸다고 단정하거나 일치율을 신호 성과로 해석하지 않는다.

파일별 원본 URL·해시·기간은 [보관본 목록](reference/mcclellan-archive-inventory-2026-10-20.csv), 범위·비교 요약은 [감사 결과](reference/mcclellan-archive-audit-2026-10-20.json)에 기록했다. 원자료와 날짜별 비교는 별도 연구 증거 파일로 보존하고 공개 소스 배포에는 포함하지 않는다. 과거 4개 보관본만을 조사했던 2026-10-19 보고서의 부분 확보 수치는 당시 스냅샷이며, 이번 43개 재조사가 후속 결과다. 원문 NDR 동등성과 2000~현재 연속성은 여전히 미검증이다.
