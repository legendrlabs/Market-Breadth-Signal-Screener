# MBSS v0.1.3: WSJ 확정치와 McClellan NYSE A/D 교차감사 (2026-10-20)

**판정: P2 비교 실행기는 구현했으나, WSJ의 실제 최종 수치 파일을 확보·대조하지 못했다. 실측 일치 건수 0 (미관측). DATA_HOLD 및 SAFE_TO_ACT=False 유지.**

## 근거별 분리

### 직접 확인한 공급원 설명
- [Tom McClellan, 2025-11-28](https://www.mcoscillator.com/learning_center/weekly_chart/watching_for_a_zweig_breadth_thrust_signal/): 최종 ZBT 계산에 WSJ Markets Diary 자료를 사용하고, 장중/장마감 직후에는 Preliminary 값이 있으며 최종 값은 늦게 발표된다고 기술한다. EMA10의 계수는 `2/11`로 설명하며 계산상 약 0.18로 표기한다. 가장 최근 `<0.40` 거래일을 Day 0으로 설명한다.
- [McClellan 무료 Breadth 페이지](https://www.mcoscillator.com/market_breadth_data/): WSJ/Barron's 최종 집계치를 사용하며 초기 발표 값과 차이가 날 수 있다고 설명한다. 비공개 전체 역사 아카이브 구매도 안내한다.
- [WSJ U.S. stocks](https://www.wsj.com/market-data/stocks/us): Markets Diary 미국 시장 개요는 모든 미국 거래소를 포함하며 최대 미국 동부시간 **20:00까지 갱신**될 수 있다고 주석에 표시한다. NYSE 열과 Nasdaq 열을 혼동하지 않아야 한다.
- [WSJ Markets Diary](https://www.wsj.com/market-data/stocks/marketsdiary): 이번 HTML 텍스트 열람에서 숫자 표가 `Loading...`으로만 표시되었다. 2026-10-19/20 일별 NYSE A/D 최종 숫자는 확보하지 못했으므로 **현재 실제 수치 비교는 불가능**하다.
- [Carson Group, 2025-04-25](https://www.carsongroup.com/insights/blog/houston-we-have-a-zweig-breadth-thrust-and-four-more-bullish-developments/): C 조건은 10거래일 중 6일 이상 70% 초과 상승 참여로 기술하지만 사건 Suppression/Cooldown의 정확한 기계적 규칙과 분모 정책을 명시하지 않는다.

## 구현된 선택적 감사

선택적 파일 `data/normalized/wsj_reference.json`에 **합법적으로 확보한 WSJ NYSE 열의 날짜별 캡처 정보**를 수동/승인된 방법으로 입력한다. 샘플은 **합성 구조 예시**이며 실측값이 아니다.

```json
[
  {
    "date": "2026-10-16",
    "source": "https://www.wsj.com/market-data/stocks/marketsdiary",
    "universe": "NYSE",
    "stage": "FINAL",
    "advances": 100,
    "declines": 200,
    "captured_at": "2026-10-17T01:30:00Z",
    "evidence_url": "https://example.org/replace-with-real-dated-evidence"
  }
]
```

**경고:** 날짜·수치·증거 URL 모두 예시이며 위 파일을 실제 입력으로 투입하면 안 된다. WSJ 출처의 정확한 날짜가 드러나는 화면 또는 원시 기록에 근거해 작성해야 한다. 캡처/확정시각이 `captured_at`에 정확히 기록돼야 한다. WSJ 데이터의 이용약관을 준수하며 자동 스크레이핑·로그인 우회·유료 데이터 재배포를 추가하지 않았다.

- `stage=FINAL`은 자료 입력자가 주장하는 상태이며, **프로그램이 WSJ의 최종성 또는 NDR 동등성을 인증하지 않는다**.
- conservative gate: 해당 날짜 NYSE 정규 세션이어야 하고, 시각이 붙은 캡처는 20:00 미국 동부시간 이후·보고서 `as-of` 이전이어야 한다. 이 기준은 수집의 일관성을 돕는 필터이며 **그 자체로 최종 확정 증빙은 아니다**.
- 증거 링크·NYSE 모집단·출처 URL·정수/비음수 수치·관측일·중복 여부를 검사한다. 실제 입력의 마지막 완료 거래일 이후 데이터 및 Preliminary는 대조에 넣지 않는다.
- 기존 McClellan 공식 XLS 원천 `https://www.mcoscillator.com/data/osc_data/OSC-DATA.xls`가 메타데이터에 표시된 경우에만 두 관측치를 비교한다. 다른 공급원의 A/D를 McClellan으로 위장하지 않는다.
- 종목 수 2개가 모두 정확히 같으면 `COUNTS_MATCH_REFERENCE_ONLY`, 하나라도 다르면 `COUNTS_DIFFER`와 부호 있는 차이를 출력한다.
- 출처 원시값을 서로 대체하거나 과거 날짜를 메우지 않는다. 비교 성공 여부와 무관하게 `eligible_for_signal=False`, `same_universe_verified=False`, `ndr_comparability_validated=False`, `safe_to_act=False`.
- 원본 사용자 입력 SHA256은 기존 `run_manifest.json.input_sha256`에 보존되고, 감사 결과는 같은 실행의 `wsj_reconciliation.json`과 `latest.md`/`latest.html`에 기록된다.
- 선택 입력이 없으면 `NO_WSJ_REFERENCE`, 형태가 잘못되면 `INVALID_WSJ_REFERENCE`; 실제 수치가 없는데 일치율이나 WSJ VERIFIED를 임의 출력하지 않는다.

## 여전히 미확인

### Carson C 추가 3건
기존 Unicorn 부분 재현에서 원문에는 없는 1982-10-18, 2009-09-15, 2011-11-03이 탐지됐다. [Carson 사건표 전사](reference/carson-2025-04-25-events-as-printed.csv), [부분 날짜 비교](reference/unicorn-carson-date-comparison.csv)는 참조 자료다. 원문에 suppression 정책이 없으므로 6개월, 63거래일 등으로 쿨다운을 맞춰 8/8을 '재현'하지 않는다.

### 무료 장기 NYSE 연속 시계열
[Unicorn](https://unicorn.us.com/advdec/)의 갱신 중단과 [기존 43개 McClellan 보관본의 불연속](reference/mcclellan-archive-audit-2026-10-20.json)은 해결되지 않았다. 거래소 [NYSE Historical](https://www.nyse.com/market-data/historical)는 일반적으로 체결·호가 데이터 상품을 안내하며, 원문과 정의가 같은 무료/무키 2000~2026 A/D 연속 파일을 이번 조사에서 확보하지 못했다. **공개 웹 전체에 존재하지 않는다고 단정하지 않는다.**

### 추가 무료 후보 — QuantShare 다운로드 스크립트 (미검증)

[QuantShare NYSE Advances and Declines](https://www.quantshare.com/item-453-nyse-advances-and-declines)는 무료 QuantShare 소프트웨어 안에서 `$ADV`/`$DECL`/`$UCHG` 일별 과거 데이터를 내려받는 스크립트라고 설명한다. **실제 스크립트 코드·다운로드 엔드포인트·2020년 이후 연속성·최종 자료 공급원·NYSE Composite 정의·라이선스는 열람/재현하지 못했다.** 기존 Unicorn과 같은 중단된 원천을 다시 포장한 것인지도 모른다. 따라서 `CANDIDATE_NOT_ACQUIRED`이며 수치 0건, 검증 완료나 무인증 자동화를 주장하지 않는다.

## 남은 P2 실측 검증 단계

1. WSJ의 날짜별 NYSE 열 (Final이라고 실제 표시된 근거) 을 합법적으로 확보하고 `evidence_url`, `captured_at`을 기록.
2. 같은 날짜의 McClellan A/D 원본 XLS, SHA256, 수집시각과 비교. 잠정치·마감 수치·수정본을 별도 이벤트로 기록.
3. 5~20거래일의 감사 표본으로 원천 일치/차이를 기록한 뒤 원자료 수정 이력과 NYSE Composite 모집단 정의를 조사. 일치하더라도 NDR 동등성과 A/C 실전 신호 승격은 별도 검증 필요.

이번 변경은 장기 적립·TQQQ·Mechanical·SSM 투자규칙 또는 A/B/C/D 신호 조건을 변경하지 않는다.
