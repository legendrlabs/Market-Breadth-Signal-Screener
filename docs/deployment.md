# GitHub 연구 배포

대상: https://github.com/legendrlabs/Market-Breadth-Signal-Screener

2026-10-19 사용자가 만든 빈 저장소의 쓰기 권한을 확인했다. 초기 데이터 제외 규칙만 main에 기록하고, 기존 독립 개발 브랜치의 코드·테스트·설정·문서를 PR로 등록한다. 이전 연구 문서의 GitHub 404와 로그인 제한은 당시 접근 시도에 대한 기록이다.

## 실행 흐름

- `ci.yml`: push/PR에서 Python 전체 테스트, Node 배포 검사, 실제 달력 의존성, 빈 입력 DATA_HOLD 보고서를 검증한다.
- `daily.yml`: UTC 23:17 월~금(다음 날 KST 08:17), 수동 실행 또는 main 버전 변경 때 무료 자료 수집을 시도한다. 실패에도 같은 실행의 품질 진단과 보고서를 생성한다.
- `release.yml`: main 버전 변경 또는 수동 실행 시 테스트와 DATA_HOLD 보고서를 검증한다. 테스트한 commit의 소스 SHA256을 `release.json`에 기록하고, draft에 업로드한 뒤 연구 prerelease로 공개한다. 기존 버전 태그와 manifest는 교체하지 않는다.

보고서는 [Actions](https://github.com/legendrlabs/Market-Breadth-Signal-Screener/actions)의 **MBSS daily research** 실행 아래 artifact에서 내려받는다. 필수 7개 파일과 보조 분석을 포함한다. 보고서 보관은 14일이며 결과를 자동 커밋하지 않는다. 수집 시점·마지막 완료 거래일은 각 보고서에서 확인한다.

실제 배포판은 [Releases](https://github.com/legendrlabs/Market-Breadth-Signal-Screener/releases)에서 확인한다. 소스 ZIP은 GitHub archive다. NYSE 연속 원자료와 원전 비교 가능성은 미해결이므로 공개 통계 주장은 UNVERIFIED, SAFE_TO_ACT=False다. 자동 주문·자금 배분은 없다.

## 배포 제외

공급원 raw/normalized 데이터, 원문 그림, 실행 결과, Python 환경, 인증정보와 개인 설정은 등록하지 않는다. 참고 사건 날짜 CSV는 원문 대조용이며 독립 신호 탐지 입력이 아니다. provenance 생성기는 data/runs 등 비소스 경로가 git에 있으면 거부한다.

## 로컬 실행

Python 3.10 이상에서 저장소를 내려받아 프로젝트 폴더 안에서 실행한다.

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python -m mbss.cli collect --input data/normalized --start 1999-01-01
python -m mbss.cli run --input data/normalized --start 2000-01-01
```

배포 유지관리 검사는 Node 24에서 `node --test tests/test_publish_release.cjs`로 실행한다. Node는 Python 분석 실행의 필수 의존성이 아니다. collect 종료코드 2는 수집 실패이며 이후 run으로 DATA_HOLD 진단을 생성할 수 있다. 새 출력 폴더를 사용한다.

Actions 한도·저장 공간·공급원 접근은 계정과 환경에 따라 제한된다.

## 확인한 첫 원격 실행 — 2026-10-19 KST

- [등록 PR #1](https://github.com/legendrlabs/Market-Breadth-Signal-Screener/pull/1) 병합, source commit `11e40fb926e19539d562e6b577f8f26a77c080b8`.
- [main CI](https://github.com/legendrlabs/Market-Breadth-Signal-Screener/actions/runs/39268895800), [연구 배포](https://github.com/legendrlabs/Market-Breadth-Signal-Screener/actions/runs/39268895665), [실자료 보고서](https://github.com/legendrlabs/Market-Breadth-Signal-Screener/actions/runs/39268895856) 모두 성공.
- [v0.1.0 prerelease](https://github.com/legendrlabs/Market-Breadth-Signal-Screener/releases/tag/v0.1.0)의 tag는 위 commit과 일치하고 manifest SHA256은 `69e39daec972b32721bdb56995a51789133afff3b15cb69e22da6061670b2f8c`로 로컬 동일 소스와 일치했다.
- [보고서 artifact](https://github.com/legendrlabs/Market-Breadth-Signal-Screener/actions/runs/39268895856/artifacts/12194971750)를 실제 다운로드하여 ZIP과 개별 출력 해시, 필수 7개 파일을 검사했다. 전체 결과 DATA_HOLD, SAFE_TO_ACT=False.
- 수집 2026-10-19 23:26 KST, 마지막 완료 NYSE 거래일 2026-10-16. SPX/SPY/QQQ는 1999년 이후 자료 검사를 통과했다. 진행 중인 10월 19일 자료는 각각 한 행 제외됐다. VIX는 결측 거래일 1개·NYSE 외 날짜가 있어 미승인, Breadth는 미확보다.
- 2000년 이후 B는 5회, 12개월 5/5 상승, 평균 +24.30%; D는 6회, 6개월 6/6 상승, 평균 +6.75%. 원문 전체 표본 재현과 구분한다. B 12개월 SPY 대기 전략 +217.91%, SPY 보유 +723.67%(현금 이자·비용 0 가정)로 단순 보유 대비 총수익 우위가 없다.

이 첫 artifact의 run_manifest.publication에는 개발 당시 NOT_PUBLISHED 상수가 남아 있었다. 실제 GitHub/릴리스 링크와 모순되는 표기 오류이며 v0.1.1에서 실행 repository·run·checkout 일치 근거를 기록하도록 수정한다. 첫 artifact나 v0.1.0 tag를 덮어쓰지 않는다. 수식·수익률과 SAFE_TO_ACT는 이 수정으로 바뀌지 않는다.
