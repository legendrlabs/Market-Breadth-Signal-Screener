"""Synthetic signal C audit cases; never interpreted as actual Carson events."""
import csv
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from mbss.c_reference_audit import (
    _c_events, _ratio, published_c_dates, reconcile_c, run_c_audit,
)

SHA='a'*64


class CReferenceAuditTests(unittest.TestCase):
    def setUp(self):
        self.idx=pd.bdate_range('2020-01-02',periods=35)
        self.frame=pd.DataFrame({'advances':[4]*11+[8]*6+[4]*18,
                                 'declines':[6]*11+[2]*6+[6]*18},index=self.idx)

    def test_reference_table_keeps_eight_mature_and_new_unmatured_date(self):
        p=Path(__file__).resolve().parents[1]/'docs/reference/carson-2025-04-25-events-as-printed.csv'
        refs=published_c_dates(p)
        self.assertEqual(len(refs),9)
        self.assertIn(pd.Timestamp('1982-08-25'),refs)
        self.assertIn(pd.Timestamp('2020-04-17'),refs)
        self.assertIn(pd.Timestamp('2025-04-23'),refs)

    def test_fully_observed_first_edge_is_unverified_not_an_approved_signal(self):
        event=self.idx[16]
        result=reconcile_c(self.frame,self.idx,[event],'SYNTHETIC_REFERENCE',SHA)
        self.assertEqual(result['status'],'PARTIAL_REFERENCE_DATE_RECONCILIATION_UNVERIFIED')
        primary=result['variants'][0]
        self.assertEqual(primary['matched'],[str(event.date())])
        self.assertEqual(primary['extras'],[])
        self.assertEqual(primary['missed'],[])
        self.assertFalse(result['safe_to_act'])
        self.assertFalse(result['eligible_for_signal'])
        self.assertEqual(result['universe_comparability'],'UNVERIFIED')
        self.assertEqual(result['suppression_policy'],'UNVERIFIED')

    def test_missing_history_not_misreported_as_failed_replication(self):
        reference=pd.Timestamp('1982-08-25')
        result=reconcile_c(self.frame,self.idx,[reference],'SYNTHETIC_REFERENCE',SHA)
        self.assertEqual(result['status'],'INSUFFICIENT_REFERENCE_COVERAGE')
        self.assertEqual(result['reference_dates'][0]['coverage'],'OUTSIDE_VALIDATED_CALENDAR_OR_DATA')
        self.assertEqual(result['variants'][0]['comparable_reference_dates'],0)
        self.assertEqual(result['variants'][0]['missed'],[])

    def test_candidate_without_printed_match_is_explicit_extra(self):
        result=reconcile_c(self.frame,self.idx,[pd.Timestamp('2020-04-17')],
                           'SYNTHETIC_REFERENCE',SHA)
        self.assertIn(str(self.idx[16].date()),result['variants'][0]['extras'])
        self.assertFalse(result['primary_candidates'][0]['eligible_for_signal'])

    def test_non_session_and_pre_1970_are_identified_not_grafted(self):
        extended=pd.concat([
            pd.DataFrame({'advances':[2],'declines':[3]},
                         index=[pd.Timestamp('1965-02-15')]),
            self.frame,
            pd.DataFrame({'advances':[4],'declines':[6]},
                         index=[pd.Timestamp('2020-01-04')]),
        ]).sort_index()
        result=reconcile_c(extended,self.idx,[self.idx[16]],'UNVERIFIED',SHA)
        self.assertEqual(result['raw_rows_before_calendar_floor'],1)
        self.assertIn('2020-01-04',result['non_session_rows_excluded'])

    def test_missing_breaks_window_and_strict_70_differs_from_inclusive(self):
        x=self.frame.copy()
        x.loc[self.idx[13],'advances']=np.nan
        result=reconcile_c(x,self.idx,[self.idx[16]],'SYNTHETIC',SHA)
        self.assertEqual(result['status'],'INSUFFICIENT_REFERENCE_COVERAGE')
        self.assertEqual(result['reference_dates'][0]['coverage'],'INCOMPLETE_11_SESSION_CONTEXT')
        ratio=pd.Series([.4]*11+[.70]*6+[.4]*18,index=self.idx)
        self.assertEqual(_c_events(ratio,inclusive=False),[])
        self.assertEqual(_c_events(ratio,inclusive=True),[self.idx[16]])

    def test_unchanged_variant_explicit_when_field_missing(self):
        result=reconcile_c(self.frame,self.idx,[self.idx[16]],'SYNTHETIC',SHA)
        self.assertEqual(result['variants'][-1]['status'],'UNCHANGED_COUNTS_UNAVAILABLE')
        other=self.frame.assign(unchanged=40)
        result2=reconcile_c(other,self.idx,[self.idx[16]],'SYNTHETIC',SHA)
        self.assertEqual(result2['variants'][-1]['status'],'RESEARCH_SENSITIVITY_ONLY')
        self.assertEqual(result2['variants'][-1]['candidate_dates'],[])

    def test_immutable_local_cli_outputs_and_hashes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            observation=root/'source.csv'
            self.frame.rename_axis('date').to_csv(observation)
            ref=root/'printed.csv'
            with ref.open('w',newline='') as out:
                writer=csv.DictWriter(out,fieldnames=['signal','date_as_printed'])
                writer.writeheader()
                writer.writerow({'signal':'C','date_as_printed':str(self.idx[16].date())})
            with patch('mbss.c_reference_audit.market_sessions',
                       return_value=(self.idx,{'valid':True})):
                r=run_c_audit(observation,ref,root/'results','SYNTHETIC ONLY',
                              '2020-03-01T00:00:00Z')
            self.assertTrue((root/'results/c_reconciliation.json').exists())
            self.assertTrue((root/'results/c_candidates.csv').exists())
            self.assertEqual(r['variants'][0]['matched'],[str(self.idx[16].date())])
            self.assertEqual(len(json.loads((root/'results/c_reconciliation.json').read_text())['source_sha256']),64)
            with self.assertRaises(FileExistsError):
                with patch('mbss.c_reference_audit.market_sessions',
                           return_value=(self.idx,{'valid':True})):
                    run_c_audit(observation,ref,root/'results','SYNTHETIC ONLY',
                                '2020-03-01T00:00:00Z')


if __name__=='__main__':
    unittest.main()
