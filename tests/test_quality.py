import unittest
import pandas as pd
from mbss.collectors.quality import validate_dataset


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

    def test_ohlc_inconsistent_invalid(self):
        self.p.iloc[0,self.p.columns.get_loc('high')]=90
        self.assertFalse(validate_dataset('spx',self.p,self.meta,self.idx,self.idx[-1])['history_valid'])

    def test_infinite_prices_invalid(self):
        self.p.iloc[0,self.p.columns.get_loc('close')]=float('inf')
        self.assertFalse(validate_dataset('spx',self.p,self.meta,self.idx,self.idx[-1])['history_valid'])

if __name__=='__main__': unittest.main()
