"""Case-pack tests use synthetic observations; no historic NYSE values invented."""
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pandas as pd

from mbss.c_episode_audit import diagnose_episodes, run_episode_audit

SHA='f'*64


class EpisodeTests(unittest.TestCase):
    def setUp(self):
        self.days=pd.bdate_range('2011-07-01','2012-02-01')
        self.case=pd.Timestamp('2011-11-03')
        self.prior=pd.Timestamp('2011-10-18')
        self.main=pd.DataFrame({'advances':4,'declines':6,'unchanged':0},index=self.days)
        i=self.days.get_loc(self.case)
        for day in self.days[i-5:i+1]:
            self.main.loc[day,['advances','declines']]=[8,2]
        self.refs=[pd.Timestamp('1982-08-25'),pd.Timestamp('2009-07-23'),
                   self.prior]

    def test_2011_synthetic_extra_is_diagnosed_without_any_signal_approval(self):
        r=diagnose_episodes(self.main,self.days,self.refs,'SYNTHETIC_RESEARCH',SHA)
        c=r['focus_cases'][2]
        self.assertEqual(c['status'],'UNVERIFIED_EXTRA_REPRODUCED_IN_THIS_SOURCE')
        self.assertEqual(c['strict_70_days_last_10'],6)
        self.assertTrue(c['candidate_valid_under_primary_research_rule'])
        self.assertEqual(c['preceding_carson_printed_date'],'2011-10-18')
        self.assertEqual(c['trading_sessions_since_preceding_printed_date'],
                         self.days.get_loc(self.case)-self.days.get_loc(self.prior))
        self.assertIsNone(c['research_variants_signal_on_date']['UNCHANGED_DENOMINATOR_RESEARCH_COOLDOWN10'] if 'unchanged' not in self.main else None)
        self.assertFalse(c['safe_to_act'])
        self.assertFalse(r['eligible_for_signal'])
        self.assertEqual(r['carson_ndr_duplicate_suppression'],'UNVERIFIED')
        rows=[row for row in r['rows'] if row['case_date']=='2011-11-03']
        self.assertTrue(all(row['breadth_ratio'] is not None for row in rows))
        self.assertEqual(len(rows),127)

    def test_missing_data_never_becomes_zero_or_a_suppressed_event(self):
        bad=self.main.copy()
        bad.loc[self.days[self.days.get_loc(self.case)-4],'advances']=float('nan')
        r=diagnose_episodes(bad,self.days,self.refs,'SYNTHETIC_RESEARCH',SHA)
        c=r['focus_cases'][2]
        self.assertEqual(c['status'],'INCOMPLETE_11_SESSION_CONTEXT')
        self.assertIsNone(c['candidate_valid_under_primary_research_rule'])
        self.assertTrue(any(row['breadth_ratio'] is None for row in r['rows'] if row['case_date']=='2011-11-03'))
        self.assertEqual(c['alternative_provider_comparison']['status'],'NOT_SUPPLIED')

    def test_same_date_comparison_is_not_automatic_splice(self):
        comp=self.main.copy()
        comp.loc[self.case,'advances']=9
        r=diagnose_episodes(self.main,self.days,self.refs,'FIRST',SHA,
                            compare=comp,comparison_source='SECOND',comparison_sha='e'*64)
        c=r['focus_cases'][2]
        self.assertEqual(c['alternative_provider_comparison']['candidate_date'],'MISMATCH')
        self.assertIn('2011-11-03',c['alternative_provider_comparison']['mismatched_dates'])
        self.assertEqual(c['status'],'UNVERIFIED_EXTRA_REPRODUCED_IN_THIS_SOURCE')
        self.assertFalse(r['safe_to_act'])

    def test_no_dates_for_1982_2009_is_coverage_not_failed_signal(self):
        r=diagnose_episodes(self.main,self.days,self.refs,'SYNTHETIC_RESEARCH',SHA)
        self.assertEqual([x['status'] for x in r['focus_cases'][:2]],
                         ['OUTSIDE_VALIDATED_CALENDAR_WINDOW']*2)

    def test_immutable_output_and_dated_provenance(self):
        with TemporaryDirectory() as d:
            root=Path(d)
            sample=root/'data.csv'
            self.main.rename_axis('date').to_csv(sample)
            ref=root/'ref.csv'
            with ref.open('w',newline='') as handle:
                w=csv.DictWriter(handle,fieldnames=['signal','date_as_printed'])
                w.writeheader()
                for x in self.refs:
                    w.writerow({'signal':'C','date_as_printed':str(x.date())})
            with patch('mbss.c_episode_audit.market_sessions',
                       return_value=(self.days,{'valid':True})):
                r=run_episode_audit(sample,ref,root/'report','SYNTHETIC_FIXTURE',
                                    '2012-02-02T20:00:00Z')
            self.assertEqual(r['focus_cases'][2]['strict_70_days_last_10'],6)
            self.assertTrue((root/'report/episode_daily_windows.csv').is_file())
            text=(root/'report/episode_audit.md').read_text()
            self.assertIn('2011-11-03',text)
            self.assertIn('SAFE_TO_ACT=False',text)
            metadata=json.loads((root/'report/episode_audit.json').read_text())
            self.assertNotIn('rows',metadata)
            self.assertEqual(len(metadata['source_sha256']),64)
            with self.assertRaises(FileExistsError):
                with patch('mbss.c_episode_audit.market_sessions',
                           return_value=(self.days,{'valid':True})):
                    run_episode_audit(sample,ref,root/'report','SYNTHETIC_FIXTURE',
                                      '2012-02-02T20:00:00Z')

    def test_malformed_input_and_missing_comparison_source_fail_closed(self):
        with TemporaryDirectory() as d:
            root=Path(d)
            invalid=root/'bad.csv'
            invalid.write_text('date,advances,declines\n2011-11-03,5,5\n2011-11-03,5,5\n')
            with self.assertRaises(ValueError):
                from mbss.c_episode_audit import _read_observed_csv
                _read_observed_csv(invalid)
            with self.assertRaises(ValueError):
                diagnose_episodes(self.main,self.days,self.refs,'MAIN',SHA,
                                  compare=self.main,comparison_source=None,
                                  comparison_sha=SHA)


if __name__=='__main__':
    unittest.main()
