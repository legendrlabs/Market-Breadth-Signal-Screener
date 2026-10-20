import unittest
import pandas as pd
from mbss.collectors.quality import validate_dataset, breadth_diagnostics


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.idx=pd.bdate_range('2020-01-01',periods=10)
        self.p=pd.DataFrame({'open':100.,'high':101.,'low':99.,'close':100.,'adj_close':90.,'dividend':0.},index=self.idx)
        self.meta={'source':'https://example.org/data','retrieval_timestamp':'2020-02-01T00:00:00Z','definition':'daily index','adjustment_method':'index price only','review_status':'documented'}

    def test_price_valid_and_current_freshness_separate(self):
        q=validate_dataset('spx',self.p,self.meta,self.idx,pd.Timestamp('2020-03-01'))
        self.assertTrue(q['history_valid']);self.assertFalse(q['fresh'])

    def test_missing_session_not_compressed(self):
        q=validate_dataset('spx',self.p.drop(self.idx[4]),self.meta,self.idx,self.idx[-1])
        self.assertFalse(q['history_valid']);self.assertEqual(q['missing_count'],1)

    def test_duplicates_invalid(self):
        q=validate_dataset('spx',pd.concat([self.p,self.p.iloc[:1]]),self.meta,self.idx,self.idx[-1])
        self.assertFalse(q['history_valid'])

    def test_unknown_breadth_universe_fails_closed(self):
        b=pd.DataFrame({'advances':100,'declines':200},index=self.idx)
        q=validate_dataset('breadth',b,self.meta,self.idx,self.idx[-1])
        self.assertFalse(q['history_valid']);self.assertIn('UNIVERSE_UNVERIFIED',q['flags'])

    def test_null_universe_fails_closed(self):
        b=pd.DataFrame({'advances':100,'declines':200},index=self.idx)
        q=validate_dataset('breadth',b,{**self.meta,'universe':None},self.idx,self.idx[-1])
        self.assertFalse(q['history_valid'])

    def test_breadth_inclusion_flags_must_be_boolean_and_point_in_time(self):
        b=pd.DataFrame({'advances':100,'declines':200},index=self.idx)
        u={'exchange':'NYSE','etf_included':'unknown','preferred_included':False,'closed_end_fund_included':True,'point_in_time_membership':False}
        q=validate_dataset('breadth',b,{**self.meta,'review_status':'reviewed','universe':u,'universe_evidence':'https://example.org/universe'},self.idx,self.idx[-1])
        self.assertFalse(q['history_valid'])

    def test_reference_comparability_required_for_breadth(self):
        b=pd.DataFrame({'advances':100,'declines':200},index=self.idx)
        u={'exchange':'NYSE','etf_included':True,'preferred_included':True,'closed_end_fund_included':True,'point_in_time_membership':True}
        m={**self.meta,'review_status':'reviewed','universe':u,'universe_evidence':'https://example.org/universe'}
        self.assertFalse(validate_dataset('breadth',b,m,self.idx,self.idx[-1])['history_valid'])
        m['reference_comparability']={'status':'reviewed_comparable','evidence':'https://example.org/comparison'}
        self.assertTrue(validate_dataset('breadth',b,m,self.idx,self.idx[-1])['history_valid'])

    def test_provider_declared_composite_scope_never_approves_pit_or_ndr(self):
        b=pd.DataFrame({'advances':100,'declines':200},index=self.idx)
        meta={**self.meta,
              'universe':{'exchange':'NYSE','etf_included':None,'preferred_included':None,
                          'closed_end_fund_included':None,'point_in_time_membership':None},
              'provider_declared_scope':{
                  'dataset':'McClellan NYSE composite A-D issue counts',
                  'status':'PUBLISHER_STATEMENT_ONLY_NOT_PIT_CONSTITUENT_AUDIT',
                  'common_only_historical_break':'2005-02-09 only for Common Only'}}
        q=validate_dataset('breadth',b,meta,self.idx,self.idx[-1])
        self.assertFalse(q['history_valid'])
        self.assertEqual(q['validation_status'],'DATA_HOLD')
        self.assertIn('UNIVERSE_UNVERIFIED',q['flags'])
        self.assertIn('REFERENCE_COMPARABILITY_UNVERIFIED',q['flags'])
        self.assertEqual(q['provider_declared_scope']['dataset'],
                         'McClellan NYSE composite A-D issue counts')

    def test_ohlc_inconsistent_invalid(self):
        self.p.iloc[0,self.p.columns.get_loc('high')]=90
        self.assertFalse(validate_dataset('spx',self.p,self.meta,self.idx,self.idx[-1])['history_valid'])

    def test_infinite_prices_invalid(self):
        self.p.iloc[0,self.p.columns.get_loc('close')]=float('inf')
        self.assertFalse(validate_dataset('spx',self.p,self.meta,self.idx,self.idx[-1])['history_valid'])

    def test_vix_non_xnys_rows_are_audited_not_treated_as_missing_trades(self):
        observed=pd.DataFrame({'close':20.0},index=self.idx)
        weekend=pd.DataFrame({'close':-999.0},index=[pd.Timestamp('2020-01-04')])
        original=pd.concat([observed,weekend]).sort_index()
        q=validate_dataset('vix',original,self.meta,self.idx,self.idx[-1])
        self.assertTrue(q['history_valid'])
        self.assertEqual(q['excluded_non_xnys_session_count'],1)
        self.assertEqual(q['excluded_non_xnys_dates'],['2020-01-04'])
        self.assertEqual(q['missing_count'],0)
        self.assertIn(pd.Timestamp('2020-01-04'),original.index)

    def test_vix_real_xnys_gap_cannot_be_filled_by_non_session_row(self):
        observed=pd.DataFrame({'close':20.0},index=self.idx).drop(self.idx[4])
        weekend=pd.DataFrame({'close':20.0},index=[pd.Timestamp('2020-01-04')])
        q=validate_dataset('vix',pd.concat([observed,weekend]).sort_index(),
                           self.meta,self.idx,self.idx[-1])
        self.assertFalse(q['history_valid'])
        self.assertEqual(q['missing_count'],1)
        self.assertIn('MISSING_SESSIONS',q['flags'])
        self.assertEqual(q['excluded_non_xnys_session_count'],1)

    def test_recent_reference_observation_has_dates_counts_and_freshness(self):
        sessions=pd.bdate_range('2026-01-01',periods=140)
        p=pd.DataFrame({'advances':70,'declines':30},index=sessions)
        recent=breadth_diagnostics(p,sessions,sessions[-1])
        self.assertEqual(recent['observed_session'],str(sessions[-1].date()))
        self.assertEqual(recent['source_freshness'],'CURRENT')
        self.assertEqual((recent['advances'],recent['declines']),(70,30))
        self.assertTrue(recent['ema100_warmup_complete'])
        self.assertFalse(recent['eligible_for_signal'])
        stale=breadth_diagnostics(p.drop(sessions[-1]),sessions,sessions[-1])
        self.assertEqual(stale['source_freshness'],'STALE')
        self.assertEqual(stale['observed_session'],str(sessions[-2].date()))
        self.assertIsNone(stale['advances'])
        self.assertIsNone(stale['breadth_ratio'])
        self.assertEqual(stale['consecutive_valid_sessions'],0)
        self.assertFalse(stale['recent_10_complete'])
        self.assertFalse(stale['ema100_warmup_complete'])
        self.assertIsNone(stale['zbt_ema10'])


if __name__=='__main__': unittest.main()
