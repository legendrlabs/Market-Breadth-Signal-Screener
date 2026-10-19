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

첫 원격 CI·실자료 실행·프리릴리스 링크는 실제 확인 후 기록한다. 워크플로 파일 존재만으로 원격 실행 완료를 주장하지 않는다. Actions 한도·저장 공간·공급원 접근은 계정과 환경에 따라 제한된다.
