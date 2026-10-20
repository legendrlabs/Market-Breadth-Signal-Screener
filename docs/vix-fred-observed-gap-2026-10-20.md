# MBSS v0.1.3 — 1999-12-31 VIX 결측과 FRED 관측값 보완

검증 시점: 2026-10-20. 기존 정책 `SAFE_TO_ACT=False` / A·C `DATA_HOLD`은 변경하지 않는다. 데이터 제공 약관을 준수하며 원본 공급원 데이터를 저장소 릴리스에 배포하지 않는다.

## 실제 외부 자료 검증

- **1999-12-31은 실제 NYSE 거래일**: 미국 SEC는 당시 증권거래소들이 연말 전환에도 거래했고 오후 1시에 장이 종료됐음을 발표했다.
  https://www.sec.gov/newsroom/press-releases/99-177-foreign-markets-experience-millennium-change-its-business-usual-us-securities-markets
- **FRED VIXCLS 날짜 관측값 24.64**: 1999-12-30 24.76, 1999-12-31 **24.64**, 2000-01-03 24.21이 FRED CBOE Volatility Index: VIX 일별 자료에 기록돼 있다.
  https://fred.stlouisfed.org/data/VIXCLS
- Cboe 원본 `VIX_History.csv`가 해당 날짜를 누락했기 때문에, 2026-10-20 MBSS 실제 실행의 VIX 품질에는 `MISSING_SESSIONS` 1일이 기록됐다. `1999-12-31` 결측은 거래일 정의 오류가 아니다.
- **FRED는 Cboe VIX 관측의 재배포 채널**이다. 별도 거래소·산출기관의 독립 확인이라는 주장은 하지 않는다.

## 엔진 구현

1. `mbss collect`가 새 Cboe VIX 파일을 정상 내려받았을 때만 `vix.csv`를 검사한다. Cboe 서버 오류·이상 CSV·달력 검증 실패에서는 복구하지 않는다.
2. XNYS `exchange_calendars`의 완료된 세션 중 **Cboe CSV에 없는 정확한 날짜만** 찾아 `FRED VIXCLS` 공개 CSV의 해당 날짜를 요청한다. 최대 결측 20일의 안전 상한을 둔다.
3. FRED의 **양의 유한 실측값**이 모든 결측 거래일에 존재해야만 원본 Cboe 관측을 유지하면서 해당 날짜만 추가한다. 값이 `.`, 빈칸, 0, 음수, 비숫자, 날짜 중복·미존재면 **일괄 복구하지 않는다**. 보간·전일값 유지·0 대입 금지.
4. 새 `vix.csv`는 날짜 정렬된 계산용 합본이지만, 최초 Cboe 원본과 FRED 원본은 각각 실행별 `raw/vix.csv`, `raw/fred_vixcls.csv`에 해시와 함께 보존된다. 별도 `vix_recovery.json`에 결측일·정확한 관측값·원본 SHA256·실패 원인·자료 출처를 기록한다.
5. `metadata.json.vix.supplemental_observations[YYYY-MM-DD]`에 FRED 해당 행의 2차 출처를 기록한다. `observations.csv`에서는 복구된 날짜 행에만 FRED 시리즈 URL 및 다운로드 시각을 사용하고 나머지 날짜는 Cboe 원천으로 표시한다.
6. `data_quality.json.vix_recovery` 와 `latest.md`/`latest.html`에 실제 복구 상태를 표시한다. `run_manifest.json.input_sha256`은 복구 감사 파일과 정규화된 입력을 해시한다.
7. Cboe 전체 시계열이 유효하고 미해결 결측이 없다면 VIX 데이터셋만 `PASSED_RESEARCH`로 변경될 수 있다. **이는 전체 MBSS 승인 또는 NYSE A/C 원자료 검증을 의미하지 않는다.**

## 후속 검사

- 실제 GitHub Actions에서 FRED Graph CSV에 키 없이 접근되는지, 1999-12-31 날짜값 `24.64`가 **실제 다운로드 결과**인지 확인한다. 원문 인터넷 열람의 값만으로 실행 성공을 주장하지 않는다.
- API가 403·5xx이거나 다운로드에 관측값이 없으면 `FRED_DOWNLOAD_OR_PARSE_FAILED` / `FRED_OBSERVATIONS_INCOMPLETE`를 유지하고 VIX는 DATA_HOLD를 지속한다.
- NYSE A/C 모집단 및 Carson/NDR 중복 제거 정의는 별도 과제. FRED 보완은 독립적으로 그 문제를 해결하지 않는다.

## 2026-10-20 첫 실전 실행과 공식 FRED 대체 주소

병합 후 GitHub Actions `39372735233`에서 Cboe VIX 다운로드는 성공했지만,
`https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS&cosd=1999-12-31&coed=1999-12-31`가 `TimeoutError: The read operation timed out`로 실패했다. 원 Cboe CSV·metadata의 해당 세션은 수정하지 않았고, 실전 보고서 VIX는 `MISSING_SESSIONS` / `DATA_HOLD`로 남았다.

따라서 FRED가 공개하는 동일 시리즈의 **서버 렌더링 표**
`https://fred.stlouisfed.org/data/VIXCLS`를 대체 경로로 추가한다.
첫 Graph CSV 요청이 실패·누락되면 게시 표를 내려받아 `Series ID VIXCLS`,
`Chicago Board Options Exchange`, `DATE VALUE` 레이블을 확인하고,
그 안의 실제 날짜별 관측을 추출한다. 페이지 HTML의 임의 기사·스크립트·
다른 시리즈 수치를 사용하지 않는다. 양쪽 소스 모두 실패하면 원자료를 유지한다.

동일 FRED 발행사의 **다른 표현 방식**을 재시도하는 것이므로 공급원 독립 검증은 여전히 성립하지 않는다. 실제 라이브 수집 성공은 새 브랜치의 테스트 통과만으로 주장하지 않고 별도 일일 실행의 감사 JSON으로 확인한다.

## 2026-10-20 FRED 접근 제한 — Yahoo ^VIX 재배포 관측값 최종 후보

GitHub Actions `39373679546`에서 FRED Graph CSV와 공식 Table Data 모두 `TimeoutError: The read operation timed out`가 발생했다. 자료가 확인되지 않았기에 `FRED_DOWNLOAD_OR_PARSE_FAILED`과 VIX `MISSING_SESSIONS`을 그대로 보존했다.

동일 Cboe 지수의 또 다른 무료 배포 경로 `Yahoo Finance ^VIX`로부터 **날짜별 실제 종가**를 받는 연구 보완을 추가한다. Yahoo는 지수 산출기관이 아니고 보조 배포처이다. 매 요청에서 `chart.result.meta.symbol`이 정확히 `^VIX`인지 확인하며 뉴욕 현지 거래일로 원시 유닉스 타임스탬프를 변환한다. FRED 두 경로가 실패한 때에만 최근/과거 관측 시계열을 다운로드한다.

복구에 필요한 모든 날짜의 Yahoo 관측이 존재하는 것만으로는 부족하며, **누락 구간 직전과 직후의 실제 Cboe 원본 종가 모두와 0.02포인트 이내 일치**해야 한다. 같은 요청 구간의 모든 공통 Cboe/Yahoo 날짜도 비교해 불일치가 하나라도 있으면 일괄 거부한다. Yahoo 숫자의 내부 float 오차는 저장 시 소수점 둘째 자리로 정규화하지만 원시 JSON과 `provider_raw_close`는 별도 보존한다.

출처는 보완된 특정 날짜의 `observations.csv`에만 `https://finance.yahoo.com/quote/%5EVIX/history/`로 기록하고, 기본 Cboe 관측 일자는 그대로 유지한다. Yahoo 비교는 *다른 배포 경로의 동일 지수 값 일관성* 검사일 뿐 역사적 재계산에 의한 독립 지수 검증이 아니다.

새 GitHub Actions 실행에서 실제 Yahoo 과거 ^VIX 관측값이 내려오는지 확인하기 전에는 복구 완료로 판정하지 않는다.

## 2026-10-20 실제 실행 재검증 — 결측 해소 완료

- **main 커밋** `9ed6a0dffb3d8960062205650e13ccf9e602fdaf` / **GitHub Actions** [#39374487312](https://github.com/legendrlabs/Market-Breadth-Signal-Screener/actions/runs/39374487312).
- 실제 Cboe 원본 다운로드 성공(원본 SHA256 `dd316faa6120a323845988c180d9d2297af29c7d4495c84d6e3e76af3f19d199`). FRED Graph CSV·HTML 모두 읽기 타임아웃.
- Yahoo `^VIX`의 **원본 시계열 JSON** 다운로드 성공, SHA256 `983818f355931c5eb3bf593f6cdc02d3eb878c48564713dbba3122789c1f8780`. 1999-12-31 Yahoo 원시 실수 `24.639999389648438` → Cboe 발행 소수 둘째 자리 `24.64`로 표준화.
- Cboe/Yahoo 공통 날짜 `1999-12-27,28,29,30`, `2000-01-03,04,05,06,07`의 9개 종가 **9/9 모두 오차 허용(0.02p)** 통과. 원 Cboe 관측일은 변경하지 않음.
- `runs/daily/vix_recovery.json`: `RECOVERED_OBSERVED_YAHOO_CBOE_DISTRIBUTION`, `recovered[0].date=1999-12-31`, `recovered[0].close=24.64`, `unresolved_xnys_dates=[]`. 복구 날짜의 행별 출처는 Yahoo ^VIX로 보존.
- `runs/daily/data_quality.json.datasets.vix`: `PASSED_RESEARCH`, `missing_count=0`, `fresh=true`, `history_valid=true`. 전체 `status=DATA_HOLD` 및 `SAFE_TO_ACT=False` 유지. NYSE Breadth의 `UNIVERSE_UNVERIFIED`, `REFERENCE_COMPARABILITY_UNVERIFIED`는 해결되지 않았다.
- 이 성공은 Cboe가 산출한 같은 VIX 지수의 **서로 다른 배포 경로(Cboe·Yahoo) 값 대조**다. FRED 원문은 웹 조사에서 24.64가 확인되었지만 실전 러너에서 원문 데이터 다운로드가 성공한 것은 아니다. Yahoo도 독립 산출기관이 아니다.

이후 CI/일일 보고에서 VIX 데이터 품질이 다시 실패하면 같은 날짜의 자동 복구를 보장한 것으로 간주하지 않는다. 라이브 실행별 감사 JSON과 SHA를 기준으로 판단한다.
