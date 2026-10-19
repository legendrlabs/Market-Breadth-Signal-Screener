import math
import numpy as np
import pandas as pd
from mbss.backtest.events import trade_metrics


def overlap_groups(rows):
    groups=[];end=None
    for _,row in rows.sort_values('entry_date').iterrows():
        entry=pd.Timestamp(row.entry_date);exit=pd.Timestamp(row.exit_date)
        if end is None or entry>end:groups.append([]);end=exit
        end=max(end,exit);groups[-1].append(float(row.return_price))
    return groups


def summarize(results,seed=42,draws=2000):
    out=[];rng=np.random.default_rng(seed)
    if results.empty:return out
    for (signal,months),rows in results.groupby(['signal','months'],sort=True):
        complete=rows[(rows.status=='COMPLETE') & rows.return_price.notna()]
        n=len(complete)
        item={'signal':signal,'months':int(months),'n':n,'events_total':len(rows),
              'immature':int((rows.status=='IMMATURE').sum()),'data_hold':int((rows.status=='DATA_HOLD').sum())}
        if n:
            x=complete.return_price.to_numpy(float);p=float((x>0).mean());z=1.959963984540054
            denom=1+z*z/n;center=(p+z*z/(2*n))/denom;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/denom
            clusters=overlap_groups(complete)
            boot=[]
            if len(clusters)>1:
                for _ in range(draws):
                    selected=rng.integers(0,len(clusters),len(clusters))
                    boot.append(float(np.mean([v for j in selected for v in clusters[j]])))
            ci=np.quantile(boot,[.025,.975]).tolist() if boot else None
            item.update(mean=float(x.mean()),median=float(np.median(x)),win_rate=p,
                        win_rate_wilson_95=[center-half,center+half],mean_cluster_bootstrap_95=ci,
                        overlap_clusters=len(clusters),mean_max_drawdown=float(complete.max_drawdown.mean()),
                        warning='SMALL_SAMPLE: 100% historical wins do not guarantee future success' if n<30 else 'Dependent overlapping observations; descriptive only')
        out.append(item)
    return out


def random_baseline(prices,sessions,months,seed=42,draws=2000,cost_bps=0):
    """Unconditional entry returns; only complete paths, no outcome selection."""
    values=[]
    for i,entry in enumerate(sessions):
        j=sessions.searchsorted(entry+pd.DateOffset(months=months))
        if j>=len(sessions):break
        m=trade_metrics(prices.reindex(sessions[i:j+1]),entry,sessions[j],cost_bps=cost_bps)
        if m is not None:values.append(m['return'])
    if not values:return {'eligible_entries':0,'mean':None,'median':None,'win_rate':None,'sample_mean':None}
    rng=np.random.default_rng(seed);x=np.array(values)
    return {'eligible_entries':len(x),'mean':float(x.mean()),'median':float(np.median(x)),
            'win_rate':float((x>0).mean()),'sample_mean':float(rng.choice(x,size=draws).mean()),
            'distribution_95':np.quantile(x,[.025,.975]).tolist(),
            'note':'Unconditional overlapping entry windows; not independent controls or a significance test'}
