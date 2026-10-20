import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from mbss.pipeline import run
from mbss.risk.core import daily_assessment
from mbss.models import Event


class PipelineTests(unittest.TestCase):
    def test_empty_run_writes_required_artifacts_and_no_fake_performance(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);out=root/'out'
            result=run(root/'input',out,as_of='2026-10-19T08:57:00Z',start='2000-01-01')
            for name in ('latest.md','latest.html','signals.csv','backtest_results.csv','signal_events.json','data_quality.json','run_manifest.json'):
                self.assertTrue((out/name).is_file(),name)
            self.assertFalse(result['assessment']['SAFE_TO_ACT'])
            self.assertEqual(result['assessment']['SIGNAL_STATUS'],'DATA_HOLD')
            self.assertIn('UNVERIFIED',(out/'latest.md').read_text())
            self.assertTrue(pd.read_csv(out/'backtest_results.csv').empty)
            self.assertNotEqual(result['manifest']['publication']['github_repository'],'NOT_PUBLISHED')

    def test_synthetic_fixture_is_labeled_and_not_claim_validation(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);inp=root/'input';inp.mkdir();out=root/'out'
            idx=pd.bdate_range('2019-01-01',periods=360)
            close=100*np.cumprod(1+np.random.default_rng(4).normal(.001,.01,len(idx)))
            close[50:54]=close[49]*1.02**np.arange(1,5)
            meta={}
            for name in ('spx','spy','qqq'):
                p=pd.DataFrame({'date':idx,'open':close*.999,'high':close*1.01,'low':close*.99,'close':close,'adj_close':close*.8,'dividend':0})
                p.to_csv(inp/(name+'.csv'),index=False)
                meta[name]={'source':'https://example.org/synthetic','retrieval_timestamp':'2026-10-19T08:00:00Z','definition':'synthetic test','adjustment_method':'synthetic','review_status':'documented'}
            (inp/'metadata.json').write_text(json.dumps(meta))
            result=run(inp,out,as_of='2026-10-19T08:57:00Z',start='2019-01-01',sessions_override=idx,synthetic=True,bootstrap_draws=50)
            self.assertIn('SYNTHETIC',(out/'latest.html').read_text())
            self.assertTrue(all(c['status']=='UNVERIFIED' for c in result['claims']))
            self.assertGreater(len(pd.read_csv(out/'backtest_results.csv')),0)

    def test_confirmed_never_means_safe_to_act(self):
        idx=pd.bdate_range('2020-01-01',periods=250)
        p=pd.DataFrame({'close':np.arange(250)+100.},index=idx)
        q={k:{'history_valid':True,'fresh':True} for k in ('spx','spy','qqq','vix','breadth')}
        r=daily_assessment([Event('B',idx[-1])],{'spx':p},q,idx,calendar_valid=True)
        self.assertEqual(r['signals']['B']['SIGNAL_STATUS'],'CONFIRMED')
        self.assertFalse(r['SAFE_TO_ACT'])

    def test_html_escapes_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);inp=root/'input';inp.mkdir();out=root/'out'
            (inp/'metadata.json').write_text(json.dumps({'spx':{'source':'<script>alert(1)</script>'}}))
            run(inp,out,as_of='2026-10-19T08:57:00Z',start='2000-01-01')
            html=(out/'latest.html').read_text()
            self.assertNotIn('<script>alert(1)</script>',html)

    def test_partial_price_coverage_does_not_create_false_early_cash_strategy(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);inp=root/'input';inp.mkdir();out=root/'out'
            idx=pd.bdate_range('2019-01-01',periods=400);meta={}
            for name,dates in [('spy',idx),('spx',idx[100:])]:
                c=np.arange(len(dates))+100.
                pd.DataFrame({'date':dates,'open':c,'high':c+1,'low':c-1,'close':c,'adj_close':c,'dividend':0}).to_csv(inp/(name+'.csv'),index=False)
                meta[name]={'source':'https://example.org/test','retrieval_timestamp':'2026-10-19T08:00:00Z','definition':'synthetic','adjustment_method':'none','review_status':'documented'}
            (inp/'metadata.json').write_text(json.dumps(meta))
            run(inp,out,as_of='2026-10-19T08:57:00Z',start='2019-01-01',sessions_override=idx,synthetic=True,bootstrap_draws=50)
            curves=pd.read_csv(out/'strategy_equity.csv')
            self.assertEqual(curves.date.iloc[0],str(idx[100].date()))

    def test_malformed_metadata_still_produces_fail_closed_report(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);inp=root/'input';inp.mkdir();out=root/'out'
            (inp/'metadata.json').write_text('[]')
            result=run(inp,out,as_of='2026-10-19T08:57:00Z',start='2000-01-01')
            self.assertEqual(result['assessment']['SIGNAL_STATUS'],'DATA_HOLD')

    def test_nonnumeric_price_csv_can_be_audited_without_crashing(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);inp=root/'input';inp.mkdir();out=root/'out'
            (inp/'spy.csv').write_text('date,open,high,low,close,adj_close,dividend\n2020-01-02,100,102,99,oops,90,0\n')
            result=run(inp,out,as_of='2026-10-19T08:57:00Z',start='2000-01-01')
            self.assertFalse(result['assessment']['SAFE_TO_ACT'])
            self.assertIn('oops',(out/'observations.csv').read_text())

    def test_prestart_election_context_is_retained_for_january_signal(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);inp=root/'input';inp.mkdir();out=root/'out'
            idx=pd.bdate_range('2022-01-03','2023-07-31');c=np.full(len(idx),100.)
            for day,value in [('2023-01-03',102),('2023-01-04',104.04),('2023-01-05',106.1208)]:c[idx.get_loc(day)]=value
            pd.DataFrame({'date':idx,'open':c,'high':c+1,'low':c-1,'close':c,'adj_close':c,'dividend':0}).to_csv(inp/'spx.csv',index=False)
            meta={'spx':{'source':'https://example.org/test','retrieval_timestamp':'2026-10-19T08:00:00Z','definition':'synthetic','adjustment_method':'none','review_status':'documented'}}
            (inp/'metadata.json').write_text(json.dumps(meta))
            run(inp,out,as_of='2026-10-19T08:57:00Z',start='2023-01-01',sessions_override=idx,synthetic=True,bootstrap_draws=50)
            events=pd.read_csv(out/'signals.csv')
            self.assertIn('D+B',events.signal.tolist())
            self.assertTrue((events.signal_date>='2023-01-01').all())

    def test_primary_signal_configuration_cannot_silently_change_definitions(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):run(Path(d)/'input',Path(d)/'out',as_of='2026-10-19T08:57:00Z',config={'zbt':{'warmup_sessions':10}})


    def test_recent_nyse_diagnostics_are_visible_but_do_not_activate_ac(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);inp=root/'input';inp.mkdir();out=root/'out'
            sessions=pd.bdate_range('2025-01-02',periods=140)
            pd.DataFrame({'date':sessions,'advances':80,'declines':20}).to_csv(
                inp/'breadth.csv',index=False)
            meta={'breadth':{'source':'https://example.org/NYSE-research-only',
                             'retrieval_timestamp':'2026-10-19T18:00:00Z',
                             'definition':'composite candidate',
                             'adjustment_method':'none',
                             'review_status':'documented'}}
            (inp/'metadata.json').write_text(json.dumps(meta))
            result=run(inp,out,as_of='2026-10-19T18:30:00Z',
                       start='2025-01-02',sessions_override=sessions,
                       synthetic=True,bootstrap_draws=20)
            q=json.loads((out/'data_quality.json').read_text())
            b=q['breadth_diagnostics']
            self.assertEqual(b['observed_session'],str(sessions[-1].date()))
            self.assertEqual(b['source_freshness'],'CURRENT')
            self.assertEqual(b['source'],meta['breadth']['source'])
            self.assertEqual((b['advances'],b['declines']),(80,20))
            self.assertEqual(b['consecutive_valid_sessions'],140)
            self.assertTrue(b['ema100_warmup_complete'])
            self.assertFalse(b['eligible_for_signal'])
            self.assertFalse(b['ndr_comparability_validated'])
            self.assertFalse(result['assessment']['SAFE_TO_ACT'])
            self.assertEqual(result['assessment']['signals']['A']['SIGNAL_STATUS'],'DATA_HOLD')
            self.assertEqual(result['assessment']['signals']['C']['SIGNAL_STATUS'],'DATA_HOLD')
            self.assertIn('observed_session',(out/'latest.md').read_text())


if __name__=='__main__':unittest.main()
