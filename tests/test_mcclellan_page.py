import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import pandas as pd

from mbss.collectors.mcclellan_page import (
    PAGE_URL, XLS_URL, parse_mcclellan_page, collect_publisher_page,
    audit_publisher_page,
)
from mbss.pipeline import run


def page(day='10/19/2026', advances=961, declines=1751, difference=-790):
    # Figures from the public McClellan table are illustrative in the tests only.
    return (f'<html><script>NYSE: 10/19/2026 Advances 9999</script><body>'
            f'<h3>NYSE: {day}</h3><table>'
            f'<tr><th> </th><th>Issues</th><th>Volume(000s)</th></tr>'
            f'<tr><th>Advances</th><td>{advances}</td><td>1575355</td></tr>'
            f'<tr><th>Declines</th><td>{declines}</td><td>2954672</td></tr>'
            f'<tr><th>Difference</th><td>{difference}</td><td>-1379317</td></tr>'
            f'</table></body></html>').encode()


class PublisherPageTests(unittest.TestCase):
    def setUp(self):
        self.sessions=pd.bdate_range('2026-10-15','2026-10-19')
        self.xls=pd.DataFrame({'advances':[100,200,961], 'declines':[250,220,1751]},
                              index=self.sessions)
        self.meta={'source':XLS_URL}
        self.asof='2026-10-20T03:00:00Z'

    def fixture(self, date='2026-10-19', advances=961, declines=1751):
        return {'status':'DOWNLOADED_REFERENCE_ONLY', 'source':PAGE_URL,
                'retrieval_timestamp':'2026-10-20T02:00:00Z',
                'date':date,'advances':advances,'declines':declines,
                'difference':advances-declines,'raw_sha256':'a'*64}

    def audit(self, d, snapshot=None, xls=None, meta=None):
        if snapshot is not None:
            Path(d,'publisher_page_snapshot.json').write_text(json.dumps(snapshot))
        return audit_publisher_page(d,self.xls if xls is None else xls,
                                    self.meta if meta is None else meta,
                                    self.sessions,pd.Timestamp(self.asof))

    def test_parse_actual_table_shape_and_ignore_script(self):
        self.assertEqual(parse_mcclellan_page(page()),
                         {'date':'2026-10-19','advances':961,'declines':1751,'difference':-790})

    def test_parser_rejects_wrong_difference_and_missing_issue_table(self):
        with self.assertRaises(ValueError):
            parse_mcclellan_page(page(difference=0))
        with self.assertRaises(ValueError):
            parse_mcclellan_page(b'<h3>NYSE: 10/19/2026</h3><p>Advances up</p>')

    def test_source_download_retains_hash_and_failed_refresh_wipes_old_values(self):
        class DummyResponse(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self,*args):self.close()
        with TemporaryDirectory() as d:
            inp=Path(d,'input');raw=Path(d,'raw')
            r=collect_publisher_page(inp,raw,opener=lambda request,timeout:DummyResponse(page()))
            self.assertEqual(r['status'],'DOWNLOADED_REFERENCE_ONLY')
            stored=json.loads((inp/'publisher_page_snapshot.json').read_text())
            self.assertEqual(stored['date'],'2026-10-19')
            self.assertEqual(stored['advances'],961)
            self.assertTrue((raw/'mcclellan_publisher_page.html').exists())
            self.assertEqual(len(stored['raw_sha256']),64)
            def failed(*args,**kwargs):raise OSError('network disabled')
            failed_attempt=collect_publisher_page(inp,raw,opener=failed)
            self.assertEqual(failed_attempt['status'],'FAILED')
            invalid=json.loads((inp/'publisher_page_snapshot.json').read_text())
            self.assertIsNone(invalid['advances'])
            self.assertEqual(invalid['status'],'SOURCE_UNAVAILABLE_OR_PARSE_FAILED')

    def test_exact_counts_means_same_publisher_not_independent_wsj(self):
        with TemporaryDirectory() as d:
            r=self.audit(d,self.fixture())
            self.assertEqual(r['status'],'COUNTS_MATCH_SAME_PUBLISHER_ONLY')
            self.assertEqual(r['delta_advances'],0)
            self.assertFalse(r['eligible_for_signal'])
            self.assertFalse(r['independent_source'])
            self.assertFalse(r['wsj_independently_verified'])

    def test_difference_and_stale_page_do_not_adjust_xls(self):
        with TemporaryDirectory() as d:
            r=self.audit(d,self.fixture(advances=960,declines=1751))
            self.assertEqual(r['status'],'COUNTS_DIFFER_SAME_PUBLISHER')
            self.assertEqual(r['delta_advances'],-1)
        with TemporaryDirectory() as d:
            r=self.audit(d,self.fixture(date='2026-10-16'))
            self.assertEqual(r['status'],'REFERENCE_NOT_COMPARABLE')
            self.assertIn('PUBLISHER_PAGE_STALE',r['flags'])

    def test_wrong_source_or_future_or_malformed_input_fails_closed(self):
        with TemporaryDirectory() as d:
            bad=self.fixture();bad['retrieval_timestamp']='2026-10-22T00:00:00Z'
            r=self.audit(d,bad)
            self.assertIn('INVALID_OR_FUTURE_RETRIEVAL_TIMESTAMP',r['flags'])
        with TemporaryDirectory() as d:
            r=self.audit(d,self.fixture(),meta={'source':'https://example.org/wrong'})
            self.assertIn('MCCLELLAN_XLS_SOURCE_NOT_CONFIRMED',r['flags'])
        with TemporaryDirectory() as d:
            r=self.audit(d,{**self.fixture(),'advances':True})
            self.assertIn('INVALID_ADVANCES',r['flags'])
        with TemporaryDirectory() as d:
            Path(d,'publisher_page_snapshot.json').write_text('broken')
            r=self.audit(d)
            self.assertEqual(r['status'],'INVALID_PUBLISHER_SNAPSHOT')

    def test_full_report_isolated_from_ac_and_contains_provenance(self):
        with TemporaryDirectory() as d:
            inp=Path(d,'input');inp.mkdir()
            self.xls.rename_axis('date').to_csv(inp/'breadth.csv')
            (inp/'publisher_page_snapshot.json').write_text(json.dumps(self.fixture()))
            (inp/'metadata.json').write_text(json.dumps({
               'breadth':{'source':XLS_URL,'review_status':'documented',
                          'definition':'NYSE published', 'adjustment_method':'none',
                          'retrieval_timestamp':'2026-10-20T02:00:00Z'}}))
            out=Path(d,'out')
            r=run(inp,out,as_of=self.asof,start='2026-10-15',
                  sessions_override=self.sessions,synthetic=True,bootstrap_draws=20)
            q=json.loads((out/'publisher_page_reconciliation.json').read_text())
            self.assertEqual(q['status'],'COUNTS_MATCH_SAME_PUBLISHER_ONLY')
            self.assertIn('publisher_page_snapshot.json',r['manifest']['input_sha256'])
            self.assertIn('SAME_PUBLISHER_REFERENCE_ONLY',(out/'latest.md').read_text())
            self.assertEqual(r['assessment']['signals']['A']['SIGNAL_STATUS'],'DATA_HOLD')
            self.assertEqual(r['assessment']['signals']['C']['SIGNAL_STATUS'],'DATA_HOLD')
            self.assertFalse(r['assessment']['SAFE_TO_ACT'])


if __name__=='__main__':
    unittest.main()
