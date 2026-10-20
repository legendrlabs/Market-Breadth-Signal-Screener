# MBSS v0.1.3 — McClellan 게시 페이지와 XLS 동일 공급원 교차감사

기준일 2026-10-20. WSJ 직접 확정치와 Carson/NDR의 내부 NYSE 브레드스를 확보하지 못한 상태에서, 확인 가능한 **McClellan 자체 웹페이지와 무료 XLS가 같은 날짜·수치인지** 점검한다.

## 실제 외부 원문 열람으로 확인한 사실

- https://www.mcoscillator.com/market_breadth_data/ 에는 **NYSE: 10/19/2026**, Issues Advances **961**, Declines **1751**, Difference **-790**이 게시되어 있다. 이 값은 McClellan 공개 페이지 **하루의 집계**다. A/(A+D)=**961/2712≈35.43%**이고 10일 EMA가 아니다.
- McClellan 운영 설명에 따르면 최종 NYSE 일별 수치는 WSJ/Barron's에 의존하며 최초/장 마감 직후 잠정 값과 달라질 수 있다. *McClellan 자기 페이지와 자기 XLS가 같다는 사실은 독립적인 WSJ 원자료 검증이 아니다.*
- WSJ https://www.wsj.com/market-data/stocks/marketsdiary 페이지의 공개 HTML 텍스트에서는 실제 최종 NYSE A/D 종목 수를 읽지 못했다(Loading). WSJ 숫자를 961/1751이라고 단정하지 않는다.
- Reuters는 2026-10-19 장 마감에 NYSE와 Nasdaq 모두 하락 종목이 상승 종목보다 많았다고 서술한다. 다만 Reuters 서술은 McClellan 개별 카운트 숫자의 직접 교차검증이 아니다.
- QuantShare object 453은 NYSE 상승/하락/보합 수 다운로드 스크립트라고 공개 설명하지만 다운로드하려면 로그인/QuantShare 프로그램이 필요하며, 2020년 이후 연속 원시 A/D, 원천/라이선스/개별 파일은 확보하지 못했다. `CANDIDATE_NOT_ACQUIRED` 상태 유지. https://www.quantshare.com/item-453-nyse-advances-and-declines

## 구현

- `mbss collect`는 기존 무료 McClellan XLS와 독립적으로 동일 운영자의 공개 HTML 한 페이지를 한 번 내려받는다. 실패는 기존 XLS나 다른 수집에 영향을 미치지 않는다.
- 날짜·NYSE Issues *Advances*, *Declines*, *Difference*를 파싱한다. 차이값 `Advances - Declines`이 맞지 않으면 거부한다. Oscillator/거래량/기사 제목의 숫자를 NYSE 이슈 카운트로 파싱하지 않는다.
- 실제 HTML 원본은 실행 고유 `data/raw/<timestamp>/mcclellan_publisher_page.html`로 보관·SHA256 기록한다. 공급원 약관에 따라 원본 HTML을 코드 저장소나 연구 아티팩트에 무단 재배포하지 않는다.
- `data/normalized/publisher_page_snapshot.json`에 날짜·원본 해시·수집 시각·출처 URL을 기록한다. 다운로드/파싱 실패 시 상태를 명시하며 이전 정상 수치를 재사용하지 않는다.
- `mbss run`은 `publisher_page_reconciliation.json`을 생성하고 Markdown/HTML에서 다음을 분리한다: `COUNTS_MATCH_SAME_PUBLISHER_ONLY`, `COUNTS_DIFFER_SAME_PUBLISHER`, `PUBLISHER_PAGE_STALE`, `XLS_DATE_MISSING_OR_INVALID`, `NO_PUBLISHER_PAGE`, `REFERENCE_NOT_COMPARABLE`.
- **최종 완료 NYSE 정규거래일**만 비교하며 날짜가 최신 완료 세션과 다르거나, 출처·수집시각·숫자·해시를 검증하지 못하면 결과를 승격하지 않는다.
- 원시 XLS 및 게시 페이지의 불일치를 수정/보간하지 않는다. `eligible_for_signal=False`, `independent_source=False`, `wsj_independently_verified=False`, `ndr_comparability_validated=False`, `safe_to_act=False`로 고정한다.
- 앞서 추가한 독립 WSJ 캡처 대조(`wsj_reconciliation.json`)는 **그대로 별개 기능**이며, 실제 WSJ 캡처 없이는 `NO_WSJ_REFERENCE`가 정상이다.

## 여전히 미완료

1. WSJ 최종 NYSE A/D의 날짜별 직접 확보·McClellan 교차 검증. 동일 발행사의 HTML·XLS 값이 일치해도 P2가 완전히 해결되는 것은 아니다.
2. Carson/NDR의 신호 C Suppression 규칙·분모 원문 확보. 1982-10-18, 2009-09-15, 2011-11-03 추가 후보 3건은 삭제하지 않는다.
3. 무료·키 없는 2000~2026 NYSE Composite 연속 원시 A/D 데이터. Unicorn 2020년 이후 중단, McClellan Wayback 43개는 2,086일 및 2,203거래일 공백 상태 그대로다.
4. 공식 일별 S&P 500 과거 PIT 구성과 폐지종목 가격·SPXTR 보강 및 VIX FRED/Cboe 관측일 실증 확인.

**연구용 진단 확대일 뿐 신호 승인 아님:** A/C `DATA_HOLD`, 전체 `SAFE_TO_ACT=False`, `OBSERVE_ONLY`. Mechanical Top15/K-Mechanical/SSM/TQQQ/장기 투자 운용 규칙은 변경하지 않는다.
