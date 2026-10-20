# MBSS v0.1.3 후속 검증 — NYSE 최근 관측과 VIX XNYS 달력 감사

기준: 2026-10-20. 연구용 보완이며 실전 운용 승인이 아니다. `SAFE_TO_ACT=False` 및 `OBSERVE_ONLY` 유지.
기존 Mechanical Top15, K-Mechanical, SSM, 장기 모으기, TQQQ 자금 출처 정책에는 영향을 주지 않는다.

## 검증 경계

| 내용 | 근거/상태 | 적용 |
|---|---|---|
| Unicorn 13,873행, 마지막 유효 2020-02-10 | `breadth-source-followup-2026-10-19.md` 저장소 당시 다운로드·감사 | 과거 참고 데이터; 최근 A/C와 접합 금지 |
| McClellan Wayback 43개 파싱, 고유 2,086거래일, 2,203일 공백 | `reference/mcclellan-archive-audit-2026-10-20.json` 기존 결과 | 연속 과거 시계열로 간주 금지 |
| 중첩 1,605일 중 완전 일치 455일(28.35%) | 저장소 Unicorn/McClellan 비교 JSON | 통합 데이터셋으로 승격 불가 |
| Carson A: 1970~2020 11/11 날짜 일치 | `reference/reconciliation-summary.json` | 부분 날짜 대조만 통과 |
| Carson C: 5개 원문 사건 모두 탐지, 추가 3건 | `reference/unicorn-carson-date-comparison.csv` | 공식 suppression 기준 미상 |
| VIX 첫 506행의 OHLC 동일값 | 공개 `datasets/finance-vix/data/vix-daily.csv` 실제 날짜 대조 | **1990-01-02 ~ 1991-12-31** 구간; 1992-01-02부터 서로 다른 OHLC 관측 |

### VIX 원자료 날짜 정정

직전 외부 조사문에서 인용된 `1990-01-02~2004-06-11 초기 506행` 서술은 동일 기간/행 수가 양립하지 않는다. 공개 CSV에서는 1991-12-31 (19.31, 19.31, 19.31, 19.31) 다음인 **1992-01-02** (OPEN 19.69, HIGH 20.15, LOW 18.88, CLOSE 18.95)부터 네 가격이 구별된다. 이는 해당 *공개 미러의 실제 행*에 대한 확인으로, Cboe의 모든 역사적 수정본에 대한 별도 검증 완료를 뜻하지 않는다.

- 공개 파일: https://github.com/datasets/finance-vix/blob/main/data/vix-daily.csv
- 계산에는 기존 Cboe 종가만 사용한다. 1990~1991년의 비정상적으로 보이는 동일 OHLC를 임의 복원하지 않는다.
- 원본 비NYSE 날짜를 소거하거나 0/ffill로 대체하지 않는다. 원본 `vix.csv`와 `observations.csv`에 보존한다.
- VIX 품질 검사에서 달력 외 행만 `excluded_non_xnys_dates`로 기록하고 계산 대상에서 제외한다. 정상 XNYS 거래일의 실제 결측은 `missing_xnys_dates`에 기록하고 계속 `DATA_HOLD` 처리한다.
- FRED VIXCLS는 Cboe의 2차 재배포 채널이다. 동일 산출기관의 값이므로 독립 데이터 생성원이라고 표시하지 않는다. 확인되지 않은 결측값을 채우는 자동 보정 기능은 **미구현**이다.

## 최근 NYSE 관측: 연구 참고층만 강화

`data_quality.json.breadth_diagnostics` 와 생성 Markdown/HTML에는 다음을 명시한다.

- `as_of_session`: XNYS 마지막 완료 거래일
- `observed_session`: 연속성 여부와 별개로 실제 유효한 최근 관측일
- `source_freshness`: CURRENT / STALE / MISSING
- `advances`, `declines`: 최신 완료 거래일에 실제 유효 관측이 있을 때만 원자료의 상승·하락 종목 수
- `consecutive_valid_sessions`: 마지막 완료 거래일까지 이어지는 결측 없는 일수
- `recent_10_complete`, `ema100_warmup_complete`: 각각 10거래일 창, 100일 EMA 초기 구간 충족 여부
- `breadth_ratio`, `zbt_ema10`, `expansion_days_10`: 단지 McClellan 원자료로 계산한 연구 참고값
- `source`, `retrieval_timestamp`: 해당 입력의 출처와 검색시각
- `eligible_for_signal=False`, `ndr_comparability_validated=False`: 원문 대응 및 거래 허가가 아님

최근 무료 XLS와 오랜 과거 Unicorn을 연결하지 않는다. 특히 139거래일이라는 2026-10-16 조사 스냅샷의 행 수를 최신일의 값으로 하드코딩하지 않는다. 실제 실행일, XLS 수집 성공 여부, `observed_session`을 구분한다.

### 소스·정의 판단

1. McClellan의 최근 관측은 WSJ Markets Diary 확정치를 참고한다고 설명하지만, 개별 일자의 WSJ 최종 스냅샷과 일대일 수치 비교는 아직 실행하지 않았다. 임의의 'WSJ VERIFIED' 상태를 부여하지 않는다.
2. `A/(A+D)`에서 보합을 제외하고, 10 EMA(`alpha=2/11`)와 엄격한 `<0.40` → `>0.615` 경계를 유지한다. Day 0은 마지막 하단 이탈 날짜이며 재이탈 시 재설정한다. Morris/Colby 문헌 해석과 1986년 단행본 소재에 관한 주장은 원문 확보 수준을 분리한다.
3. Carson C의 6/10일, 70% 초과 원문 외에 *신호 suppression* 규칙 및 A+D+U 분모는 확정되지 않았다. 10일 쿨다운은 **MBSS 연구 가정**이다. 8/8 표본에 맞춰 쿨다운을 역추정하지 않는다.
4. SPY holdings proxy, S&P 500 공식 PIT Breadth, NYSE Composite A/D는 다른 모집단이다. SPY 보유목록을 과거로 소급하거나 A/C 판정에 투입하지 않는다.
5. `^SP500TR`은 Yahoo 비공식 유통 심볼이며, 일별 시계열을 실제 다운로드·검증하지 않은 구간에 TR을 만들어내지 않는다. SPY 배당조정 수익률은 공식 SPXTR과 구분한다.

## 미완료 우선순위

- **P2 WSJ 확정치 수치 대조**: 관측일, 마지막 마감 이후 확정 시각, 값 변경 이력, McClellan 중복 비교를 기록할 별도 명세와 테스트가 필요하다. 웹 페이지 설명 확인만으로 자동 데이터 수집을 약속하지 않는다.
- **P3 A 정의**: EMA 2/11 대 McClellan 18% 표기, 시드·워밍업·10거래일 카운트의 민감도를 원문/관측 기준으로 추적한다.
- **P4 C 중복 정의**: Carson/NDR 명세 원문 확보 전까지 추가 1982-10-18, 2009-09-15, 2011-11-03을 소거하지 않는다.
- **P5 장기 원자료**: 무료 무인증 연속 NYSE Composite A/D 파일은 *이번 조사에서 미확보* 상태. 존재하지 않는다고 일반 명제화하지 않는다. 유료 제공처의 사용권/재배포 조건을 우회하지 않는다.
- FRED와 Cboe의 구체적 결측 거래일을 실제 값으로 교차검증하고, 출처별 행 검증 뒤에만 추후 결측 보완을 고려한다. 현재는 **자동 보완 없음**.

## 변경 범위와 검증

`src/mbss/collectors/quality.py`, `src/mbss/pipeline.py`, `src/mbss/reports/render.py` 및 관련 단위테스트를 수정한다. 원본 데이터 출처 및 A/B/C/D 수식, 복합 신호, 백테스트, 실전 승인 로직은 변경하지 않는다. 새 참고 필드가 보고서에 등장하더라도 `SAFE_TO_ACT=False`가 유지되어야 한다.
