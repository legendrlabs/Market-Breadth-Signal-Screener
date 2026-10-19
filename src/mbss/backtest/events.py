"""Event outcomes are descriptive; they are not a continuously invested strategy."""
import numpy as np
import pandas as pd


def trade_metrics(frame,entry,exit,total=False,cost_bps=0):
    if not 0 <= cost_bps < 10000: raise ValueError('cost_bps outside [0,10000)')
    block=frame.loc[entry:exit]
    needed=['open','high','low','close']+(['adj_close'] if total else [])
    if block.empty or entry not in block.index or exit not in block.index or not np.isfinite(block[needed].to_numpy()).all():
        return None
    factor=block.adj_close/block.close if total else pd.Series(1.,index=block.index)
    buy=float(block.loc[entry,'open']*factor.loc[entry]); sell=float(block.loc[exit,'close']*factor.loc[exit])
    if buy<=0 or sell<=0: return None
    close=block.close*factor
    path=np.r_[buy,close.to_numpy()]
    drawdown=path/np.maximum.accumulate(path)-1
    cost=cost_bps/10000
    return {'return':sell*(1-cost)/(buy*(1+cost))-1,
            'max_drawdown':float(drawdown.min()),
            'max_upside':float(max(0.,(block.high*factor).max()/buy-1)),
            'max_adverse_excursion':float(min(0.,(block.low*factor).min()/buy-1)),
            'entry_price':buy,'exit_price':sell}


def event_study(events,data,sessions,months=(1,3,6,12),as_of=None,cost_bps=0):
    rows=[]; spx=data.get('spx')
    if spx is None or spx.empty: return pd.DataFrame(columns=['signal','months','status','return_price','entry_date','exit_date'])
    as_of=pd.Timestamp(as_of if as_of is not None else sessions[-1])
    sessions=sessions[sessions<=as_of]
    for event in sorted(events,key=lambda e:(e.date,e.signal)):
        if event.date>as_of: continue
        entry_i=sessions.searchsorted(event.date,side='right')
        for month in months:
            row={**event.record(),'months':month,'status':'IMMATURE','entry_date':None,'exit_date':None,
                 'return_price':None,'spx_return_total':None,'max_drawdown':None,'max_upside':None,
                 'max_adverse_excursion':None,'entry_price':None,'exit_price':None,
                 'spx_at_signal':float(spx.loc[event.date,'close']) if event.date in spx.index else None,
                 'vix_at_signal':None,'spy_return_price':None,'spy_return_total_proxy':None,
                 'qqq_return_price':None,'qqq_return_total_proxy':None,
                 'excess_spy_price':None,'excess_qqq_price':None,'cost_bps_per_side':cost_bps}
            # Diagnostic publication-style comparisons. These same-close entries
            # are not executable after-close signals and never feed strategy P&L.
            row.update(signal_close_calendar_return=None,signal_close_session_return=None,
                       reference_session_horizon={1:21,3:63,6:126,12:252}.get(month))
            if event.date in spx.index and np.isfinite(spx.loc[event.date,'close']):
                signal_close=float(spx.loc[event.date,'close'])
                ref_i=sessions.searchsorted(event.date+pd.DateOffset(months=month))
                if ref_i<len(sessions) and sessions[ref_i] in spx.index and np.isfinite(spx.loc[sessions[ref_i],'close']):
                    row['signal_close_calendar_return']=float(spx.loc[sessions[ref_i],'close']/signal_close-1)
                distance=row['reference_session_horizon']
                signal_i=sessions.searchsorted(event.date)
                if distance is not None and signal_i+distance<len(sessions):
                    ref_date=sessions[signal_i+distance]
                    if ref_date in spx.index and np.isfinite(spx.loc[ref_date,'close']):row['signal_close_session_return']=float(spx.loc[ref_date,'close']/signal_close-1)
            vix=data.get('vix')
            if vix is not None and event.date in vix.index: row['vix_at_signal']=float(vix.loc[event.date,'close'])
            if entry_i>=len(sessions): rows.append(row);continue
            entry=sessions[entry_i]; row['entry_date']=str(entry.date())
            target=entry+pd.DateOffset(months=month); row['target_exit_date']=str(target.date())
            exit_i=sessions.searchsorted(target)
            if exit_i>=len(sessions): rows.append(row);continue
            exit=sessions[exit_i]; row['exit_date']=str(exit.date())
            if entry not in spx.index or exit not in spx.index: row['status']='DATA_HOLD';rows.append(row);continue
            block=spx.reindex(sessions[entry_i:exit_i+1])
            metrics=trade_metrics(block,entry,exit,cost_bps=cost_bps)
            if metrics is None: row['status']='DATA_HOLD';rows.append(row);continue
            row.update(status='COMPLETE',return_price=metrics.pop('return'),**metrics)
            for name in ('spy','qqq'):
                frame=data.get(name)
                if frame is None: continue
                frame=frame.reindex(sessions[entry_i:exit_i+1])
                for total,label in ((False,'price'),(True,'total_proxy')):
                    m=trade_metrics(frame,entry,exit,total=total,cost_bps=cost_bps)
                    if m is not None: row[name+'_return_'+label]=m['return']
                if row[name+'_return_price'] is not None: row['excess_'+name+'_price']=row['return_price']-row[name+'_return_price']
            rows.append(row)
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=['signal','months','status','return_price','entry_date','exit_date'])
