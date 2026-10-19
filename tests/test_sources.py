import json
import unittest
import pandas as pd
from mbss.collectors.sources import parse_yahoo,parse_cboe
from mbss.collectors.calendar import as_utc,market_sessions


class SourceTests(unittest.TestCase):
    def test_yahoo_timezone_and_dividend_not_double_added(self):
        body={'chart':{'result':[{'timestamp':[1609770600],
              'indicators':{'quote':[{'open':[100],'high':[102],'low':[99],'close':[101]}],
                            'adjclose':[{'adjclose':[90]}]},
              'events':{'dividends':{'x':{'date':1609770600,'amount':1.2}}}}]}}
        p=parse_yahoo(json.dumps(body).encode())
        self.assertEqual(p.index[0],pd.Timestamp('2021-01-04'))
        self.assertEqual(p.iloc[0].dividend,1.2)
        self.assertEqual(p.iloc[0].adj_close,90)

    def test_cboe_csv(self):
        p=parse_cboe(b'DATE,OPEN,HIGH,LOW,CLOSE\n01/04/2021,20,30,10,25\n')
        self.assertEqual(p.loc['2021-01-04','close'],25)

    def test_asof_timezone_required(self):
        with self.assertRaises(ValueError):as_utc('2026-10-19')

    def test_calendar_never_falls_back_to_weekdays(self):
        idx,q=market_sessions('2026-01-01','2026-10-19T08:57:00Z')
        if q['valid']:
            self.assertNotIn(pd.Timestamp('2026-04-03'),idx)
            self.assertNotIn(pd.Timestamp('2026-06-19'),idx)
            self.assertEqual(idx[-1],pd.Timestamp('2026-10-16'))
        else:
            self.assertEqual(len(idx),0)
            self.assertIn('DEPENDENCY_MISSING',q['error'])

    def test_early_close_before_regular_close_when_calendar_available(self):
        idx,q=market_sessions('2026-11-01','2026-11-27T18:30:00Z')
        if not q['valid']:self.skipTest('exchange-calendars unavailable; gate tested separately')
        self.assertEqual(idx[-1],pd.Timestamp('2026-11-27'))

if __name__=='__main__':unittest.main()
