# v0.1.0 verification and review ledger

Plan: `docs/superpowers/plans/2026-10-19-mbss.md`. Requirements and scope come from the user's supplied design. Work executed inline in an isolated new git repository on `develop`.

## Completed implementation

Data acquisition adapters for Yahoo OHLC/adjusted close/dividends and official Cboe VIX; CSV breadth adapter; provenance/universe/reference-comparability gates; NYSE completed-session calendar; causal A/B/C/D and 5/10-session/election combinations; next-open event studies; price vs total-return proxies; net costs; forward excursions/drawdowns; overlapping-cluster bootstrap; Wilson diagnostics; seeded random-entry baseline; SPY cash/waiting portfolios; six-state live assessment with SAFE_TO_ACT=False; seven required report files, seven charts, sensitivity, source hashes and audit exports; CI/daily workflow; Korean manual.

## Real execution

Main window: 2000-01-01 through completed NYSE 2026-10-16, evaluated as of the request time 2026-10-19T08:57:22Z. Supplement: 1970 onward with the same cutoff, including all 13 elections from 1974–2022. Download retrievals occurred later the same UTC day; this is retrospective research, not a point-in-time historical feed.

SPX/SPY/QQQ passed structural/session validation in their covered windows. Cboe VIX was downloaded but full-history XNYS date alignment failed, so validated event VIX values and VIX risk inputs remain unavailable. Breadth source/universe comparison is unresolved; A/C and breadth combinations have no verified real sample.

B's 10 mature pre-publication cases and D's 13 election cases match the published rounded aggregates under explicitly labeled same-close reference conventions. Full source replication remains UNVERIFIED. Primary next-open returns, calendar-month exits and after-close confirmation are unchanged. See research.md and actual-run JSON/CSV for values and differences.

## Test evidence

`PYTHONPATH=src python -m unittest discover -s tests -v`: 47 tests pass after installing exchange-calendars 4.13.2. No skipped tests in the final environment. Tests cover signal numerical boundaries and prefix invariance; missing inputs; invalid universe/metadata; holiday and early-close handling; next-open and actual-entry horizons; immature outcomes; costs/dividends; drawdowns; old-event remapping; pre-start election context; publication-time maturity; cluster/random reproducibility; HTML escaping; immutable report output and source-comparison-only returns.

## Independent code review and resolved findings

A separate reviewer inspected the code and ran reproductions. Important findings were fixed with regressions:

1. Old signals were incorrectly mapped to a delayed comparison start: historical entries are no longer moved forward.
2. Pre-start constituents/elections were discarded before combinations: buffered context is retained and only confirmations are filtered.
3. Publication claim comparisons included subsequently matured outcomes: publication-time maturity is now required.
4. Null universe/nonnumeric audit values crashed a run: they now produce fail-closed reports preserving original invalid values.

The configuration-description finding was resolved by fixing primary signal definitions and rejecting silent changes. Sensitivities remain separately labeled. No deferred code-review findings are knowingly left open. The reviewer did not repeat the final suite; the implementer ran all regressions and the full final suite.

## Explicit design rulings and remaining limits

- Strict ZBT boundaries, SMA10 seed, 100-session warmup and distance <=10 are a documented research convention until original-book verification; inclusive/9-session/first-seed variants are diagnostics. Cost of an incorrect original interpretation: different A dates; A remains DATA_HOLD with no capital action.
- Validated calendar coverage floors at 1970 after earlier holiday discrepancies. Cost: earlier possible events cannot be counted; no claim of an exhaustive 1950/WWII sample.
- VIX date mismatches are not silently repaired or filled. Cost: current and event VIX analysis remains unavailable despite acquiring observations.
- No automatic allocation or orders. Actual capital percentage requires a subsequent risk-budget decision.
- Full breadth history, composite empirical results, exact original event-list/return reconciliation, FX and official SPX total return remain incomplete.
- Earlier GitHub lookup was 404 and browser creation required sign-in. On 2026-10-19 the user supplied an empty repository and write access was verified. Current evidence is maintained in deployment.md.


## GitHub registration continuation

Existing develop checkout and 737467e research reconciliation were resumed; the approved design and completed signal/backtest work were not repeated. The initial import failed because this session had no installed package; reinstalling the declared dependencies restored all 47 engine tests with zero skips.

Six Python release tests failed before the metadata generator existed; Node publication tests failed before the publisher existed. The implemented source provenance/prerelease protection passes Python 53/53 and Node 6/6 tests. Empty-input CLI still reports DATA_HOLD and SAFE_TO_ACT=False.

Ruling: publish only a research prerelease, keeping provider data and reports outside the source tree, as the original deployment plan requires. Incorrect interpretation would overstate trading readiness; manifest and release text retain UNVERIFIED and the hold status. Initial main registration triggers actual collection/report generation so remote execution can be observed.


Final publication review: no Critical/Important findings; reviewer independently ran Python 53/53 and Node 6/6, zero skips. Final: minor (deferred): reject a previously published release externally converted from prerelease to stable. The first-publication path always sets prerelease=true; this affects external mutation/retry hardening only.

Actual main execution 39268895856 and v0.1.0 prerelease succeeded. Artifact inspection found the run manifest still used a development-era NOT_PUBLISHED constant despite executing on GitHub. Root cause: publication metadata never consumed the already recorded checkout commit or GitHub run context. Four provenance regressions failed before implementing matching-checkout context; the existing empty-run test also rejects the stale constant. v0.1.1 records only verified matching execution context and uses NOT_CHECKED for unqueried release existence. This does not change signal detection, statistics or trade permission.


## v0.1.2 feedback and data continuation

Ruling: distinguish the absence of a current active signal from the lifecycle of an actual past signal. EXPIRED was valid for B's 2025 and D's 2022 event; current fields now use NO_SIGNAL and separate LAST_SIGNAL_STATUS. Cost if wrong: consumers may misread an inactive history as a fresh signal. D has separate seasonality context. No detection threshold or outcome formula changed.

Ruling: connect the publicly available recent McClellan XLS while preserving universe/NDR DATA_HOLD. Add only explicitly unverified recent-window diagnostics; do not splice incompatible historical archives. Cost if wrong: a recent numeric ratio could be mistaken for a validated ZBT, so it is excluded from all signal/backtest inputs and labeled REFERENCE_ONLY.

Tests first: seven live-diagnostic regressions failed (four failures, three errors) before implementation. Current/expired state, no-prior-event, six-month seasonality, hold causes, gap resets, XLS header/blank future rows and isolated external context now pass. Two extra boundary/future-reference cases cover twenty-session expiry and future external input. Full Python 66/66 and Node 6/6 pass locally.

Live acquisition obtained NYSE actual issue counts; the first attempt also exposed a genuine SPX source failure and correctly kept affected signals on SOURCE_UNAVAILABLE rather than implying NO_SIGNAL. Recent NYSE diagnostics through 2026-10-16: 139 consecutive observations, ratio 0.4233737596, EMA10 0.4927491823, one >70% day in the last ten. These are not approved signal inputs.


Final v0.1.2 review: no Critical findings, two Important findings reproduced. Final: fixed existing imported/reviewed breadth overwrite — test_collection_preserves_imported_breadth_and_stages_candidate RED→GREEN. Final: fixed XLS footer note counted as an observation — test_xls_note_row_is_not_an_observation_but_partial_numeric_row_is RED→GREEN. Full suite 68/68 Python and 6/6 Node green. Only collector-managed unreviewed files at the same source can be refreshed in place; other existing inputs are preserved and new data staged separately. No incompatible historical splicing.

Final: minor (deferred): malformed external-context JSON is diagnosed in JSON but the rendered empty-reference wording omits that parsing error. Final: minor (deferred): an external record missing value does not receive an explicit missing-value flag. Both remain permanently excluded from all signal calculations; improve these auxiliary input messages later. No second review requested after the single regression fix pass.
