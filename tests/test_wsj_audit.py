"""Provenance, date and non-interference tests for optional WSJ reference counts."""
import json
import tempfile
import unittest
from pathlib import Path
import pandas as pd

from mbss.collectors.wsj_audit import audit_wsj_reference, WSJ_URL, MCCLELLAN_URL
from mbss.pipeline import run


class WsjAuditTests(unittest.TestCase):
    def setUp(self):
        self.days=pd.bdate_range('2026-10-12','2026-10-16')
        self.actual=pd.DataFrame({'advances':[100,200,300,400,500],
                                  'declines':[900,800,700,600,500]},index=self.days)
        self.meta={'source':MCCLELLAN_URL}
        self.asof='2026-10-20T05:00:00Z'

    def record(self, date='2026-10-16', advances=500, declines=500, stage='FINAL',
               captured_at='2026-10-17T01:30:00Z'):
        return {'date':date,'advances':advances,'declines':declines,
                'stage':stage,'source':WSJ_URL,'universe':'NYSE',
                'captured_at':captured_at,'evidence_url':'https://example.org/dated-source-evidence'}

    def audit(self, directory, records, meta=None):
        if records is not None:
            Path(directory,'wsj_reference.json').write_text(json.dumps(records))
        return audit_wsj_reference(directory,self.actual,self.meta if meta is None else meta,
                                   self.days,pd.Timestamp(self.asof))

    def test_absent_snapshot_is_explicitly_unavailable(self):
        with tempfile.TemporaryDirectory() as d:
            a=self.audit(d,None)
            self.assertEqual(a['status'],'NO_WSJ_REFERENCE')
            self.assertEqual(a['compared_rows'],0)
            self.assertFalse(a['eligible_for_signal'])
            self.assertFalse(a['safe_to_act'])

    def test_same_date_exact_counts_and_mismatch_do_not_verify_ndr(self):
        with tempfile.TemporaryDirectory() as d:
            a=self.audit(d,[self.record(),self.record(date='2026-10-15',
                                      advances=409,declines=600,
                                      captured_at='2026-10-16T01:30:00Z')])
            self.assertEqual(a['status'],'MISMATCH_OBSERVED')
            self.assertEqual((a['compared_rows'],a['exact_matches'],a['mismatches']),(2,1,1))
            self.assertEqual(a['rows'][1]['difference_advances'],9)
            self.assertEqual(a['rows'][0]['status'],'COUNTS_MATCH_REFERENCE_ONLY')
            self.assertFalse(a['ndr_comparability_validated'])
            self.assertFalse(a['same_universe_verified'])

    def test_preliminary_and_early_final_capture_do_not_compare(self):
        with tempfile.TemporaryDirectory() as d:
            a=self.audit(d,[self.record(stage='PRELIMINARY'),
                            self.record(date='2026-10-15',advances=400,declines=600,
                                        captured_at='2026-10-15T19:00:00Z')])
            self.assertEqual(a['compared_rows'],0)
            self.assertEqual(a['status'],'NO_COMPARABLE_ROWS')
            self.assertIn('NOT_FINAL_REPORTED',a['rows'][0]['flags'])
            self.assertIn('CAPTURE_BEFORE_WSJ_FINAL_WINDOW',a['rows'][1]['flags'])

    def test_duplicate_dates_and_missing_evidence_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            x=self.record()
            y=self.record()
            y['evidence_url']=None
            a=self.audit(d,[x,y])
            self.assertEqual(a['status'],'REVIEW_REQUIRED')
            self.assertEqual(a['compared_rows'],0)
            self.assertTrue(all('DUPLICATE_FINAL_DATE' in row['flags'] for row in a['rows']))

    def test_future_and_invalid_counts_and_wrong_source_are_inert(self):
        with tempfile.TemporaryDirectory() as d:
            x=self.record(advances=True)
            y=self.record(date='2026-10-19',captured_at='2026-10-21T01:00:00Z')
            z=self.record(date='2026-10-15',advances=400,declines=600,
                          captured_at='2026-10-16T01:30:00Z')
            z['source']='https://example.org/unauthorized-source'
            a=self.audit(d,[x,y,z])
            self.assertEqual(a['compared_rows'],0)
            self.assertIn('INVALID_COUNTS',a['rows'][0]['flags'])
            self.assertIn('NOT_COMPLETED_XNYS_SESSION',a['rows'][1]['flags'])
            self.assertIn('UNRECOGNIZED_REFERENCE_SOURCE',a['rows'][2]['flags'])

    def test_unconfirmed_mcclellan_source_blocks_numeric_comparison(self):
        with tempfile.TemporaryDirectory() as d:
            a=self.audit(d,[self.record()],meta={'source':'https://example.org/fake'})
            self.assertEqual(a['compared_rows'],0)
            self.assertIn('MCCLELLAN_SOURCE_NOT_CONFIRMED',a['errors'])

    def test_malformed_reference_produces_hold_not_exception(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d,'wsj_reference.json').write_text('{ broken')
            a=audit_wsj_reference(d,self.actual,self.meta,self.days,pd.Timestamp(self.asof))
            self.assertEqual(a['status'],'INVALID_WSJ_REFERENCE')
            self.assertFalse(a['eligible_for_signal'])

    def test_full_pipeline_keeps_source_only_comparison_out_of_ac(self):
        with tempfile.TemporaryDirectory() as d:
            inp=Path(d,'input');inp.mkdir();out=Path(d,'out')
            self.actual.rename_axis('date').to_csv(inp/'breadth.csv')
            (inp/'wsj_reference.json').write_text(json.dumps([self.record()]))
            (inp/'metadata.json').write_text(json.dumps({
                'breadth':{**self.meta,'retrieval_timestamp':self.asof,
                           'definition':'McClellan recent observed NYSE counts',
                           'adjustment_method':'unadjusted','review_status':'documented'}
            }))
            result=run(inp,out,as_of=self.asof,start='2026-10-12',
                       sessions_override=self.days,synthetic=True,bootstrap_draws=20)
            a=json.loads((out/'wsj_reconciliation.json').read_text())
            self.assertEqual(a['exact_matches'],1)
            self.assertIn('WSJ vs McClellan',(out/'latest.md').read_text())
            self.assertEqual(result['assessment']['signals']['A']['SIGNAL_STATUS'],'DATA_HOLD')
            self.assertEqual(result['assessment']['signals']['C']['SIGNAL_STATUS'],'DATA_HOLD')
            self.assertFalse(result['assessment']['SAFE_TO_ACT'])
            self.assertIn('wsj_reference.json',result['manifest']['input_sha256'])


if __name__ == '__main__':
    unittest.main()
