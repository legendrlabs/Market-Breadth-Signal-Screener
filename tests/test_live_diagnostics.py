import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import io
import pandas as pd
from mbss.models import Event
from mbss.risk.core import daily_assessment
from mbss.collectors import quality, sources


class LiveDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.idx=pd.bdate_range('2024-01-02',periods=140)
        self.price=pd.DataFrame({'close':100.},index=self.idx)
        self.q={k:{'history_valid':True,'fresh':True,'rows':140,'reason_codes':[]} for k in ['spx','breadth','vix']}

    def assess(self,events):
        return daily_assessment(events,{'spx':self.price},self.q,self.idx)

    def test_expired_history_is_not_a_current_signal(self):
        r=self.assess([Event('B',self.idx[0])])['signals']['B']
        self.assertEqual(r['SIGNAL_STATUS'],'NO_SIGNAL')
        self.assertIsNone(r['SIGNAL_DATE'])
        self.assertEqual(r['LAST_SIGNAL_STATUS'],'EXPIRED')
        self.assertEqual(r['LAST_SIGNAL_DATE'],str(self.idx[0].date()))

    def test_no_prior_event_is_distinct_from_expired(self):
        r=self.assess([])['signals']['B']
        self.assertEqual(r['SIGNAL_STATUS'],'NO_SIGNAL')
        self.assertIsNone(r['LAST_SIGNAL_STATUS'])

    def test_observation_window_boundary_keeps_last_lifecycle(self):
        r=self.assess([Event('B',self.idx[-21])])['signals']['B']
        self.assertEqual(r['SIGNAL_STATUS'],'HISTORICAL_SIGNAL')
        r=self.assess([Event('B',self.idx[-22])])['signals']['B']
        self.assertEqual(r['SIGNAL_STATUS'],'NO_SIGNAL')
        self.assertEqual(r['LAST_SIGNAL_STATUS'],'EXPIRED')

    def test_external_future_reference_is_flagged_and_inert(self):
        from mbss.collectors.context import external_context
        with TemporaryDirectory() as d:
            row={'metric':'advancing_share','value':.99,'universe':'NYSE','session_type':'INTRADAY',
                 'observed_at':'2026-10-20T00:00:00Z','retrieval_timestamp':'2026-10-19T14:00:00Z',
                 'source':'https://example.org','eligible_for_signal':True}
            Path(d,'external_context.json').write_text(json.dumps([row]))
            r=external_context(d,pd.Timestamp('2026-10-19T15:00:00Z'))['observations'][0]
            self.assertFalse(r['eligible_for_signal'])
            self.assertIn('FUTURE_OBSERVED_AT',r['flags'])

    def test_midterm_inactive_and_active_window_are_explicit(self):
        old=Event('D',pd.Timestamp('2022-11-08'))
        r=self.assess([old])['signals']['D']
        self.assertEqual(r['SIGNAL_STATUS'],'NO_SIGNAL')
        self.assertEqual(r['SEASONALITY_STATUS'],'INACTIVE')
        r=self.assess([Event('D',self.idx[-2])])['signals']['D']
        self.assertEqual(r['SEASONALITY_STATUS'],'ACTIVE')
        self.assertEqual(r['SIGNAL_STATUS'],'HISTORICAL_SIGNAL')

    def test_hold_reasons_distinguish_missing_failed_and_short(self):
        q=quality.validate_dataset('breadth',pd.DataFrame(),{},self.idx,self.idx[-1])
        self.assertIn('SOURCE_UNAVAILABLE',q['reason_codes'])
        p=pd.DataFrame({'advances':10,'declines':20},index=self.idx)
        q=quality.validate_dataset('breadth',p,{},self.idx,self.idx[-1])
        self.assertIn('VALIDATION_FAILED',q['reason_codes'])
        self.q['spx']['rows']=2
        r=self.assess([])['signals']['B']
        self.assertEqual(r['SIGNAL_STATUS'],'DATA_HOLD')
        self.assertIn('INSUFFICIENT_HISTORY',r['DATA_HOLD_REASONS'])

    def test_recent_breadth_diagnostic_resets_on_gap_and_never_approves(self):
        p=pd.DataFrame({'advances':80,'declines':20},index=self.idx)
        fn=getattr(quality,'breadth_diagnostics',None)
        self.assertTrue(callable(fn),'recent breadth diagnostic missing')
        d=fn(p,self.idx,self.idx[-1])
        self.assertTrue(d['recent_10_complete'])
        self.assertEqual(d['expansion_days_10'],10)
        self.assertAlmostEqual(d['zbt_ema10'],.8)
        self.assertFalse(d['eligible_for_signal'])
        d=fn(p.drop(self.idx[-5]),self.idx,self.idx[-1])
        self.assertFalse(d['recent_10_complete'])
        self.assertIsNone(d['expansion_days_10'])
        self.assertIsNone(d['zbt_ema10'])

    def test_mcclellan_header_contract_and_blank_future_rows(self):
        fn=getattr(sources,'parse_mcclellan_rows',None)
        self.assertTrue(callable(fn),'free XLS parser missing')
        rows=[['title'],['DATE','NYSE','NYSE'],['','ADV.','DEC.'],
              [46112,200,100],[46113,'','']]
        p=fn(rows)
        self.assertEqual(len(p),1)
        self.assertEqual(p.iloc[0]['advances'],200)
        with self.assertRaises(ValueError):fn([['DATE','NASDAQ','NYSE'],['','ADV.','DEC.'],[46112,200,100]])

    def test_xls_note_row_is_not_an_observation_but_partial_numeric_row_is(self):
        rows=[['DATE','NYSE','NYSE'],['','ADV.','DEC.'],[46112,200,100],
              [46113,'','Last row of autofill formulas'],[46114,100,'']]
        p=sources.parse_mcclellan_rows(rows)
        self.assertEqual(len(p),2)
        self.assertEqual(p.attrs['non_observation_note_rows'],1)
        self.assertEqual(p.iloc[-1]['advances'],100)

    def test_collection_preserves_imported_breadth_and_stages_candidate(self):
        with TemporaryDirectory() as d:
            p=Path(d)/'input';p.mkdir()
            original=b'date,advances,declines\n2000-01-03,100,200\n'
            (p/'breadth.csv').write_bytes(original)
            meta={'breadth':{'source':'https://example.org/reviewed','review_status':'reviewed'}}
            (p/'metadata.json').write_text(json.dumps(meta))
            frame=pd.DataFrame({'advances':[200],'declines':[100]},index=pd.DatetimeIndex(['2026-10-16'],name='date'))
            def fetch(request,timeout):
                if request.full_url.endswith('OSC-DATA.xls'):return io.BytesIO(b'fixture')
                raise OSError('test source unavailable')
            with patch.object(sources,'urlopen',side_effect=fetch),patch.object(sources,'parse_mcclellan',return_value=frame):
                attempts=sources.collect(p)
            self.assertEqual((p/'breadth.csv').read_bytes(),original)
            self.assertEqual(json.loads((p/'metadata.json').read_text())['breadth'],meta['breadth'])
            self.assertTrue((p/'breadth_candidate.csv').is_file())
            self.assertEqual(next(a for a in attempts if a['dataset']=='breadth')['application_status'],'CANDIDATE_ONLY_EXISTING_INPUT_PRESERVED')

    def test_external_intraday_reference_never_enters_signal_metrics(self):
        with TemporaryDirectory() as d:
            from mbss.pipeline import run
            p=Path(d);(p/'in').mkdir()
            (p/'in/external_context.json').write_text(json.dumps([{'metric':'advancing_share',
                'value':.32,'universe':'S&P 500','session_type':'INTRADAY',
                'observed_at':None,'source':'https://example.org/article',
                'retrieval_timestamp':'2026-10-19T14:00:00Z'}]))
            r=run(p/'in',p/'out',as_of='2026-10-19T15:00:00Z',start='2000-01-01')
            x=json.loads((p/'out/external_context.json').read_text())
            self.assertFalse(x['observations'][0]['eligible_for_signal'])
            self.assertIn('OBSERVATION_TIME_UNKNOWN',x['observations'][0]['flags'])
            self.assertNotIn('advancing_share',r['assessment']['metrics'])
            self.assertIn('S&P 500',(p/'out/latest.md').read_text())


if __name__=='__main__':unittest.main()
