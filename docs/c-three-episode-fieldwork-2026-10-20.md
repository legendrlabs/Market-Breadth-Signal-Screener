# MBSS P1: 세 건의 C 후보 미스매치 실측 조사

2026-10-20 기준. P1 이슈 [#13](https://github.com/legendrlabs/Market-Breadth-Signal-Screener/issues/13), 장기 소스 조사 P2 [#14](https://github.com/legendrlabs/Market-Breadth-Signal-Screener/issues/14).

## 확인된 기존 증거

Carson 2025-04-25 공개 C 인쇄표에는 1982-08-25, 2009-07-23, 2011-10-18의 C 사례가 있으나, MBSS가 1965–2020 Unicorn 합성 집계로 계산한 별도 후보 **1982-10-18 / 2009-09-15 / 2011-11-03**은 인쇄표에 없다. 출처는 `docs/reference/unicorn-carson-date-comparison.csv`의 날짜 목록이고, 이 저장소에 **세 사건의 원시 일별 A/D 관측값은 포함되지 않는다.**

Unicorn은 이슈별 상승/하락/보합 과거값을 무료 제공했으며 마지막 유효 시점이 2020-02-10이다. 공급원별 최종 A/D를 받아 여러 자료의 중앙값으로 결합한 복합 피드여서 WSJ·McClellan·NDR과 결과가 다를 수 있다. `https://unicorn.us.com/advdec/` / `https://unicorn.us.com/advdec/about.php` 참조. 현재까지 이슈 3건에 대한 *추가 실측*을 확보했다고 선언하지 않는다.

## 새 연구 도구: 세 에피소드 전용

```bash
mbss audit-c-episodes \
  --input-csv /path/to/observed_unicorn_nyse_breadth.csv \
  --reference-csv docs/reference/carson-2025-04-25-events-as-printed.csv \
  --source "Unicorn NYSE composite median, original URL" \
  --output runs/c-episodes-unique \
  --as-of 2026-10-20T06:00:00Z
```

선택적 교차검증은 `--comparison-csv /path/to/mcclellan_same_day.csv --comparison-source "McClellan URL"`을 명시한다. 원본 입력은 `date,advances,declines`, 확보 가능하면 `unchanged`를 포함한 정규화된 CSV다. 원문을 임의로 재구성하지 않으며, 직접 수집한 원본 파일과 별도의 SHA256을 자료 출처와 함께 보관한다. 두 공급원의 일별 값은 일치 여부만 비교하고 결측을 보정하기 위해 합치지 않는다.

산출물:
- `episode_audit.json`: 각 날짜의 11거래일 신호 확인 가능 여부, 6/10 일수, 원문 인쇄 이전 사건과의 NYSE 거래일 간격, 연구 정의별 이벤트 유지/삭제 변화, 동일 날짜 대조 가능량 및 불일치 목록
- `episode_daily_windows.csv`: 세 사건 각각 전후 63개 NYSE 거래일의 원시 상승/하락/보합 수, A/(A+D), 최근 10일 임계 초과일 수, 인쇄표 이벤트일 여부
- `episode_audit.md`: 사람이 검토하기 위한 사건별 비교 및 신뢰도 경고

**기존 daily run, 승인 이벤트 생성 코드, 포트폴리오 백테스트와 연결하지 않는다.** `eligible_for_signal=False` / `safe_to_act=False`는 고정이다. 모든 변형은 가설이며 Carson/NDR 실제 신호 suppression·PIT universe를 확정하지 못한다.

## 실제 실측 조사 순서

1. Unicorn 역사 데이터의 1982/2009/2011 구간을 세 열 이상으로 확보하고 raw URL·bytes SHA256·영업일 유효성을 확인. 날짜별 0/0, holiday 또는 특정 이슈 유형을 원본 그대로 남긴다.
2. 같은 구간 McClellan 빈티지 보관본이 실제 존재하면 동일 날짜 값만 대조한다. 1982는 공개 McClellan 보관본의 최초 기간인 2009-09-30보다 전이므로 해당 보관본으로는 직접 검증 불가능하다.
3. 세 후보 전후 각각 63영업일과 가장 가까운 Carson 인쇄일을 사건별로 비교한다. 예를 들어 쿨다운 63일 시나리오에서 후보가 사라져도 *정답*이 된 것이 아니다.
4. Carson/NDR 내부 규칙이나 동일 PIT 모집단을 확보하지 못하면 정식 결과는 `UNVERIFIED`로 유지. 교차검증 실측값이 없으면 `NOT_SUPPLIED`를 남기고 날짜별 금액·비율을 만들어내지 않는다.

## 병렬 유지 사항

P2는 장기 연속 데이터와 모집단 명세를 장기 조사한다. 기존 McClellan 오늘의 A/D, VIX, 최근 Breadth 참고 EMA 및 웹/XLS 동일 발행사 일치 감시는 그대로 유지된다. 원천 NDR 검증이 끝나기 전에는 C를 실전 주문 트리거로 전환하지 않는다.
