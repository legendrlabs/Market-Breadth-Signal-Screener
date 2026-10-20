# Input / provenance contract

Session dates are unique, ascending, timezone-naive `YYYY-MM-DD`. Empty or nonfinite values never become zeros. All price columns are numeric and positive, dividends nonnegative, high >= open/close/low, low <= open/close/high. Breadth counts are nonnegative integers with a positive sum; unchanged issues are excluded from A+D.

Metadata keys are dataset names: `spx`, `spy`, `qqq`, `vix`, `breadth`. Required fields are `source`, timezone-aware `retrieval_timestamp`, `definition`, `adjustment_method`, and `review_status`. Source review can be `documented` or `reviewed` for price data, but breadth requires `reviewed` plus a documented universe. An attestation records a review; it is not independently verified automatically by MBSS.

Example shape (illustrative, not an approved source):

```json
{
  "breadth": {
    "source": "https://provider.example/actual-download-url",
    "retrieval_timestamp": "2026-10-19T08:57:00Z",
    "definition": "NYSE advances and declines as published, excluding unchanged",
    "adjustment_method": "None; original issue counts",
    "review_status": "unreviewed",
    "universe": {
      "exchange": "NYSE",
      "etf_included": null,
      "preferred_included": null,
      "closed_end_fund_included": null,
      "point_in_time_membership": null
    },
    "universe_evidence": "",
    "comparability_to_ndr": "UNVERIFIED",
    "reference_comparability": {"status": "UNVERIFIED", "evidence": ""},
    "reviewer": "",
    "redistribution": "Provider terms apply"
  }
}
```

Never fill unknown inclusion flags with guesses. Inclusion fields must be JSON booleans, and point_in_time_membership must be true. A common-stock-only universe is a different research dataset and cannot silently replace all issues. Even a reviewed universe does not establish exact comparability to the Carson/NDR universe. A/C additionally require reference_comparability.status="reviewed_comparable" and evidence documenting the comparison. Unknown comparability keeps DATA_HOLD. This review attestation must be backed by an actual study; changing the label cannot prove equivalence. Record source changes and constituent-policy changes; do not append incompatible series under one metadata record. Revision history and historical universe evidence are required before promotion beyond research status.

Yahoo supplies split-adjusted OHLC and a splits/dividends-adjusted close. MBSS's original_value means the provider's published value, not a pre-split reconstructed original. For a dividend-reinvestment proxy, multiply same-day OHLC by adj_close/close; ratios cancel scale factors. This is an approximation with provider-dependent dividend conventions. Do not add `dividend` again to the adjusted series. An index `adj_close` is not accepted as proof of a true index total-return series. SPX total return remains null. FX is optional and is not implemented in this version.

Validation includes internal missing sessions, duplicated dates, non-session dates, source metadata and numeric shape. The historical gate is separate from freshness at the latest completed session. A stale dataset may support retrospective research but never a current confirmation. Leading unavailable years are reported through coverage dates, and strategy comparisons use the common observed window. Final ongoing trading-session rows are removed before calculation and counted in `future_or_unclosed_rows_excluded`.

`observations.csv` records source, observation_date, retrieval_timestamp, original_value, adjusted_value, missing_count, freshness and validation_status per input field. `data_quality.json` records flags, rows and start/end. The manifest hashes inputs/outputs and records the source retrieval attempts. Provider raw data are retained locally on download; they are excluded from the source release. No redistributable dataset license is inferred from public accessibility.


## v0.1.2 quality and context outputs

Dataset `reason_codes` and signal `DATA_HOLD_REASONS` separate SOURCE_UNAVAILABLE, INSUFFICIENT_HISTORY, VALIDATION_FAILED and STALE_DATA; detailed flags remain. Current SIGNAL_DATE is null when no active event exists; LAST_SIGNAL_DATE/LAST_SIGNAL_STATUS preserve expired history. D additionally exposes SEASONALITY_STATUS.

`data_quality.json.breadth_diagnostics` is unverified, source-only recent NYSE observation arithmetic. It is excluded from signals and event/portfolio results. Gaps reset EMA warmup and the ten-session count. The McClellan adapter requires DATE/NYSE/NYSE followed by ADV./DEC. and excludes blank rows and audited note rows with no numeric issue counts; partial numeric observations remain for validation. It never reads calculated oscillator/volume columns as counts. Existing user-imported breadth and metadata are preserved; incompatible new downloads go to breadth_candidate.csv/breadth_candidate_metadata.json.

Optional input `external_context.json` is a list of records with metric/value/universe/session_type/observed_at/retrieval_timestamp/source. It is copied into a separate output with eligibility always False. Missing exact observation time is OBSERVATION_TIME_UNKNOWN; future timestamps are flagged. No external value is merged into observed official metrics or the NYSE signal series. See breadth-live-research-2026-10-19.md for a schema example.


## v0.1.3 auxiliary snapshot

`auxiliary_breadth.json` is a collector-owned current snapshot, not an NYSE CSV. It records the issuer holdings date, original tickers/identifiers, supported Yahoo mappings, excluded records, original dated closes, download hashes, retrieval and completion times, errors and flags. Failure replaces the old collector snapshot with an explicit diagnosis. Raw downloads remain in the dated raw directory; no raw data is shipped in the release.

At report time revalidate snapshot date and retrieval/completion against as-of and the completed exchange calendar. Require the same latest session for holdings and prices and 100% prior/current daily close coverage. Unknown/intraday granularity is rejected. Never use live/extended-market prices to fill a missing close or shorten the denominator. Advancing share all = advances / (advances+declines+unchanged); active share excludes unchanged. All-unchanged active share is null. Source closes are Yahoo split-adjusted price proxies, not dividend-adjusted total returns.

The issuer file is SPY holdings, not certified index membership. Unsupported ticker records (including cash or unlisted claims) are separately audited rather than assigned returns. Current supported holdings count must fall in 450–550 to reject top-holdings tables; the range is a schema sanity check, not an index rule. No historical reconstruction, signal or backtest use is authorized. `eligible_for_signal` is always false. Auxiliary failure never changes whether an independently valid B or D is NO_SIGNAL.

External context requires finite numeric values; null/missing gets MISSING_VALUE, nonfinite/boolean/non-numeric gets INVALID_VALUE and null. EXTERNAL_CONTEXT_LOAD_FAILED is visible in JSON, Markdown and HTML.

The immutable report also preserves the exact normalized auxiliary input as auxiliary_snapshot.json and hashes it in run_manifest.json, including invalid inputs for diagnosis. The assessed auxiliary_breadth.json remains separate. Parser failures retain raw download paths/hashes in collection_attempts; bytes remain outside source releases.

## v0.1.3 VIX 실제 거래일 결측 보완 — 2026-10-20

Cboe VIX 원본 CSV의 NYSE 세션 누락과 NYSE 비거래일 원자료 행은 별개의 문제다. 모든 원문 관측을 raw Cboe 입력에 그대로 보존하고, 정상 XNYS 거래일 결측만 `missing_xnys_dates`로 식별한다. SEC 역사 기록이 1999-12-31을 실제 조기 폐장 거래일로 확인하며, FRED `VIXCLS`는 같은 날짜의 **24.64**를 게시한다. 재배포처 값은 실제 관측에 한정하고 그 자체를 독립 검증이라고 표현하지 않는다.

수집기가 새로운 Cboe 데이터를 성공적으로 받아온 경우에만 FRED VIXCLS와 교차 대조한다. 완결된 세션 중 내부 결측일만 요청하며, 모든 결측일의 유효한 `VIXCLS` 숫자값(>0, finite)이 실제 확인돼야 한 번에 복구한다. 다운로드/달력/파싱 실패, 점(`.`)/빈칸/비숫자/0/음수, 날짜 중복 또는 누락, 20일 초과 갭은 보완을 중지한다. 원래 Cboe 관측값을 FRED 수치로 덮어쓰지 않는다.

`data/normalized/vix_recovery.json`은 복구 이벤트와 FRED 원문 해시를 기록하고 같은 실행 보고서 `vix_recovery.json`으로 복사한다. `metadata.json.vix.supplemental_observations`은 행별 FRED 재배포 출처, 수집시각, 원문 SHA256을 보존하고, `observations.csv`는 정확히 해당 날짜에만 FRED 출처를 표시한다. 완전 복구 시 VIX 단일 데이터셋의 `PASSED_RESEARCH`가 가능하지만, `SAFE_TO_ACT=False`와 독립 WSJ/NDR A/C 검증 보류는 유지한다.
