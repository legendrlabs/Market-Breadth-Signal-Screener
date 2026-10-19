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
