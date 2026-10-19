# MBSS v0.1.0 design

Authoritative brief: user's 2026-10-19 development request. Purpose: independent replication, not promotion of perfect historical hit rates. Existing engines are outside this repository. No order routing, allocation recommendation, or strategy modification.

## Approach and alternatives

Selected: a local Python research engine with immutable raw downloads, explicit provenance sidecars, per-dataset historical and live gates, and a CSV import contract for breadth. Automatic price/VIX downloads are attempted without keys. A missing comparable NYSE breadth source blocks A/C and breadth combinations. Alternative vendor integration would improve coverage but requires paid credentials; reconstructing breadth from surviving stocks would change the research question and is rejected.

## Interfaces

Normalized daily files: `spx.csv`, `spy.csv`, `qqq.csv` with date, open, high, low, close, adj_close, dividend; `vix.csv` with date, close; `breadth.csv` with date, advances, declines. A `metadata.json` holds each dataset's source, retrieval_timestamp, definition, adjustment_method, redistribution permission, review_status, and breadth universe evidence. Every observation is exported with original_value and adjusted_value; unavailable observations are never interpolated. Data are reindexed to XNYS sessions before indicator computation. Missing calendar dependency or data prevents validation. Historical validity is separate from current freshness. Third-party review is an auditable attestation, not automatic certification.

## Definitions

A: A/(A+D), EMA alpha=2/11; default SMA10 seed, 100 consecutive-session warmup; strict `<0.4 -> >0.615`, distance 1..10 sessions, consume setup on first confirmation. Original book page unavailable: exact original remains UNVERIFIED. Also export inclusive boundaries and 9-session distance sensitivities without choosing a best fit.
B: unadjusted index close daily returns >=0.015 for three consecutive sessions; only third day in a run. C: ratio >0.70 on >=6 of 10 complete sessions; first false-to-true transition, 10-session refractory interval. Missing input resets state. D: Tuesday after first Monday in November of midterm years, calendar rule; exclude future dates; first session after election open. Primary default start 2000, optionally 1974 for D and longer history for claims.

Combos: all required constituent events must have occurred in the trailing inclusive 5/10-session distance window; confirmation is last constituent's known date. Require a fresh constituent event; deduplicate sustained overlap and suppress for 10 sessions. Election combinations use the known six calendar months after an already completed election, without consulting outcomes.

## Backtest

Signal at close, next session open, exit at first session on/after entry + 1/3/6/12 calendar months. Never shorten immature horizons. Index price return and ETF split/dividend-adjusted proxy total return are separate; ETF proxies are not S&P index total return. Every benchmark shares actual entry and exit sessions. Missing benchmark produces null, not zero. Costs charged at both ends. Daily close drawdown includes entry open as initial capital, max high/low excursion uses daily extrema; cannot order intraday extrema. Random-entry comparison samples only horizon-complete, data-complete eligible sessions with fixed seed; distribution is unconditional and overlapping. Outcome bootstrap resamples connected overlapping holding-period clusters. Small samples, overlapping returns, retrospective revisions, non-PIT universe history, multiple comparisons and statistical selection are disclosed. No inferential claim from synthetic tests.

Strategy comparison: fully invested SPY on each eligible next open, flat cash earns 0%, no leverage, no additional entries while a position is open, fixed 6/12 month exits, daily adjusted equity. Same-window SPY buy-and-hold includes identical transaction costs. Report exposure, missed market returns, CAGR, daily volatility, Sharpe (rf=0) and drawdown. Truncated open trades are marked to market, not counted as completed events.

## Daily and safety

Each signal has independent DATA_HOLD / NO_SIGNAL / WATCH / CONFIRMED / HISTORICAL_SIGNAL / EXPIRED state. Latest evaluated session is the last completed NYSE close as of UTC time. VIX level and 5-session jump, SPX SMA200, drawdown, breadth support and post-signal reversal are descriptive risk flags. `SAFE_TO_ACT=False` always in v0.1.0: research validation and allocation budget approval are outstanding. Confidence describes evidence completeness only, never predicted probability. D is seasonal context, not a trading command.

## Reports and reproducibility

Required seven output files plus normalized observations, claim audit, summary, strategies, regime summaries and charts. Reports visibly separate actual observations from hypothetical trades. Missing plots are explicit DATA_HOLD panels, not invented curves. SHA256 inputs/raw/outputs, as-of cutoff, package versions, git commit, seed, configuration, definitions and download attempts are in the manifest. HTML is escaped and standalone. Atomic run directory, `latest` output uses only the same run.

## Limits to completion

An implemented adapter is not an acquired dataset. Unit tests demonstrate code behavior, not historical claims. A 2000 start cannot reproduce WWII-era 19/10/8 event counts or 1974–2022 13 elections. Report partial periods honestly. Repository creation/releases require a callable remote capability; a local git repository and archive do not count as published.
