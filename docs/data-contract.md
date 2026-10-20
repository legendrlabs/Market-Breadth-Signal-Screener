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
