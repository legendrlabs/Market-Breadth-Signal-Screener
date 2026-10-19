import unittest
import numpy as np
import pandas as pd
from mbss.indicators.core import breadth_ratio, ema, strong_streak, expansion_count
from mbss.signals.core import zbt_events, rally_events, expansion_events, combine_events, election_events
from mbss.models import Event


class SignalTests(unittest.TestCase):
    def test_ratio_denominator_and_missing(self):
        a = pd.Series([3, 0, -1, 3, np.nan]); d = pd.Series([1, 0, 2, 0, 1])
        r = breadth_ratio(a, d)
        self.assertEqual(r.iloc[0], .75)
        self.assertTrue(r.iloc[[1, 2, 4]].isna().all())
        self.assertEqual(r.iloc[3], 1)

    def test_ema_sma_seed_and_reset(self):
        x = pd.Series([.1, .2, .3, .4, np.nan, .5, .5, .5])
        y = ema(x, span=3, warmup=3)
        self.assertAlmostEqual(y.iloc[2], .2)
        self.assertAlmostEqual(y.iloc[3], .3)
        self.assertTrue(y.iloc[4:7].isna().all())
        self.assertAlmostEqual(y.iloc[7], .5)

    def test_zbt_strict_and_inclusive_boundary(self):
        s = pd.Series([.4, .5, .615], index=pd.bdate_range('2020-01-01', periods=3))
        self.assertEqual(zbt_events(s), [])
        self.assertEqual(len(zbt_events(s, inclusive=True)), 1)

    def test_zbt_tenth_session_but_not_eleventh(self):
        idx = pd.bdate_range('2020-01-01', periods=12)
        yes = pd.Series([.39] + [.5]*9 + [.62, .7], index=idx)
        self.assertEqual([e.date for e in zbt_events(yes)], [idx[10]])
        no = pd.Series([.39] + [.5]*10 + [.62], index=idx)
        self.assertEqual(zbt_events(no), [])

    def test_zbt_missing_resets_and_one_confirmation(self):
        idx = pd.bdate_range('2020-01-01', periods=5)
        self.assertEqual(zbt_events(pd.Series([.39, np.nan, .5, .62, .7], index=idx)), [])
        self.assertEqual(len(zbt_events(pd.Series([.39, .5, .62, .7, .8], index=idx))), 1)

    def test_three_distinct_daily_rallies(self):
        idx = pd.bdate_range('2020-01-01', periods=6)
        c = pd.Series(100*1.015**np.arange(6), index=idx)
        self.assertEqual([e.date for e in rally_events(c)], [idx[3]])
        self.assertEqual(strong_streak(c).iloc[-1], 5)
        self.assertEqual(rally_events(pd.Series([100, 100.5, 101, 101.5], index=idx[:4])), [])

    def test_missing_price_does_not_bridge_returns(self):
        x = pd.Series([100, 102, np.nan, 104, 106, 108], index=pd.bdate_range('2020-01-01', periods=6))
        self.assertEqual(rally_events(x), [])

    def test_six_in_ten_not_six_consecutive(self):
        idx = pd.bdate_range('2020-01-01', periods=12)
        x = pd.Series([.8,.5,.8,.5,.8,.5,.8,.8,.5,.8,.8,.8], index=idx)
        self.assertEqual(expansion_count(x).iloc[9], 6)
        self.assertEqual([e.date for e in expansion_events(x)], [idx[9]])
        x.iloc[0] = .7
        self.assertEqual(expansion_count(x).iloc[9], 5)

    def test_combinations_are_causal_and_windowed(self):
        idx = pd.bdate_range('2020-01-01', periods=20)
        events = [Event('A',idx[0]), Event('B',idx[5]), Event('C',idx[6])]
        result = combine_events(events, idx, ('A','B'), 5)
        self.assertEqual([e.date for e in result], [idx[5]])
        self.assertEqual(combine_events(events, idx, ('A','C'), 5), [])
        self.assertEqual(combine_events(events, idx, ('A','B'), 5), combine_events(events[:2],idx[:6],('A','B'),5))

    def test_elections_not_future_and_entry_after_holiday(self):
        # Trading calendar deliberately omits election day and following holiday.
        idx = pd.to_datetime(['2022-11-07','2022-11-10','2026-11-04'])
        events = election_events(idx, pd.Timestamp('2026-10-19'), first_year=2022)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].date, pd.Timestamp('2022-11-08'))

    def test_prefix_invariance(self):
        idx = pd.bdate_range('2000-01-01',periods=400)
        r = pd.Series(np.random.default_rng(2).uniform(.2,.9,400),index=idx)
        for n in (120,200,300):
            full = zbt_events(ema(r)) + expansion_events(r)
            partial = zbt_events(ema(r.iloc[:n])) + expansion_events(r.iloc[:n])
            self.assertEqual(sorted((e.signal,e.date) for e in full if e.date<=idx[n-1]), sorted((e.signal,e.date) for e in partial))


if __name__ == '__main__': unittest.main()
