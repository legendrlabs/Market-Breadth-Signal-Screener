import unittest
import pandas as pd
from mbss.analytics.claims import claim_audit


class ClaimTests(unittest.TestCase):
    def test_carson_sample_must_be_mature_at_publication(self):
        r=pd.DataFrame([{'signal':'B','signal_date':'2025-01-02','entry_date':'2025-01-03','exit_date':'2026-01-05','months':12,'status':'COMPLETE','return_price':.25}])
        b=next(c for c in claim_audit(r) if c['signal']=='B')
        self.assertEqual(b['reproduced_complete_n_in_claim_scope'],0)

    def test_d_event_year_scope_not_carson_publication_scope(self):
        r=pd.DataFrame([{'signal':'D','signal_date':'2022-11-08','entry_date':'2022-11-09','exit_date':'2023-05-09','months':6,'status':'COMPLETE','return_price':.10}])
        c=next(c for c in claim_audit(r) if c['signal']=='D')
        self.assertEqual(c['reproduced_complete_n_in_claim_scope'],1)

if __name__=='__main__':unittest.main()
