import importlib.util
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import pandas as pd
from mbss.collectors.context import external_context
from mbss.pipeline import run


class AuxiliaryTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('mbss.collectors.auxiliary'),'auxiliary collector missing')
        from mbss.collectors import auxiliary
        return auxiliary

    def holdings(self):
        m=self.module()
        rows=[['Fund Name:','SPY test'],['Holdings:','As of 16-Oct-2026'],
              ['Name','Ticker','Identifier','Weight'],['Alpha','AAA','id1',50],
              ['Beta','BB.B','id2',49.5],['Cash','-','cash',.5]]
        b=io.BytesIO();pd.DataFrame(rows).to_excel(b,index=False,header=False)
        return m.parse_spy_holdings(b.getvalue())

    def sessions(self):return pd.DatetimeIndex(['2026-10-15','2026-10-16'])

    def snapshot(self):
        return {'holdings_date':'2026-10-16','retrieval_timestamp':'2026-10-16T22:00:00Z',
                'constituents':[{'symbol':s} for s in ['AAA','BBB','CCC']],
                'prices':{s:{'2026-10-15':100,'2026-10-16':v} for s,v in [('AAA',101),('BBB',99),('CCC',100)]},
                'excluded_holdings':[]}

    def test_holdings_date_symbols_and_exclusions_are_audited(self):
        h=self.holdings()
        self.assertEqual(h['holdings_date'],'2026-10-16')
        self.assertEqual([r['symbol'] for r in h['constituents']],['AAA','BB-B'])
        self.assertEqual(len(h['excluded_holdings']),1)

    def test_duplicate_mapped_symbol_is_rejected(self):
        m=self.module();b=io.BytesIO()
        pd.DataFrame([['Holdings:','As of 16-Oct-2026'],['Name','Ticker','Identifier','Weight'],
                      ['A','BB.B','i',50],['B','BB-B','j',50]]).to_excel(b,index=False,header=False)
        with self.assertRaises(ValueError):m.parse_spy_holdings(b.getvalue())

    def test_counts_have_two_explicit_denominators_and_are_inert(self):
        d=self.module().assess_snapshot(self.snapshot(),self.sessions(),pd.Timestamp('2026-10-17T00:00:00Z'))
        self.assertEqual((d['advances'],d['declines'],d['unchanged']),(1,1,1))
        self.assertAlmostEqual(d['advancing_share_all'],1/3)
        self.assertAlmostEqual(d['advancing_share_active'],.5)
        self.assertFalse(d['eligible_for_signal'])
        self.assertEqual(d['status'],'REFERENCE_ONLY_PROXY')

    def test_missing_price_cannot_shrink_denominator(self):
        m=self.module();s=self.snapshot();del s['prices']['CCC']
        d=m.assess_snapshot(s,self.sessions(),pd.Timestamp('2026-10-17T00:00:00Z'))
        self.assertEqual(d['expected_count'],3)
        self.assertEqual(d['covered_count'],2)
        self.assertIsNone(d['advancing_share_all'])
        self.assertIn('INSUFFICIENT_PRICE_COVERAGE',d['flags'])

    def test_stale_holdings_future_retrieval_and_missing_session_block(self):
        m=self.module();s=self.snapshot()
        for sessions,asof,flag in [(self.sessions().append(pd.DatetimeIndex(['2026-10-19'])),pd.Timestamp('2026-10-20T00:00:00Z'),'HOLDINGS_DATE_MISMATCH'),
                (self.sessions(),pd.Timestamp('2026-10-16T21:00:00Z'),'FUTURE_RETRIEVAL'),
                (pd.DatetimeIndex([]),pd.Timestamp('2026-10-17T00:00:00Z'),'CALENDAR_UNAVAILABLE')]:
            d=m.assess_snapshot(s,sessions,asof);self.assertIn(flag,d['flags']);self.assertIsNone(d['advancing_share_all'])

    def test_spark_uses_daily_dated_closes_never_live_price_fallback(self):
        m=self.module();dates=[int(pd.Timestamp(x,tz='America/New_York').timestamp()) for x in ['2026-10-15 09:30','2026-10-16 09:30']]
        b=json.dumps({'AAA':{'symbol':'AAA','dataGranularity':86400,'timestamp':dates,'close':[100,None],'fulldayPrice':999}}).encode()
        p=m.parse_spark(b,['AAA']);self.assertIsNone(p['AAA']['2026-10-16'])
        with self.assertRaises(ValueError):m.parse_spark(b,['BBB'])

    def test_intraday_or_unknown_granularity_is_rejected(self):
        m=self.module()
        for g in [300,None]:
            b=json.dumps({'AAA':{'symbol':'AAA','dataGranularity':g,'timestamp':[1792157400],'close':[100]}}).encode()
            with self.assertRaises(ValueError):m.parse_spark(b,['AAA'])

    def test_collection_finish_after_asof_cannot_leak_later_prices(self):
        s=self.snapshot();s['collection_finished_at']='2026-10-18T00:00:00Z'
        d=self.module().assess_snapshot(s,self.sessions(),pd.Timestamp('2026-10-17T00:00:00Z'))
        self.assertIn('FUTURE_RETRIEVAL',d['flags']);self.assertIsNone(d['advancing_share_all'])

    def test_collection_uses_date_only_calendar_start(self):
        m=self.module()
        h={'holdings_date':'2026-10-16','constituents':[{'symbol':'A'+chr(65+i//26)+chr(65+i%26)} for i in range(450)],'excluded_holdings':[]}
        with TemporaryDirectory() as d:
            p=Path(d)
            with patch.object(m,'utc_now',return_value='2026-10-17T00:30:00+00:00'),patch.object(m,'parse_spy_holdings',return_value=h),patch.object(m,'urlopen',side_effect=lambda *a,**k:io.BytesIO(b'fixture')):
                m.collect_auxiliary(p,p/'raw',timeout=1)
            snap=json.loads((p/'auxiliary_breadth.json').read_text())
            self.assertNotIn('CALENDAR_UNAVAILABLE',snap['flags'])

    def test_complete_collection_preserves_every_expected_symbol_and_raw_provenance(self):
        from urllib.parse import urlparse,parse_qs
        m=self.module()
        h={'holdings_date':'2026-10-16','constituents':[{'symbol':'A'+chr(65+i//26)+chr(65+i%26)} for i in range(450)],'excluded_holdings':[]}
        dates=[int(pd.Timestamp(x,tz='America/New_York').timestamp()) for x in ['2026-10-15 09:30','2026-10-16 09:30']]
        def fetch(request,timeout):
            if request.full_url==m.HOLDINGS_URL:return io.BytesIO(b'holdings fixture')
            symbols=parse_qs(urlparse(request.full_url).query)['symbols'][0].split(',')
            return io.BytesIO(json.dumps({s:{'symbol':s,'dataGranularity':86400,'timestamp':dates,'close':[100,101]} for s in symbols}).encode())
        with TemporaryDirectory() as d:
            p=Path(d)
            with patch.object(m,'utc_now',return_value='2026-10-17T00:30:00+00:00'),patch.object(m,'parse_spy_holdings',return_value=h),patch.object(m,'urlopen',side_effect=fetch):
                attempts=m.collect_auxiliary(p,p/'raw',timeout=1)
            s=json.loads((p/'auxiliary_breadth.json').read_text())
            a=m.assess_snapshot(s,self.sessions(),pd.Timestamp('2026-10-17T00:31:00Z'))
            self.assertEqual(a['expected_count'],450);self.assertEqual(a['covered_count'],450)
            self.assertEqual(a['advancing_share_all'],1.0);self.assertEqual(a['status'],'REFERENCE_ONLY_PROXY')
            self.assertTrue(all(Path(x['raw_file']).is_file() and x['raw_sha256'] for x in attempts))

    def test_collection_failure_replaces_previous_success_with_diagnosis(self):
        m=self.module()
        with TemporaryDirectory() as d:
            p=Path(d);(p/'auxiliary_breadth.json').write_text(json.dumps(self.snapshot()))
            with patch.object(m,'urlopen',side_effect=OSError('network unavailable')):
                attempts=m.collect_auxiliary(p,p/'raw',timeout=1)
            self.assertEqual(attempts[0]['status'],'FAILED')
            snap=json.loads((p/'auxiliary_breadth.json').read_text())
            self.assertIn('SOURCE_UNAVAILABLE',snap['flags'])
            self.assertEqual(snap['prices'],{})

    def test_report_preserves_same_run_normalized_auxiliary_evidence(self):
        import hashlib
        with TemporaryDirectory() as d:
            p=Path(d);i=p/'in';i.mkdir();body=json.dumps(self.snapshot()).encode()
            (i/'auxiliary_breadth.json').write_bytes(body)
            run(i,p/'out',as_of='2026-10-17T00:00:00Z',start='2026-10-01',bootstrap_draws=20)
            saved=p/'out/auxiliary_snapshot.json';self.assertTrue(saved.is_file())
            self.assertEqual(saved.read_bytes(),body)
            m=json.loads((p/'out/run_manifest.json').read_text())
            self.assertEqual(m['output_sha256']['auxiliary_snapshot.json'],hashlib.sha256(body).hexdigest())

    def test_failed_parsing_preserves_download_hash_and_file(self):
        m=self.module();h={'holdings_date':'2026-10-16','constituents':[{'symbol':'A'+chr(65+i//26)+chr(65+i%26)} for i in range(450)],'excluded_holdings':[]}
        with TemporaryDirectory() as d:
            p=Path(d)
            with patch.object(m,'utc_now',return_value='2026-10-17T00:30:00+00:00'),patch.object(m,'parse_spy_holdings',return_value=h),patch.object(m,'urlopen',side_effect=lambda *a,**k:io.BytesIO(b'invalid-json')):
                attempts=m.collect_auxiliary(p,p/'raw',timeout=1)
            failed=[a for a in attempts if a['status']=='FAILED']
            self.assertTrue(failed)
            for a in failed:self.assertTrue(a.get('raw_sha256') and Path(a.get('raw_file','missing')).is_file())

    def test_overflowing_external_value_is_diagnosed(self):
        with TemporaryDirectory() as d:
            Path(d,'external_context.json').write_text(json.dumps([{'value':10**400}]))
            try:r=external_context(d,pd.Timestamp('2026-10-17T00:00:00Z'))
            except OverflowError:self.fail('oversized external integer must not abort the report')
            self.assertIn('INVALID_VALUE',r['observations'][0]['flags'])

    def test_missing_nonfinite_or_boolean_external_values_are_flagged(self):
        with TemporaryDirectory() as d:
            base={'metric':'advancing_share','universe':'S&P500','source':'https://example.org',
                  'session_type':'INTRADAY','observed_at':'2026-10-16T19:00:00Z','retrieval_timestamp':'2026-10-16T20:00:00Z'}
            rows=[base,{**base,'value':None},{**base,'value':float('nan')},{**base,'value':True}]
            Path(d,'external_context.json').write_text(json.dumps(rows))
            r=external_context(d,pd.Timestamp('2026-10-17T00:00:00Z'))
            for x in r['observations']:self.assertTrue(any(f in x['flags'] for f in ['MISSING_VALUE','INVALID_VALUE']))
            self.assertIsNone(r['observations'][2]['value'])

    def test_malformed_external_context_is_visible_in_both_reports(self):
        with TemporaryDirectory() as d:
            p=Path(d);i=p/'in';i.mkdir();(i/'external_context.json').write_text('{broken')
            run(i,p/'out',as_of='2026-10-17T00:00:00Z',start='2026-10-01',bootstrap_draws=20)
            for n in ['latest.md','latest.html']:
                s=(p/'out'/n).read_text();self.assertIn('EXTERNAL_CONTEXT_LOAD_FAILED',s)
                self.assertNotIn('No external reference supplied.',s)

    def test_auxiliary_does_not_enter_signals_and_asof_is_revalidated(self):
        self.module()
        with TemporaryDirectory() as d:
            p=Path(d);i=p/'in';i.mkdir();(i/'auxiliary_breadth.json').write_text(json.dumps(self.snapshot()))
            r=run(i,p/'out',as_of='2026-10-17T00:00:00Z',start='2026-10-01',bootstrap_draws=20)
            a=json.loads((p/'out/auxiliary_breadth.json').read_text())
            self.assertFalse(a['eligible_for_signal']);self.assertEqual(a['status'],'REFERENCE_ONLY_PROXY')
            self.assertEqual(r['assessment']['SIGNAL_STATUS'],'DATA_HOLD')
            self.assertNotIn('advancing_share_all',r['assessment']['metrics'])
            self.assertIn('SPY holdings breadth proxy',(p/'out/latest.html').read_text())

if __name__=='__main__':unittest.main()
