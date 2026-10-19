import unittest
import numpy as np
import pandas as pd
from mbss.models import Event
from mbss.backtest.events import event_study, trade_metrics
from mbss.backtest.portfolio import portfolio_curve, curve_metrics
from mbss.analytics.stats import summarize, random_baseline


def prices(n=600):
    idx=pd.bdate_range('2019-01-01',periods=n)
    c=pd.Series(np.arange(n)+100.,index=idx)
    return pd.DataFrame({'open':c-.5,'high':c+1,'low':c-1,'close':c,'adj_close':c*.8,'dividend':0.},index=idx)


class BacktestTests(unittest.TestCase):
    def test_next_open_actual_entry_months_and_weekend(self):
        p=prices(); e=Event('B',p.index[3])
        r=event_study([e],{'spx':p,'spy':p,'qqq':p},p.index,months=(1,),as_of=p.index[-1])
        row=r.iloc[0]; entry=p.index[4]
        exit=p.index[p.index.searchsorted(entry+pd.DateOffset(months=1))]
        self.assertEqual(row.entry_date,entry.date().isoformat())
        self.assertEqual(row.exit_date,exit.date().isoformat())
        self.assertAlmostEqual(row.return_price,p.loc[exit,'close']/p.loc[entry,'open']-1)

    def test_immature_not_shortened_and_missing_benchmark_null(self):
        p=prices(100); e=Event('B',p.index[-3])
        r=event_study([e],{'spx':p},p.index,months=(12,),as_of=p.index[-1])
        self.assertEqual(r.iloc[0].status,'IMMATURE')
        self.assertTrue(pd.isna(r.iloc[0].return_price))
        r=event_study([Event('B',p.index[1])],{'spx':p},p.index,months=(1,),as_of=p.index[-1])
        self.assertTrue(pd.isna(r.iloc[0].spy_return_price))

    def test_costs_and_close_drawdown_include_entry_open(self):
        p=prices(4); p['open']=100.; p['close']=[90,95,80,110];p['high']=[100,100,100,120];p['low']=[85,90,70,100]
        r=trade_metrics(p,p.index[0],p.index[-1],cost_bps=10)
        self.assertAlmostEqual(r['return'],110*.999/(100*1.001)-1)
        self.assertAlmostEqual(r['max_drawdown'],80/100-1)
        self.assertAlmostEqual(r['max_upside'],.2)
        self.assertAlmostEqual(r['max_adverse_excursion'],-.3)

    def test_total_return_proxy_uses_same_day_open_factor(self):
        p=prices(4);p['open']=100;p['close']=100;p['adj_close']=[90,90,100,100]
        price=trade_metrics(p,p.index[0],p.index[-1])
        total=trade_metrics(p,p.index[0],p.index[-1],total=True)
        self.assertEqual(price['return'],0)
        self.assertAlmostEqual(total['return'],100/90-1)

    def test_internal_missing_prices_invalid_not_bridged(self):
        p=prices();p.iloc[15,p.columns.get_loc('close')]=np.nan
        r=event_study([Event('B',p.index[1])],{'spx':p},p.index,months=(1,),as_of=p.index[-1])
        self.assertEqual(r.iloc[0].status,'DATA_HOLD')

    def test_portfolio_cash_zero_and_no_overlapping_entries(self):
        p=prices(400);events=[Event('A',p.index[3]),Event('A',p.index[5])]
        curve,trades=portfolio_curve(events,p,p.index,months=6)
        self.assertEqual(len(trades),1)
        self.assertTrue((curve.iloc[:4].equity==1).all())
        self.assertGreater(curve_metrics(curve)['exposure'],0)

    def test_random_baseline_reproducible(self):
        p=prices(400)
        a=random_baseline(p,p.index,1,seed=11,draws=100)
        b=random_baseline(p,p.index,1,seed=11,draws=100)
        self.assertEqual(a,b)
        self.assertGreater(a['eligible_entries'],100)

    def test_overlap_clusters_and_deterministic_bootstrap(self):
        rows=pd.DataFrame([
          {'signal':'A','months':6,'status':'COMPLETE','return_price':.1,'entry_date':'2020-01-01','exit_date':'2020-07-01','max_drawdown':-.1},
          {'signal':'A','months':6,'status':'COMPLETE','return_price':.2,'entry_date':'2020-02-01','exit_date':'2020-08-01','max_drawdown':-.2},
          {'signal':'A','months':6,'status':'COMPLETE','return_price':-.1,'entry_date':'2021-02-01','exit_date':'2021-08-01','max_drawdown':-.3}])
        a=summarize(rows,seed=7,draws=200)
        self.assertEqual(a,summarize(rows,seed=7,draws=200))
        self.assertEqual(a[0]['n'],3);self.assertEqual(a[0]['overlap_clusters'],2)
        self.assertAlmostEqual(a[0]['win_rate'],2/3)

    def test_portfolio_initial_capital_loss_in_drawdown(self):
        idx=pd.bdate_range('2020-01-01',periods=3)
        c=pd.DataFrame({'equity':[.9,.95,.8],'invested':True},index=idx)
        self.assertAlmostEqual(curve_metrics(c)['max_drawdown'],-.2)

    def test_old_signal_not_remapped_to_new_coverage_start(self):
        p=prices(400)
        curve,trades=portfolio_curve([Event('B',p.index[1])],p,p.index[50:],months=6)
        self.assertEqual(trades,[])
        self.assertTrue((curve.equity==1.).all())

    def test_publication_reference_returns_do_not_change_next_open_execution(self):
        p=prices(600);event=Event('B',p.index[2])
        r=event_study([event],{'spx':p},p.index,months=(12,),as_of=p.index[-1]).iloc[0]
        self.assertAlmostEqual(r.signal_close_session_return,p.close.iloc[254]/p.close.iloc[2]-1)
        self.assertNotEqual(r.signal_close_session_return,r.return_price)

if __name__=='__main__': unittest.main()
