import numpy as np
import pandas as pd
from mbss.indicators.core import breadth_ratio,ema,strong_streak,expansion_count


def daily_assessment(events,data,quality,sessions,calendar_valid=True,risk_config=None):
    cfg={'vix_high':30.,'vix_five_session_jump':.25,'drawdown_alert':-.15,'post_signal_reversal':-.05,'observation_sessions':20}
    cfg.update(risk_config or {})
    last=sessions[-1] if len(sessions) else None
    deps={'A':('spx','breadth'),'B':('spx',),'C':('spx','breadth'),'D':('spx',)}
    flags=['RESEARCH_VALIDATION_PENDING','RISK_BUDGET_NOT_APPROVED'];metrics={};states={}
    spx=data.get('spx');vix=data.get('vix');breadth=data.get('breadth')
    if spx is not None and not spx.empty and 'close' in spx:
        c=spx.close
        metrics['spx_close']=float(c.iloc[-1]);metrics['strong_rally_streak']=int(strong_streak(c).iloc[-1])
        sma=c.rolling(200,min_periods=200).mean().iloc[-1]
        metrics['spx_sma200']=float(sma) if np.isfinite(sma) else None
        if not np.isfinite(sma):flags.append('TREND_HISTORY_INSUFFICIENT')
        elif c.iloc[-1]<sma:flags.append('BELOW_SMA200')
        dd=c.iloc[-1]/c.tail(252).max()-1;metrics['spx_drawdown_252']=float(dd)
        if dd<cfg['drawdown_alert']:flags.append('INDEX_DRAWDOWN')
        recent=[e for e in events if e.signal in ('A','B','C') and e.date in c.index and last is not None and len(sessions[sessions>=e.date])<=cfg['observation_sessions']+1]
        if any(c.iloc[-1]/c.loc[e.date]-1<cfg['post_signal_reversal'] for e in recent):flags.append('POST_SIGNAL_REVERSAL')
    if vix is not None and not vix.empty and 'close' in vix:
        v=vix.close;metrics['vix_close']=float(v.iloc[-1])
        if v.iloc[-1]>=cfg['vix_high']:flags.append('VIX_ELEVATED')
        jump=float(v.iloc[-1]/v.iloc[-6]-1) if len(v)>=6 else None;metrics['vix_change_5_sessions']=jump
        if jump is None:flags.append('VIX_HISTORY_INSUFFICIENT')
        elif jump>=cfg['vix_five_session_jump']:flags.append('VIX_ACCELERATING')
    else:flags.append('VIX_UNAVAILABLE')
    if breadth is not None and not breadth.empty:
        ratio=breadth_ratio(breadth.advances,breadth.declines);smooth=ema(ratio);count=expansion_count(ratio)
        for key,val in [('breadth_ratio',ratio.iloc[-1]),('zbt_ema10',smooth.iloc[-1]),('expansion_days_10',count.iloc[-1])]:metrics[key]=float(val) if np.isfinite(val) else None
        if ratio.iloc[-1]<.5:flags.append('BREADTH_WEAK')
    else:flags.append('BREADTH_UNAVAILABLE')
    for signal,required in deps.items():
        valid=calendar_valid and last is not None and all(quality.get(k,{}).get('history_valid') and quality.get(k,{}).get('fresh') for k in required)
        known=sorted([e for e in events if e.signal==signal and last is not None and e.date<=last],key=lambda e:e.date)
        event=known[-1] if known else None
        status='NO_SIGNAL'
        if not valid:status='DATA_HOLD'
        elif event:
            age=len(sessions[(sessions>event.date)&(sessions<=last)])
            if event.date==last:status='CONFIRMED'
            elif signal=='D':status='HISTORICAL_SIGNAL' if last<=event.date+pd.DateOffset(months=6) else 'EXPIRED'
            else:status='HISTORICAL_SIGNAL' if age<=cfg['observation_sessions'] else 'EXPIRED'
        if valid and signal=='B' and metrics.get('strong_rally_streak') in (1,2):status='WATCH'
        if valid and signal=='C' and metrics.get('expansion_days_10') in (4,5):status='WATCH'
        if valid and signal=='A' and breadth is not None:
            lows=np.flatnonzero((smooth<.4).to_numpy())
            if len(lows) and len(smooth)-1-lows[-1]<=10 and (event is None or event.date<smooth.index[lows[-1]]):status='WATCH'
        states[signal]={'SIGNAL_STATUS':status,'SIGNAL_DATE':str(event.date.date()) if event else None,
                        'DATA_QUALITY':'PASSED_RESEARCH' if valid else 'DATA_HOLD','SAFE_TO_ACT':False,
                        'CONFIDENCE':'LOW_RESEARCH_ONLY','RISK_FLAGS':list(flags),
                        'RECOMMENDED_ACTION':'OBSERVE_ONLY','REASON':'v0.1.0 statistics and risk budget not independently validated; no automatic allocation'}
    overall='DATA_HOLD' if not calendar_valid or not all(s['DATA_QUALITY']=='PASSED_RESEARCH' for s in states.values()) else next((v for v in ('CONFIRMED','WATCH','HISTORICAL_SIGNAL','EXPIRED') if any(s['SIGNAL_STATUS']==v for s in states.values())),'NO_SIGNAL')
    return {'SIGNAL_STATUS':overall,'SIGNAL_DATE':max((s['SIGNAL_DATE'] for s in states.values() if s['SIGNAL_DATE']),default=None),
            'DATA_QUALITY':'DATA_HOLD' if overall=='DATA_HOLD' else 'PASSED_RESEARCH',
            'SAFE_TO_ACT':False,'CONFIDENCE':'LOW_RESEARCH_ONLY','RISK_FLAGS':flags,
            'RECOMMENDED_ACTION':'OBSERVE_ONLY','REASON':'Historical replication incomplete; no trading/allocation authorization encoded',
            'as_of_session':str(last.date()) if last is not None else None,'signals':states,'metrics':metrics}
