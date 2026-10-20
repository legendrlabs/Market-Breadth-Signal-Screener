# MBSS v0.1.3 — NYSE A/D 모집단 근거와 Carson C 신호 정의 감사

2026-10-20. **신호·백테스트·자금배분은 변경하지 않으며 `SAFE_TO_ACT=False`를 유지한다.**

## 1. McClellan 자료의 모집단: 확인된 것 vs 아직 입증되지 않은 것

### 원문으로 확인되는 범위

McClellan Market Data Questions의 [A-D Data: Composite, or Operating Companies Only](https://www.mcoscillator.com/learning_center/kb/market_data/a-d_data_composite_or_operating_companies_only/)는 McClellan이 대부분의 시장분석에 **composite NYSE A/D and volume** 수치를 사용한다고 설명한다. `Common Only`는 **별도 시계열**이며, NYSE Composite Index 편입종목 1종 보통주 등으로 제한되는 선택적 필터이다.

원문에는 McClellan 자료의 Barron's/WSJ 최종 수치 우선 정책과 공급원별 A/D 숫자 차이가 날 수 있는 이유도 설명된다. 모든 A/D 제공자는 상장 이슈 목록, 전일 및 당일 최종 종가, 분할 조정 등을 자체 재구성하거나 제3자 숫자를 재전송해야 하므로 계산방식이 다를 수 있다.

**주의할 2005-02-09 변경:** 원문에서 이 날짜에 변경된 것은 NYSE가 Barron's에 제공하는 `Common Only` 집계다. 3글자 초과 심볼을 걸러내는 옛 방식에서 NYSE Composite Index 구성종목 중심 방식으로 바뀌었다. **McClellan composite 전체 A/D의 2005년 중단점이라고 쓰면 안 된다.** 이 변경은 다른 모집단의 역사적 A/D로 대체할 때 특히 중요하다.

McClellan의 [2017-03-24 글](https://www.mcoscillator.com/learning_center/weekly_chart/why_dont_we_use_just_common-only_a-d_numbers/)은 Composite NYSE에 우선주·채권 관련 폐쇄형 펀드 등 여러 유형의 이슈가 포함될 수 있음을 지적한다. 그러나 이것만으로 최근 XLS의 ETF/우선주/CEF/REIT 각각의 실제 포함 플래그나 과거 시점별 구성 파일을 확보한 것은 아니다.

### 명확히 **미검증**

- 날짜별 구성종목 고유 ID/PIT roster, 중복 주식 클래스·ETF·우선주·CEF·REIT의 정확한 편입/제외 기준
- McClellan의 무료 NYSE composite 이슈 수와 Carson/Ned Davis Research 과거 A/D 표본의 **동일 모집단 여부**
- 당일 최종 WSJ 실측 2026년 전체 기간의 독립적인 대조. McClellan 동일 발행사 웹 ↔ XLS 비교는 성공했지만 독립 공급원 인증이 아니다.
- Unicorn 자료와 McClellan의 A/D 수가 중첩 1,605일 중 정확히 일치한 날짜는 455일(28.35%)에 불과하다. 이 둘은 동일 시계열로 이어붙일 수 없다.

따라서 `metadata.json.breadth.provider_declared_scope`에 제공자의 **범위 설명**만 기록하고, 실제 `universe`의 ETF/우선주/CEF/PIT 포함 불리언은 여전히 `null`로 남긴다. `UNIVERSE_UNVERIFIED` 및 `REFERENCE_COMPARABILITY_UNVERIFIED` 품질 경고를 유지한다.

## 2. C 신호: 원문 기재사항과 연구자의 추가 규칙

[Carson Group 2025-04-25 기사](https://www.carsongroup.com/insights/blog/houston-we-have-a-zweig-breadth-thrust-and-four-more-bullish-developments/)는 **10거래일 중 6일 이상에서 NYSE 상승 참여율이 70%를 초과**한 사례를 2025년에 확인했다고 서술한다. 표에 과거 8개 성숙 사례와 2025-04-23의 신규 사례가 함께 실렸다. 원문 설명에 **중복 신호 묶음 규칙, 보합 종목을 분모에 넣는지, 70%와 정확히 같은 날의 포함 여부, 2005년 같은 모집단 변경의 조정 여부**는 충분히 명시되어 있지 않다.

### 이미 확보된 역사적 부분 대조

1970년 이후 Unicorn 합성 자료로 **기존 MBSS 6/10, `A/(A+D)>0.70`, 첫 진입, 쿨다운 10거래일**이라는 독자 규칙을 탐색했을 때 8개 C 후보 중 5개는 Carson의 인쇄 날짜와 일치하고, 다른 3개는 표에 없다.

| 인쇄표에 없는 Unicorn 후보 날짜 | 상태 |
|---|---|
| 1982-10-18 | `EXTRA_UNEXPLAINED` |
| 2009-09-15 | `EXTRA_UNEXPLAINED` |
| 2011-11-03 | `EXTRA_UNEXPLAINED` |

이들은 **삭제하거나 정답 맞추기 위한 임의의 장기 쿨다운을 적용하지 않는다.** Unicorn이 2020-02-10까지만 유효해 Carson의 2020·2023·2025 표본을 검증하지 못하고, 1962 표본은 현재 MBSS의 XNYS 1970년 달력 검증 범위 밖이다. 따라서 "Carson 8/8 공식 재현"이라고 선언할 근거가 없다.

- [원문 그림에서 기록한 날짜표](reference/carson-2025-04-25-events-as-printed.csv)
- [기존 부분 날짜 대조](reference/reconciliation-summary.json)
- [43개 McClellan 보관본 감사](reference/mcclellan-archive-audit-2026-10-20.json)

## 3. 새 독립 연구 커맨드: `mbss audit-c`

```bash
mbss audit-c \
  --input-csv /path/to/lawfully-obtained-daily-nyse-advances-declines.csv \
  --reference-csv docs/reference/carson-2025-04-25-events-as-printed.csv \
  --source "actual source name and retrieval URL" \
  --as-of 2026-10-20T06:00:00Z \
  --output runs/c-audit-new
```

입력 CSV 스키마는 `date,advances,declines`; 있으면 `unchanged`를 추가할 수 있다. 날짜는 `YYYY-MM-DD`, 일별로 고유하고 오름차순이어야 한다. 결측·비숫자·음수·비정수·A+D=0은 **무관측**으로 취급하며 인위적 0 또는 이전 값을 생성하지 않는다. XNYS 달력에 없는 날짜는 계산 제외와 감사 대상으로 기록하고, 1970년 이전 날짜는 달력 미검증 범위라 계산에서 제외한다.

비교하는 연구 변형은 다음과 같으며 **어느 것도 Carson/NDR가 공표한 공식 쿨다운 규칙이라는 증거가 없다**.

| 연구 변형 | 70% 조건 | C 이벤트 정책 | 분모 |
|---|---|---|---|
| MBSS 현재 연구 기준 | 엄격한 `>70%` | rising edge + 10일 쿨다운 | `A+D` |
| 쿨다운 없음 | 엄격한 `>70%` | rising edge | `A+D` |
| 63일 쿨다운 | 엄격한 `>70%` | rising edge + 63일 | `A+D` |
| 경계 포함 | `>=70%` | rising edge + 10일 | `A+D` |
| 보합 포함 민감도 | 엄격한 `>70%` | rising edge + 10일 | `A+D+UNCHANGED` |

**11거래일 연속 유효한 관측**을 요구하여 신호 당일의 10일 창과 직전 신호 상태를 동시에 확인한다. 원문에 날짜만 있고 입력이 부족하면 `INCOMPLETE_11_SESSION_CONTEXT`, 데이터 기간 밖이면 `OUTSIDE_VALIDATED_CALENDAR_OR_DATA` 또는 `AFTER_DATA_WINDOW`를 남긴다. 비교 가능했던 인쇄 날짜 0건이면 `INSUFFICIENT_REFERENCE_COVERAGE`; 0/8 실패로 해석하지 않는다.

출력 `c_reconciliation.json`에는 입력/원문 날짜표 SHA256, 모집단 및 suppression 검증 보류, 버전별 매치/누락/추가 날짜가 남는다. `c_candidates.csv`에도 `eligible_for_signal=False`를 고정한다. 출력 디렉터리가 있으면 덮어쓰지 않는다. **`mbss run`, 정식 C 이벤트, 백테스트, 자산배분 로직은 이 커맨드의 결과를 읽지 않는다.**

## 남은 연구

1. Carson 또는 NDR로부터 *실제 표본선정 정책*, 쿨다운 및 70% 분모 정의에 대한 공개 원문/설명 확보
2. 1962년 포함 C 원표를 완전히 대조할 수 있는 달력·장기 NYSE 구성 검증
3. Unicorn 제공자가 중단한 2020년 이후를 포함하는 동일 모집단 연속 A/D 데이터 확보(키 없는 무료 원본 이번 조사에서는 미확보)
4. 서로 다른 자료 공급원 간 **동일 날짜 실제 이슈 수**에 대한 감사를 추가하고, 수정본·시차와 가격 분할을 검증

확인되지 않은 성과 통계의 100% 적중률은 실전 진입 근거가 아니며 `SAFE_TO_ACT=False`다.
