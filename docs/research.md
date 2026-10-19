# Source research and unresolved replication — 2026-10-19

## Primary / first-party sources inspected

| Source | Finding | Remaining gap |
|---|---|---|
| [Ryan Detrick / Carson, 2025-04-25](https://www.carsongroup.com/insights/blog/houston-we-have-a-zweig-breadth-thrust-and-four-more-bullish-developments/) | Describes 19 mature post-WWII ZBT cases, 10 prior strong-rally cases, and eight repeated-expansion cases. Includes charts/tables as images. | NDR underlying breadth archive and exact counting/entry conventions not acquired. Event dates in the original Carson table images have now been transcribed and partially reconciled; see the follow-up below. The text references already mature observations; new April 2025 signals are not mature at publication. |
| [Schwab, 2026-08-18](https://www.schwab.com/learn/story/what-2026-midterms-could-mean-markets) | 1974–2022, 13 positive six-month periods, average 12.4%; explicitly price return only using Yahoo Finance, calculation as of 2026-08-14. | Exact starting close/open and anniversary rolling convention not fully specified. Next-open implementation is an independent convention. |
| [Tom McClellan, 2015-10-09](https://www.mcoscillator.com/learning_center/weekly_chart/zweig_breadth_thrust_signal/) | Analyst's own calculation describes EMA10 of A/(A+D), strict lower/upper boundaries and <=10-session distance. Earlier-history discussion includes unsuccessful episodes. | This is first-party analysis of a named analyst, not the Zweig book itself; different sample era and qualitative classification cannot directly refute Carson's one-year statistic. |
| [Martin Zweig: Winning on Wall Street](https://cmtassociation.org/technically_speaking/technically-speaking-may-2012/) | CMT's retrospective identifies the book and strict 40/61.5/10-day condition. | Actual source-book page not obtained. Original exact formula, EMA initialization and inclusive day-count convention remain UNVERIFIED. |
| [NYSE daily statistics introduction](https://www.nyse.com/data-insights/nyse-introduces-daily-us-equity-market-statistics-report) | Official market-quality and volume statistics for selected stocks/ETFs. | Not an identified free 2000-present NYSE advance/decline count archive. Does not establish a historical breadth universe. |
| [NYSE hours / calendar](https://www.nyse.com/trade/hours-calendars) | Current holidays and early-close schedule. | Long historical schedule supplied by the third-party exchange-calendars package, with version recorded; historical special closures require verification. |
| [McClellan breadth page](https://www.mcoscillator.com/market_breadth_data/) and [common-only discussion](https://www.mcoscillator.com/learning_center/weekly_chart/common_only_mcclellan_oscillator/) | Recent breadth is public; full historical archive is offered for purchase; common-only and all-issue data differ. | Paid archive is not a default dependency. Free comparable long history not secured. |
| [Yahoo adjusted close](https://in.help.yahoo.com/kb/adjusted-close-sln28256.html) | Close is adjusted for splits and distributions. | API access and retrospective data revisions remain source-dependent; adjusted OHLC is a proxy, not official SPX total return. |
| [Cboe VIX history](https://www.cboe.com/tradable-products/vix/vix-historical-data) | Official historical VIX daily-price download route. | Downloaded successfully on retry; historical session-alignment issues are documented below. |
| [2 USC 7](https://uscode.house.gov/us/usc/119-120/t2/s7/) and [FEC dates](https://www.fec.gov/introduction-campaign-finance/election-results-and-voting-information/) | Federal general election calendar rule; 2026 election is November 3. | Calendar event only; MBSS neither predicts nor waits for certified electoral outcomes. 2026 is excluded from completed historical samples as of this run. |

## Replication policy

Every target remains **UNVERIFIED** until underlying input definition, full date list, sample scope, entry/exit dates and return basis are reconciled. Exact aggregate count or mean coincidence is insufficient. A smaller 2000+ sample is reported as partial evidence, never a full reproduction. The implementation includes strict/inclusive boundaries, 9/10-session distance and initialization sensitivity; these are diagnostics, not parameters optimized to reproduce a desired count.

Publication-source performance is normally measured from a signal close. The requested executable assumption is next-session open and calendar months from actual entry. These differ through overnight gaps, leap dates, weekends and holidays. SPY/QQQ distributions add another difference. Original book and NDR data access limitations are reported rather than resolved by a guessed ticker-based reconstruction.

## Runtime acquisition evidence

Initial Yahoo/Cboe probes timed out and the default package source could not install the calendar. Retrying the actual adapters succeeded: Yahoo SPX history from 1950, SPY from 1993, QQQ from 1999, and Cboe VIX from 1990 were downloaded and hashed. An explicit PyPI install supplied exchange-calendars 4.13.2. No keys or paid datasets were used. Unit fixtures remain synthetic and do not count as acquired historical data.

Price and XNYS sessions match with no internal gaps from 1970 onward. The 1950–1969 calendar/provider comparison contains 182 date discrepancies, including historical holidays. Earlier calendar definitions have not been reconciled; the engine explicitly floors validated calendar coverage at 1970. It does not fill or compress those observations. The initial research scope remains 2000+; the longer 1970 run is a separate replication supplement.

Cboe VIX was acquired but fails the strict full-history XNYS alignment gate: the long archive has four missing NYSE sessions and observations outside the NYSE session calendar. The 2000 run's one-year buffer includes one of these missing dates. These are unresolved calendar/definition issues, not an assertion that the exchange source is generally unreliable. VIX is excluded from validated event and live risk inputs; raw values and source flags are preserved in the audit snapshot. Comparable continuous breadth input remains unavailable. Overall DATA_HOLD and SAFE_TO_ACT=False remain appropriate.

## Numerical reconciliation obtained (not complete source verification)

| Claim | Independently detected mature source-scope cases | Diagnostic reference convention | Aggregate result | Primary executable assumption |
|---|---:|---|---|---|
| B, 10/10, about 21.6% | 10, from 1970 through the mature pre-April-2025 sample | Signal close to 252 sessions later | 10/10, +21.6338% | Next open to 12 calendar months: +21.7791% |
| D, 13/13, about 12.4% | 13, elections 1974–2022 | Election-day close to six calendar months, roll forward | 13/13, +12.4115% | First following session open to six calendar months: +11.9744% |

The B signal-close calendar-year alternative is +21.9659%; D's 126-session alternative is +11.9389%. Both standard horizon conventions are exported for all signals. They are definition diagnostics, not an optimized replacement for the user-specified entry rule. A same-close entry cannot be executed using a signal known only after that close; it never enters strategy P&L. Original date-list and exact convention reconciliation remain UNVERIFIED even when aggregate counts and rounded means match.

2000–2026-10-16 executable B sample: five 12-month cases, 5/5 positive, mean +24.2960%; six-month sample 4/5 positive, mean +14.0230%. D has six post-2000 elections, 6/6 positive over six months, mean +6.7506%. SPY 2000-window adjusted buy-and-hold terminal return is +723.6660%; B 12-month waiting strategy is +217.9130%, with 18.789% market exposure, versus 100% for buy-and-hold. These are hypothetical results at zero transaction costs and zero cash interest. They do not establish an investable advantage or future perfect success.

The requested GitHub repository lookup returned 404 through the current connection. This can mean absent or inaccessible; no assertion of public nonexistence is made. The available GitHub connector has no repository-creation or release-creation operation. Local code packaging is complete; remote publication and Actions execution remain outstanding.

## Original table follow-up

[2026-10-19 source-image/date reconciliation](publication-reconciliation-2026-10-19.md): A matches 11/11 dates in the 1970–2020 overlap; C matches all five reference dates but detects three additional nearby episodes; B matches all 11 printed dates, including the new 2025 case. This is partial date reconciliation, not full input/return verification. Source-internal A date and B mean inconsistencies are preserved.
