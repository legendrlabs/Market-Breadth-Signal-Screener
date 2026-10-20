"""VIX 1999-12-31 observed-value recovery; no imputed history or source swaps."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from mbss.collectors.quality import validate_dataset
from mbss.collectors.vix_recovery import (
    CBOE_URL, FRED_SERIES_URL, FRED_TABLE_URL, parse_fred_vixcls,\n    parse_fred_vixcls_table, recover_missing_vix,
)
from mbss.pipeline import run


class Response(io.BytesIO):
    pass


class VixObservedRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.idx=pd.DatetimeIndex(['1999-12-30','1999-12-31','2000-01-03'])
        self.meta={'vix':{
            'source':CBOE_URL,'retrieval_timestamp':'2026-10-20T04:00:00Z',
            'definition':'Cboe VIX daily close','adjustment_method':'Cboe published close',
            'review_status':'documented'}}
        self.cboe=pd.DataFrame({'close':[24.76,24.21]},
                      index=pd.DatetimeIndex(['1999-12-30','2000-01-03'],name='date'))
        self.stamp='2026-10-20T05:00:00Z'
        self.fred=b'observation_date,VIXCLS\n1999-12-31,24.64\n'

    def perform(self, directory, fred=None, primary=True, meta=None, sessions=None, opener=None):
        d=Path(directory); d.mkdir(exist_ok=True)
        if not (d/'vix.csv').exists():
            self.cboe.to_csv(d/'vix.csv',index_label='date')
        info=meta if meta is not None else json.loads(json.dumps(self.meta))
        def fake(url,timeout):
            if opener is not None:return opener(url,timeout)
            self.assertIn('id=VIXCLS',url.full_url)
            self.assertIn('cosd=1999-12-31',url.full_url)
            return Response(self.fred if fred is None else fred)
        with patch('mbss.collectors.vix_recovery.market_sessions',
                   return_value=(self.idx if sessions is None else sessions,{'valid':True})):
            result=recover_missing_vix(d,d/'raw',info,start='2000-01-01',
                                       now=self.stamp,opener=fake,
                                       primary_downloaded=primary)
        return result,info,json.loads((d/'vix_recovery.json').read_text())

    def test_fred_csv_supports_both_date_headers_and_missing_symbols(self):
        parsed=parse_fred_vixcls(b'DATE,VIXCLS\n1999-12-30,24.76\n1999-12-31,.\n')
        self.assertEqual(parsed.loc['1999-12-30'],'24.76')
        self.assertEqual(parsed.loc['1999-12-31'],'.')
        with self.assertRaises(ValueError):
            parse_fred_vixcls(b'DATE,VIXCLS\n1999-12-31,24.64\n1999-12-31,24.64\n')
        with self.assertRaises(ValueError):
            parse_fred_vixcls(b'badcol,other\n1999-12-31,24.64\n')

    def test_actual_observation_recovers_exact_missing_session_and_raw_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            result,meta,snapshot=self.perform(d)
            self.assertEqual(result['status'],'RECOVERED_OBSERVED_FRED_CBOE_REPUBLICATION')
            self.assertEqual(snapshot['identified_missing_xnys_dates'],['1999-12-31'])
            self.assertEqual(snapshot['unresolved_xnys_dates'],[])
            self.assertEqual(snapshot['recovered'][0]['close'],24.64)
            vix=pd.read_csv(Path(d,'vix.csv')).set_index('date')
            self.assertEqual(len(vix),3)
            self.assertAlmostEqual(vix.loc['1999-12-31','close'],24.64)
            self.assertAlmostEqual(vix.loc['1999-12-30','close'],24.76)
            self.assertAlmostEqual(vix.loc['2000-01-03','close'],24.21)
            self.assertEqual(meta['vix']['supplemental_observations']['1999-12-31']['source'],FRED_SERIES_URL)
            self.assertFalse(meta['vix']['secondary_source_is_independent'])
            self.assertEqual(len(snapshot['raw_sha256']),64)
            self.assertTrue((Path(d)/'raw/fred_vixcls.csv').is_file())
            q=validate_dataset('vix',vix.set_axis(pd.to_datetime(vix.index)),meta['vix'],
                               self.idx,self.idx[-1])
            self.assertTrue(q['history_valid'])
            self.assertEqual(q['missing_count'],0)

    def test_dotted_or_missing_fred_value_does_not_partially_repair(self):
        for body in [b'DATE,VIXCLS\n1999-12-31,.\n',
                     b'DATE,VIXCLS\n1999-12-30,24.76\n',
                     b'DATE,VIXCLS\n1999-12-31,-1\n',
                     b'DATE,VIXCLS\n1999-12-31,0\n']:
            with tempfile.TemporaryDirectory() as d:
                self.cboe.to_csv(Path(d,'vix.csv'),index_label='date')
                original=Path(d,'vix.csv').read_bytes()
                result,meta,snapshot=self.perform(d,fred=body)
                self.assertEqual(result['status'],'FRED_OBSERVATIONS_INCOMPLETE')
                self.assertEqual(original,Path(d,'vix.csv').read_bytes())
                self.assertNotIn('supplemental_observations',meta['vix'])
                self.assertEqual(snapshot['unresolved_xnys_dates'],['1999-12-31'])

    def test_missing_primary_or_wrong_provider_fails_closed_without_network(self):
        with tempfile.TemporaryDirectory() as d:
            def forbidden(*args):raise AssertionError('must not fetch')
            result,meta,snapshot=self.perform(d,primary=False,opener=forbidden)
            self.assertEqual(result['status'],'PRIMARY_CBOE_NOT_VERIFIED')
        with tempfile.TemporaryDirectory() as d:
            invalid={'vix':{**self.meta['vix'],'source':'https://example.org/unverified'}}
            result,meta,snapshot=self.perform(d,meta=invalid,opener=forbidden)
            self.assertEqual(result['status'],'PRIMARY_CBOE_NOT_VERIFIED')

    def test_fred_network_error_preserves_raw_primary_and_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            def fail(*args):raise OSError('no network')
            result,meta,snapshot=self.perform(d,opener=fail)
            self.assertEqual(result['status'],'FRED_DOWNLOAD_OR_PARSE_FAILED')
            self.assertIn('no network',result['error'])
            self.assertEqual(len(pd.read_csv(Path(d,'vix.csv'))),2)
            self.assertNotIn('supplemental_observations',meta['vix'])

    def test_no_gap_or_calendar_failure_does_not_repair(self):
        with tempfile.TemporaryDirectory() as d:
            self.cboe.to_csv(Path(d,'vix.csv'),index_label='date')
            _,_,snap=self.perform(d,sessions=self.idx.drop(pd.Timestamp('1999-12-31')))
            self.assertEqual(snap['status'],'NO_MISSING_XNYS_SESSIONS')
        with tempfile.TemporaryDirectory() as d:
            Path(d,'vix.csv').write_text('date,close\n1999-12-30,24.76\n2000-01-03,24.21\n')
            with patch('mbss.collectors.vix_recovery.market_sessions',
                      return_value=(pd.DatetimeIndex([]),{'valid':False,'error':'calendar error'})):
                result=recover_missing_vix(d,Path(d,'raw'),json.loads(json.dumps(self.meta)),
                                           now=self.stamp,primary_downloaded=True)
            self.assertEqual(result['status'],'CALENDAR_UNAVAILABLE')

    def test_two_gaps_require_all_observations_before_repair(self):
        sessions=pd.DatetimeIndex(['1999-12-30','1999-12-31','2000-01-03','2000-01-04'])
        with tempfile.TemporaryDirectory() as d:
            # Both holes lie strictly between two original Cboe observations.
            pd.DataFrame({'close':[24.76,25.0]},
                         index=pd.DatetimeIndex(['1999-12-30','2000-01-04'],name='date')).to_csv(
                             Path(d,'vix.csv'),index_label='date')
            r,m,s=self.perform(d,sessions=sessions)
            self.assertEqual(s['status'],'FRED_OBSERVATIONS_INCOMPLETE')
            self.assertEqual(s['unresolved_xnys_dates'],['2000-01-03'])


    def test_fred_published_html_table_is_fallback_when_csv_times_out(self):
        html=(b'<html><h1>Table Data - CBOE Volatility Index: VIX</h1>'
              b'<p>Series ID VIXCLS</p><p>Source Chicago Board Options Exchange</p>'
              b'<table><tr><th>DATE</th><th>VALUE</th></tr>'
              b'<tr><td>1999-12-30</td><td>24.76</td></tr>'
              b'<tr><td>1999-12-31</td><td>24.64</td></tr>'
              b'<tr><td>2000-01-03</td><td>24.21</td></tr></table></html>')
        self.assertEqual(parse_fred_vixcls_table(html).loc['1999-12-31'],'24.64')
        def opener(request,timeout):
            if 'fredgraph.csv' in request.full_url:
                raise TimeoutError('read operation timed out')
            self.assertEqual(request.full_url,FRED_TABLE_URL)
            return Response(html)
        with tempfile.TemporaryDirectory() as d:
            result,meta,audit=self.perform(d,opener=opener)
            self.assertEqual(result['status'],'RECOVERED_OBSERVED_FRED_CBOE_REPUBLICATION')
            self.assertEqual(audit['download_url'],FRED_TABLE_URL)
            self.assertEqual([a['status'] for a in audit['download_attempts']],
                             ['FETCH_OR_PARSE_FAILED','OBSERVATIONS_COMPLETE'])
            self.assertTrue((Path(d)/'raw/fred_vixcls_table.html').is_file())
            self.assertAlmostEqual(pd.read_csv(Path(d,'vix.csv')).loc[1,'close'],24.64)

    def test_unverified_fred_html_page_never_supplies_observation(self):
        html=(b'<html><h1>Some other volatility data</h1>'
              b'<p>Series ID FAKE</p><table>'
              b'<tr><th>DATE</th><th>VALUE</th></tr>'
              b'<tr><td>1999-12-31</td><td>24.64</td></tr></table></html>')
        with self.assertRaises(ValueError):
            parse_fred_vixcls_table(html)
        def opener(request,timeout):
            if 'fredgraph.csv' in request.full_url:raise TimeoutError('timeout')
            return Response(html)
        with tempfile.TemporaryDirectory() as d:
            original=self.cboe.to_csv(Path(d,'vix.csv'),index_label='date')
            result,meta,audit=self.perform(d,opener=opener)
            self.assertEqual(result['status'],'FRED_DOWNLOAD_OR_PARSE_FAILED')
            self.assertEqual(len(pd.read_csv(Path(d,'vix.csv'))),2)
            self.assertEqual(audit['recovered'],[])

    def test_full_report_marks_fred_row_and_stays_no_trade(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);inp=root/'input';inp.mkdir()
            self.cboe.to_csv(inp/'vix.csv',index_label='date')
            result,meta,snapshot=self.perform(inp)
            (inp/'metadata.json').write_text(json.dumps(meta))
            out=root/'report'
            r=run(inp,out,as_of=self.stamp,start='1999-12-30',
                  sessions_override=self.idx,synthetic=True,bootstrap_draws=20)
            observations=pd.read_csv(out/'observations.csv')
            recovered=observations[(observations.dataset=='vix') &
                                   (observations.observation_date=='1999-12-31')]
            self.assertEqual(recovered.iloc[0]['source'],FRED_SERIES_URL)
            self.assertEqual(json.loads((out/'data_quality.json').read_text())['vix_recovery']['status'],
                             'RECOVERED_OBSERVED_FRED_CBOE_REPUBLICATION')
            self.assertIn('1999-12-31',(out/'latest.md').read_text())
            self.assertEqual(r['assessment']['SIGNAL_STATUS'],'DATA_HOLD')
            self.assertFalse(r['assessment']['SAFE_TO_ACT'])


if __name__=='__main__':
    unittest.main()
