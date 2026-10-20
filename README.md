# Market Breadth Signal Screener (MBSS) v0.1.3

미국 상승 참여도 신호를 **독립 검증**하는 Python 연구 도구입니다. 과거 100% 승률을 전제로 삼지 않습니다. 기존 Mechanical Top15, K-Mechanical, SSM 코드나 규칙을 가져오거나 변경하지 않습니다. 자동매매 기능은 없습니다.

**연구 상태: 소스 구현·로컬 실자료 실행 완료. B/D 집계 수치와 A/C 일부 사건 날짜 대조. A/C 전체·복합 신호 실자료 검증 미완료. SAFE_TO_ACT=False.**

개발·배포 저장소는 [legendrlabs/Market-Breadth-Signal-Screener](https://github.com/legendrlabs/Market-Breadth-Signal-Screener)입니다. v0.1.3은 검증 진행 중인 연구 프리릴리스입니다. 실제 게시 여부는 [Releases](https://github.com/legendrlabs/Market-Breadth-Signal-Screener/releases), 실행·보고서는 [Actions](https://github.com/legendrlabs/Market-Breadth-Signal-Screener/actions)에서 확인합니다.

## 빠른 실행

Python 3.10 이상, 인터넷과 무료 패키지 설치가 가능한 환경에서:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
mbss collect --input data/normalized --start 1999-01-01 --aux-breadth
mbss run --input data/normalized --start 2000-01-01
```

Windows PowerShell 활성화는 `.venv\Scripts\Activate.ps1`입니다. 설치하지 않고 실행할 때는 `PYTHONPATH=src python -m mbss.cli ...`를 사용합니다.

수집 명령이 실패하면 종료코드 2를 반환합니다. 이후 `run`을 실행하면 확보된 입력만 검증하여 보고서를 만들며, 부족한 항목은 DATA_HOLD로 남깁니다. McClellan 무료 최근 NYSE A/D XLS를 일일 수집하지만 장기 공백·집계 범위·NDR 비교 검증을 통과하지 못했으므로, 가격 수집 성공만으로 A/C 신호가 활성화되지 않습니다. 거래일 라이브러리가 없으면 평일로 대체하지 않습니다.

```bash
mbss run --as-of 2026-10-19T08:57:00Z --output runs/research-20261019
mbss run --start 1974-01-01 --cost-bps 5 --output runs/long-history-costs
```

1974 검증에는 충분한 워밍업을 포함하여 그 이전부터의 가격 입력을 준비해야 합니다. 19회 등 전후 표본 검증에는 2000년보다 훨씬 이전의 자료가 필요합니다. `--as-of`는 시간대를 포함해야 하며, 완료된 NYSE 종가까지만 사용합니다. 출력 폴더는 새 경로여야 합니다. 기존 실행을 덮어쓰지 않습니다.

## 입력과 출력

- `data/normalized/{spx,spy,qqq}.csv`: `date,open,high,low,close,adj_close,dividend`
- `data/normalized/vix.csv`: `date,close`
- `data/normalized/breadth.csv`: `date,advances,declines`
- `data/normalized/metadata.json`: 출처·정의·조정·검색시각·검토 내역. 계약은 [docs/data-contract.md](docs/data-contract.md)를 참조합니다.

출력 실행 폴더에는 `latest.md`, 독립 실행 HTML인 `latest.html`, `signals.csv`, `backtest_results.csv`, `signal_events.json`, `data_quality.json`, `run_manifest.json`을 저장합니다. 보조 파일에는 원관측/조정값 감사표, 신호 정의 민감도, 국면별 사례, 통계 요약, 무작위 진입 기준, SPY 전략별 일별 자산곡선과 거래가 포함됩니다. 데이터가 없을 때는 빈 CSV에 헤더를 보존하고 그래프에 DATA_HOLD를 표시합니다.

## 신호와 성과

| 신호 | 구현 정의 | 처리 |
|---|---|---|
| A ZBT | NYSE A/(A+D)의 EMA10, `<0.400`에서 `>0.615`까지 1~10거래일 | SMA10 초기값, 연속 100개 관측 워밍업. 경계 포함·9일 거리·첫 값 초기화 민감도 별도 |
| B Strong Rally | 각각 +1.5% 이상인 연속 3거래일 | 연속 구간의 최초 세 번째 날만 신호 |
| C Expansion | 비율 `>70%`인 날이 완전한 최근 10거래일 중 6일 이상 | 최초 충족, 해제 후 재진입, 10거래일 재발 제한 |
| D Midterm | 중간선거 이후 첫 NYSE 거래일 시가 | 계절성 참고. 미래 선거는 제외 |

원전 책의 해당 페이지와 NDR 원자료 시계열은 확보되지 않았습니다. Carson 원문 표의 사건 목록은 직접 확인해 참조 CSV로 기록했습니다. A의 원전 일치나 19/19·10/10·8/8·13/13 주장을 VERIFIED로 표시하지 않습니다. 출처와 상충 사항은 [docs/research.md](docs/research.md)에 기록합니다.

2026-10-19 실제 실행에서는 Yahoo 가격·분배금, Cboe VIX, XNYS 달력을 확보했습니다. SPX/SPY/QQQ는 관측기간 내 검사를 통과했지만 VIX는 역사적 결측·비NYSE 날짜 불일치로 엄격 게이트를 통과하지 못했습니다. NYSE Breadth는 Unicorn 1965~2020 아카이브와 McClellan 최근·과거 보관본을 부분 확보했지만 검증된 연속 입력은 없습니다. 1970 보충 실행에서 B의 원문 성숙 표본 10/10·252거래일 평균 +21.63%, D의 1974~2022 표본 13/13·선거일 종가 기준 달력 6개월 평균 +12.41%로 집계값이 일치했습니다. 정확한 원문 사건 목록·정의까지 검증된 것은 아닙니다. 같은 표본의 실제 다음 시가 진입 평균은 B +21.78%, D +11.97%입니다.

2000년 이후 B는 5회·1년 평균 +24.30%였지만, 신호만 기다리는 B 12개월 전략의 누적 성과 +217.91%는 SPY 단순 보유 +723.67%에 미달했습니다. 현금 이자 0%, 비용 0인 가정이며 계좌 실현성과가 아닙니다. 1950~1969 달력 규칙은 미검증이라 엔진이 역사적 달력 시작을 1970년으로 제한하고 그 사실을 기록합니다.

신호 확정 다음 거래일 시가부터 실제 진입일 + 1/3/6/12개월의 다음 거래일 종가까지 계산합니다. 거래일 수 21/63/126/252개로 달력을 대신하지 않습니다. SPX 가격수익률과 SPY/QQQ 배당조정 대용 수익률을 구분합니다. 비용 단위는 편도 bps이며 매수·매도 양쪽에 적용됩니다. 모든 수익률은 소수입니다(`0.10=10%`). 가격지수는 직접 매수 가능한 자산이 아닙니다.

추가 원문 대조에서 A는 1970~2020 중첩 구간의 11회 날짜가 모두 일치했고, C는 원문 5회를 모두 탐지했으나 추가 3회가 있어 중복 집계 규칙이 미해결입니다. B의 11회 날짜 목록도 신규 2025년 사례를 포함해 일치했습니다. A의 2025년 날짜 표기와 B의 그림별 평균 수치에는 원문 내부 불일치가 있습니다. 자세한 근거·참조 CSV·남은 공백은 [추가 대조 보고서](docs/publication-reconciliation-2026-10-19.md)에 기록했습니다. 전체 재현 성공이나 실전 승인으로 표시하지 않습니다.

## 검증과 운영

합성자료는 테스트에만 사용하며 보고서에 SYNTHETIC TEST ONLY를 표시합니다. 입력이 없을 때의 정상 보고, 잘못된 메타데이터, 누락·중복·무한값, 인과적 신호, 경계, 겹치는 보유기간, 비용과 배당 조정, 비교기간 정렬 등을 테스트합니다. 거래일 의존성을 설치하지 못한 환경에서는 조기 폐장 검증을 SKIP하고 그 사실을 보고합니다.

최초 엔진 검수는 Python 47개 통과이며 등록 단계의 배포 검사를 포함한 최종 로컬 검수는 Python 85개와 Node 6개 전체 통과입니다. 의존성 설치 후에는 휴장일·조기 폐장 검사도 생략하지 않았습니다. 같은 실행 환경을 복원하려면 `requirements.lock.txt`를 사용합니다. 잠금 파일은 이 실행의 Python 3.12 환경 스냅샷입니다.

GitHub 워크플로는 `.github/workflows/ci.yml`, `daily.yml`에 있습니다. 일일 작업은 미국 거래일 저녁 이후 UTC 23:17 / 다음 날 KST 08:17에 시도하며 휴장일에는 직전 완료 거래일을 사용합니다. 개인/조직의 Actions 무료 사용량 한도는 별도이며 무제한 무료 실행을 보장하지 않습니다. 공급원 자료와 보고서를 코드 릴리스에 자동 커밋하지 않습니다.

main의 버전 변경은 테스트 후 연구 프리릴리스를 준비하고 첫 일일 보고서를 생성합니다. 기존 태그·공개 파일을 덮어쓰지 않습니다. 실제 배포 근거와 상태는 [docs/deployment.md](docs/deployment.md), 운용은 [docs/운용매뉴얼.md](docs/운용매뉴얼.md)를 참조합니다.


## v0.1.2 실행 출처 수정

v0.1.0의 첫 GitHub 보고서에서 publication 필드가 로컬 개발 당시의 NOT_PUBLISHED 상수로 남아 있던 오류를 수정했습니다. GitHub Actions 환경의 repository/run/SHA와 실제 checkout commit이 일치할 때 실행 URL을 기록합니다. 로컬 실행이나 일치하지 않는 환경은 UNKNOWN_NOT_CHECKED이며 원격 release의 존재는 조회 없이 단정하지 않습니다. 신호 수식·수익률·DATA_HOLD 판정은 변경하지 않았습니다.


## v0.1.2 현재 상태·품질 원인·관측 자료

- 현재 신호가 없으면 `SIGNAL_STATUS=NO_SIGNAL`, `SIGNAL_DATE=null`입니다. 과거 사건은 `LAST_SIGNAL_DATE`와 `LAST_SIGNAL_STATUS=EXPIRED`로 추적합니다. D에는 `SEASONALITY_STATUS=ACTIVE/INACTIVE`를 별도로 표시합니다.
- 보류 원인은 `DATA_HOLD_REASONS`와 데이터별 `reason_codes`로 구분합니다: SOURCE_UNAVAILABLE, INSUFFICIENT_HISTORY, VALIDATION_FAILED, STALE_DATA. 상세 기존 flags도 보존합니다.
- McClellan 최근 XLS에서 실제 상승·하락 수를 읽습니다. 10거래일 연속성·100관측 EMA 워밍업을 검사한 참고 지표는 `data_quality.json.breadth_diagnostics`와 별도 보고서 표에만 표시합니다. 미검증 범위를 신호·백테스트에 투입하지 않습니다.
- 장중 보도·S&P500 보조 참고값은 입력 폴더의 선택적 `external_context.json`에 보관하고 같은 이름의 출력으로 분리합니다. 출처·모집단·관측/수집시각·장중 여부를 표시하며 A/C 입력으로 사용하지 않습니다. S&P500 일별 자동 Breadth 시계열 수집은 아직 구현하지 않았습니다.

추가 자료와 한계는 [v0.1.2 연구](docs/breadth-live-research-2026-10-19.md)를 참조합니다.


## v0.1.3 보조 Breadth와 외부 자료 오류

`collect --aux-breadth`는 State Street 공식 SPY 보유종목 XLSX에서 기준일·거래 가능한 티커를 읽고, 같은 기준일의 Yahoo 일봉 종가를 최대 20종목씩 요청합니다. 일일 Actions도 이 옵션을 사용합니다. **공식 S&P500 구성종목 Breadth가 아니라 SPY 보유종목 기반 대용 참고값**입니다. 지원하지 않는 티커·현금 등 제외 원본 행을 숨기지 않습니다.

최신 완료 거래일과 보유종목 기준일이 다르거나, 전 거래일/당일 가격이 하나라도 누락되거나, 일봉 응답이 확인되지 않으면 비율은 null입니다. 450~550개는 잘린 상위 보유목록 방지를 위한 점검 범위이며 S&P500 공식 구성 인증이 아닙니다. 상승/(상승+하락+보합), 상승/(상승+하락)을 구분합니다. 현재 구성으로 과거 시계열을 소급 생성하지 않습니다.

별도 입력·출력 `auxiliary_breadth.json` 및 `data_quality.json.auxiliary_breadth`에서 기준일·범위·제외 행·분모·가격 커버리지·보류 사유를 확인합니다. A/C 신호·백테스트·SAFE_TO_ACT에 연결하지 않습니다. 외부 JSON 파싱 실패는 Markdown/HTML에도 표시하며, 외부 수치의 누락·NaN·불리언 값은 명시적으로 차단합니다.

NYSE 장기 무료 원천·정의 비교는 아직 미완료입니다. 실제 접근 시도와 보조 지표 한계는 [2026-10-20 검증 기록](docs/breadth-remaining-work-2026-10-20.md)을 참조합니다.

후속 아카이브 조사에서 McClellan 보관본 43개를 복원해 2,086거래일을 부분 확보했습니다. Unicorn과 겹치는 1,605일 중 상승·하락 수가 모두 같은 날은 455일(28.35%)로, 공급원 간 단순 접합은 승인하지 않습니다. 장기 연속 검증 완료를 뜻하지 않습니다.

## 2026-10-20 NYSE 참고 관측·VIX 품질 감사 (v0.1.3 유지)

- `data_quality.json.breadth_diagnostics`에 실제 최근 NYSE 관측일, 원자료 상승/하락 수, CURRENT/STALE 상태, 연속 유효 거래일 수, 10일 창·100일 EMA 충족 여부, 출처·검색시각을 노출합니다. 이는 `UNVERIFIED_REFERENCE_ONLY`이며 A/C 신호·백테스트·실전 승인 입력이 아닙니다.
- Cboe VIX에서 NYSE 달력 외 날짜는 원자료에 보존하고 `excluded_non_xnys_dates`로 감사하지만, 정상 NYSE 거래일 누락은 `missing_xnys_dates`와 `MISSING_SESSIONS`로 계속 차단합니다. FRED 값으로 자동 대체하지 않습니다.
- 공개 VIX CSV의 동일 OHLC 첫 506행은 1990-01-02~1991-12-31이며 1992-01-02부터 OHLC가 분리됩니다. 2004-06-11까지 506행이라는 외부 조사문 설명은 정정했습니다.
- 원전 확인 수준, Carson/NDR C 신호 중복 미해결, WSJ 최종값 대조 미구현과 후속 과제: [2026-10-20 후속 검증](docs/verification-followup-2026-10-20.md). `SAFE_TO_ACT=False`, `OBSERVE_ONLY` 유지.

## 2026-10-20 WSJ/McClellan 확정치 감사 모듈 (v0.1.3 유지)

WSJ 일별 NYSE 상승·하락 수는 공개 HTML 열람에서 동적 로딩만 확인되어 **실측 일치 검증은 아직 0건(자료 미확보)**입니다. 출처와 일자·캡처시각이 분명한 `wsj_reference.json`을 수동 입력할 수 있으며, 정규 NYSE 세션·미래일·잠정치·중복일·원천 확인 여부를 감사하여 McClellan XLS 원관측과 날짜별 차이를 `wsj_reconciliation.json` 및 Markdown/HTML 보고서에 표시합니다.

증거가 없으면 `NO_WSJ_REFERENCE`로 표시하고 수치를 만들지 않습니다. 일치하더라도 `COUNTS_MATCH_REFERENCE_ONLY`이며 원전/NDR 비교 인증이 아닙니다. **A/C 신호·백테스트·자금배분·SAFE_TO_ACT에 연결하지 않습니다.**

자세한 스키마와 원문 근거: [WSJ/McClellan 대조 및 미완료 과제](docs/wsj-mcclellan-reconciliation-2026-10-20.md).

## 2026-10-20 McClellan 공개 웹페이지 ↔ 무료 XLS 감시

`mbss collect`가 동일 McClellan 발행사의 NYSE 일일 공개 표(`market_breadth_data/`)와 기존 최근 A/D 엑셀(`OSC-DATA.xls`)을 별도로 수집해 수치·날짜가 일치하는지 감시합니다. 원본 웹페이지는 실행별 raw 디렉터리에 해시와 함께 저장하고, `publisher_page_snapshot.json`과 `publisher_page_reconciliation.json` 및 Markdown/HTML에 날짜·상승·하락·차이를 제공합니다. 실패·구버전 페이지·XLS 결측은 값을 생성하거나 자동 보정하지 않습니다.

2026-10-19 McClellan 공개 페이지: NYSE 상승 961/하락 1,751, 하락 우위 790개. 이는 하루 관측값이며 ZBT EMA10이 아닙니다. **발행사 자체 두 표현을 대조하는 것일 뿐, WSJ 독립 확정치/NDR/Carson 비교 완료가 아닙니다.** A/C `DATA_HOLD`, `SAFE_TO_ACT=False` 유지. 실제 수집이 시작된 실행의 품질 JSON을 확인해야 하며, 이 설명만으로 자동 수집 성공을 단정하지 않습니다.

원문과 구현 경계: [McClellan 웹/XLS 비교](docs/mcclellan-publisher-audit-2026-10-20.md).
