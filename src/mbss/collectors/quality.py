"""Validation is deliberately stricter than a successful HTTP request."""
import numpy as np
import pandas as pd

PRICE_COLUMNS=['open','high','low','close','adj_close','dividend']


def reason_codes(flags,fresh=True,rows=0):
    codes=[]
    if 'NO_OBSERVATIONS' in flags:codes.append('SOURCE_UNAVAILABLE')
    if any(f!='NO_OBSERVATIONS' for f in flags):codes.append('VALIDATION_FAILED')
    if rows and not fresh:codes.append('STALE_DATA')
    return codes


def breadth_diagnostics(frame,sessions,expected_last):
    """Unverified observations only: never supply this output to signal detection."""
    from mbss.indicators.core import breadth_ratio,ema,expansion_count
    out={'status':'UNVERIFIED_REFERENCE_ONLY','eligible_for_signal':False,
         'as_of_session':str(pd.Timestamp(expected_last).date()),'recent_10_complete':False,
         'consecutive_valid_sessions':0,'breadth_ratio':None,'zbt_ema10':None,'expansion_days_10':None}
    if frame.empty or frame.index.duplicated().any() or not {'advances','declines'}.issubset(frame):return out
    p=frame.reindex(sessions)[['advances','declines']].apply(pd.to_numeric,errors='coerce')
    p=p.where((p>=0)&(p%1==0))
    ratio=breadth_ratio(p.advances,p.declines)
    if ratio.empty:return out
    n=0
    for valid in ratio.notna().iloc[::-1]:
        if not valid:break
        n+=1
    out['consecutive_valid_sessions']=n;out['recent_10_complete']=n>=10
    for key,val in [('breadth_ratio',ratio.iloc[-1]),('zbt_ema10',ema(ratio).iloc[-1]),('expansion_days_10',expansion_count(ratio).iloc[-1])]:
        out[key]=float(val) if np.isfinite(val) else None
    return out


def validate_dataset(name,frame,meta,sessions,expected_last):
    flags=[]
    required=['advances','declines'] if name=='breadth' else ['close'] if name=='vix' else PRICE_COLUMNS
    result={'source':meta.get('source'), 'retrieval_timestamp':meta.get('retrieval_timestamp'),
            'definition':meta.get('definition'), 'adjustment_method':meta.get('adjustment_method'),
            'universe':meta.get('universe'), 'universe_evidence':meta.get('universe_evidence'),
            'review_status':meta.get('review_status'), 'flags':flags}
    if frame.empty:
        flags.append('NO_OBSERVATIONS')
        return {**result,'reason_codes':reason_codes(flags),'history_valid':False,'fresh':False,'freshness':'MISSING','missing_count':len(sessions),'validation_status':'DATA_HOLD','rows':0,'start':None,'end':None}
    if not isinstance(frame.index,pd.DatetimeIndex) or frame.index.hasnans:
        flags.append('INVALID_DATES')
    if frame.index.duplicated().any(): flags.append('DUPLICATE_DATES')
    if not frame.index.is_monotonic_increasing: flags.append('UNSORTED_DATES')
    missing_columns=[c for c in required if c not in frame]
    if missing_columns: flags.append('MISSING_COLUMNS:'+','.join(missing_columns))
    expected=sessions[(sessions>=frame.index.min()) & (sessions<=frame.index.max())]
    missing=len(expected.difference(frame.index))
    if missing: flags.append('MISSING_SESSIONS')
    if len(frame.index.difference(sessions)): flags.append('NON_SESSION_DATES')
    if not missing_columns:
        values=frame[required].apply(pd.to_numeric,errors='coerce')
        if not np.isfinite(values.to_numpy()).all(): flags.append('NONFINITE_VALUES')
        if name=='breadth':
            if (values<0).any().any() or (values.sum(axis=1)<=0).any() or (values%1!=0).any().any(): flags.append('INVALID_COUNTS')
        elif name=='vix':
            if (values<=0).any().any(): flags.append('NONPOSITIVE_VALUES')
        else:
            if (values.drop(columns='dividend')<=0).any().any() or (values.dividend<0).any(): flags.append('INVALID_PRICES')
            if ((values.high < values[['open','close','low']].max(axis=1)) | (values.low > values[['open','close','high']].min(axis=1))).any(): flags.append('OHLC_INCONSISTENT')
    for field in ('source','retrieval_timestamp','definition','adjustment_method'):
        if not meta.get(field): flags.append('PROVENANCE_MISSING:'+field)
    try:
        stamp=pd.Timestamp(meta.get('retrieval_timestamp'))
        if pd.isna(stamp) or stamp.tzinfo is None: flags.append('INVALID_RETRIEVAL_TIMESTAMP')
    except (TypeError,ValueError): flags.append('INVALID_RETRIEVAL_TIMESTAMP')
    if meta.get('review_status') not in ('documented','reviewed'): flags.append('SOURCE_UNREVIEWED')
    if name=='breadth':
        universe=meta.get('universe')
        if not isinstance(universe,dict):universe={}
        needed=('exchange','etf_included','preferred_included','closed_end_fund_included','point_in_time_membership')
        if (not all(k in universe and universe[k] is not None for k in needed)
            or universe.get('exchange')!='NYSE' or not meta.get('universe_evidence')
            or meta.get('review_status')!='reviewed'
            or not all(isinstance(universe.get(k),bool) for k in needed[1:])
            or universe.get('point_in_time_membership') is not True):
            flags.append('UNIVERSE_UNVERIFIED')
        comparable=meta.get('reference_comparability')
        if not isinstance(comparable,dict) or comparable.get('status')!='reviewed_comparable' or not comparable.get('evidence'):
            flags.append('REFERENCE_COMPARABILITY_UNVERIFIED')
    fresh=frame.index.max()==pd.Timestamp(expected_last)
    return {**result,'reason_codes':reason_codes(flags,fresh,len(frame)),'history_valid':not flags,'fresh':fresh,
            'freshness':'CURRENT' if fresh else 'STALE', 'missing_count':missing,
            'validation_status':'PASSED_RESEARCH' if not flags else 'DATA_HOLD',
            'rows':len(frame),'start':str(frame.index.min().date()),'end':str(frame.index.max().date())}
