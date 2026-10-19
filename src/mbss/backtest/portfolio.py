import numpy as np
import pandas as pd


def portfolio_curve(events,prices,sessions,months=6,cost_bps=0,buy_hold=False):
    """Long SPY, one open position maximum; cash returns zero; open tail marked."""
    if not 0<=cost_bps<10000: raise ValueError('invalid costs')
    p=prices.reindex(sessions)
    if p.empty or p[['open','close','adj_close']].isna().any().any():
        return pd.DataFrame(columns=['equity','invested']),[]
    factor=p.adj_close/p.close; adjusted_open=p.open*factor; adjusted_close=p.adj_close
    entry_days=set()
    for event in events:
        # An old signal's actual next open predates the comparison window.
        # Never move that historical entry forward to the first available row.
        if event.date < sessions[0]:continue
        i=sessions.searchsorted(event.date,side='right')
        if i<len(sessions):entry_days.add(sessions[i])
    if buy_hold:entry_days={sessions[0]}
    cash=1.; shares=0.; target=None; trades=[]; values=[]; active=None;cost=cost_bps/10000
    for date in sessions:
        if not shares and date in entry_days:
            shares=cash/(adjusted_open.loc[date]*(1+cost)); cash=0.
            target=sessions[-1] if buy_hold else date+pd.DateOffset(months=months)
            active={'entry_date':str(date.date()),'exit_date':None,'status':'OPEN_MARKED_TO_MARKET'}
            trades.append(active)
        invested=bool(shares)
        if shares and date>=target:
            cash=shares*adjusted_close.loc[date]*(1-cost);shares=0.
            active.update(exit_date=str(date.date()),status='COMPLETE')
        values.append((date,cash+shares*adjusted_close.loc[date],invested))
    return pd.DataFrame(values,columns=['date','equity','invested']).set_index('date'),trades


def curve_metrics(curve):
    if curve.empty:return {}
    equity=curve.equity
    # Initial capital at first open is 1, including entry-day gains and costs.
    path=np.r_[1.,equity.to_numpy()]; r=path[1:]/path[:-1]-1
    years=max((curve.index[-1]-curve.index[0]).days/365.25,1/252)
    vol=float(np.std(r,ddof=1)*np.sqrt(252)) if len(r)>1 else 0.
    return {'cumulative_return':float(equity.iloc[-1]-1),
            'cagr':float(equity.iloc[-1]**(1/years)-1),'annualized_volatility':vol,
            'sharpe_rf_zero':float(np.mean(r)*252/vol) if vol>0 else None,
            'max_drawdown':float((path/np.maximum.accumulate(path)-1).min()),
            'exposure':float(curve.invested.mean())}
