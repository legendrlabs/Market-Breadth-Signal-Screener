"""Isolated, auditable case files for the three unexplained Carson C extras.

Only supplied observed daily A/D data may be analyzed. This is not a
Carson/NDR replication, a historical source splice, or a trading signal.
"""
import csv
import hashlib
import json
from pathlib import Path

import pandas as pd

from mbss.c_reference_audit import (
    DEFAULT_VARIANTS, _c_events, _ratio, published_c_dates,
)
from mbss.collectors.calendar import as_utc, market_sessions

CASE_DATES=('1982-10-18', '2009-09-15', '2011-11-03')
DEFAULT_REFERENCE='docs/reference/carson-2025-04-25-events-as-printed.csv'


def _read_observed_csv(file):
    data=Path(file).read_bytes()
    frame=pd.read_csv(file,dtype={'date':'string'})
    if 'date' not in frame or not {'advances','declines'}.issubset(frame.columns):
        raise ValueError('source needs date, advances and declines')
    dates=frame.pop('date')
    if dates.isna().any() or not dates.str.fullmatch(r'\d{4}-\d{2}-\d{2}').all():
        raise ValueError('source dates must be YYYY-MM-DD')
    idx=pd.DatetimeIndex(pd.to_datetime(dates,format='%Y-%m-%d',errors='raise'))
    if idx.has_duplicates or not idx.is_monotonic_increasing:
        raise ValueError('source must contain unique ascending dates')
    frame.index=idx
    frame.index.name='date'
    return frame,hashlib.sha256(data).hexdigest()


def _item(value):
    if pd.isna(value):return None
    if isinstance(value,(int,float)):return int(value) if float(value).is_integer() else float(value)
    try:return float(value)
    except (ValueError,TypeError):return None


def diagnose_episodes(frame, sessions, reference_dates, source, sha, compare=None,
                      comparison_source=None, comparison_sha=None, radius=63):
    """Return source-constrained episode diagnostics and individual date rows."""
    sessions=pd.DatetimeIndex(sessions)
    if sessions.empty or sessions.has_duplicates or not sessions.is_monotonic_increasing:
        raise ValueError('NYSE exchange calendar invalid')
    if not source or not isinstance(sha,str) or len(sha)!=64:
        raise ValueError('primary source provenance is mandatory')
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError('source observations duplicated or unordered')
    if compare is not None and (compare.index.has_duplicates or
                                not compare.index.is_monotonic_increasing or
                                not comparison_source or not comparison_sha):
        raise ValueError('comparison provenance or dates invalid')
    data=frame.reindex(sessions)
    ratio=_ratio(data)
    comp=compare.reindex(sessions) if compare is not None else None
    active=ratio.gt(.70).astype(float).where(ratio.notna())
    count=active.rolling(10,min_periods=10).sum()
    eleven=ratio.notna().astype(int).rolling(11,min_periods=11).sum().eq(11)
    variant_dates={}
    for label,inclusive,cooldown,unchanged in DEFAULT_VARIANTS:
        r=_ratio(data,include_unchanged=unchanged)
        variant_dates[label]=set(_c_events(r,inclusive,cooldown)) if r is not None else None
    historical=sorted(pd.Timestamp(x) for x in reference_dates)
    cases=[]
    rows=[]
    for raw in CASE_DATES:
        date=pd.Timestamp(raw)
        preceding=[d for d in historical if d<date]
        previous=max(preceding) if preceding else None
        in_cal=date in sessions
        i=int(sessions.get_loc(date)) if in_cal else None
        previous_in_cal=previous in sessions if previous is not None else False
        span=(i-int(sessions.get_loc(previous))) if in_cal and previous_in_cal else None
        indices=sessions[max(0,i-radius):min(len(sessions),i+radius+1)] if in_cal else pd.DatetimeIndex([])
        observed=int(ratio.loc[indices].notna().sum()) if len(indices) else 0
        complete=bool(eleven.loc[date]) if in_cal else False
        valid_candidate=bool(date in variant_dates[DEFAULT_VARIANTS[0][0]]) if in_cal else False
        if date<sessions.min() or date>sessions.max():
            status='OUTSIDE_VALIDATED_CALENDAR_WINDOW'
        elif not in_cal:
            status='NOT_A_VALIDATED_EXCHANGE_SESSION'
        elif not observed:
            status='SOURCE_UNAVAILABLE_FOR_EPISODE'
        elif not complete:
            status='INCOMPLETE_11_SESSION_CONTEXT'
        elif valid_candidate:
            status='UNVERIFIED_EXTRA_REPRODUCED_IN_THIS_SOURCE'
        else:
            status='EXTRA_NOT_REPRODUCED_IN_THIS_SOURCE'
        variants={k:None if v is None or not complete else date in v
                  for k,v in variant_dates.items()}
        overlap={'status':'NOT_SUPPLIED','compared_days':0,'matched_pairs':0,
                 'mismatched_dates':[],'candidate_date':None}
        if comp is not None and len(indices):
            overlap['status']='NO_COMPARABLE_DATES'
            equal=0
            mismatches=[]
            common=[]
            for day in indices:
                a=data.loc[day] if day in data.index else None
                b=comp.loc[day] if day in comp.index else None
                if a is None or b is None:continue
                values=[pd.to_numeric(x.get(k),errors='coerce') for x in (a,b) for k in ('advances','declines')]
                if not all(pd.notna(v) and v>=0 and float(v).is_integer() for v in values):continue
                common.append(day)
                if values[0]==values[2] and values[1]==values[3]:equal+=1
                else:mismatches.append(str(day.date()))
            overlap.update(compared_days=len(common),matched_pairs=equal,mismatched_dates=mismatches)
            if common:
                overlap['status']='SAME_DATE_COUNTS_COMPARED_NOT_UNIVERSE_CERTIFIED'
            if date in common:
                overlap['candidate_date']='MATCH' if date not in mismatches else 'MISMATCH'
        case={'date':raw,'status':status,
              'first_order_model':'6/10 strictly >70%, first rising edge, 10-session cooldown',
              'source_observed_days_in_window':observed,
              'window_exchange_days':len(indices),
              'has_complete_11_session_context':complete,
              'strict_70_days_last_10':_item(count.loc[date]) if in_cal else None,
              'candidate_valid_under_primary_research_rule':valid_candidate if complete else None,
              'preceding_carson_printed_date':str(previous.date()) if previous is not None else None,
              'trading_sessions_since_preceding_printed_date':span,
              'suppression_note':'Only a hypothetical cooldown >= distance could suppress this extra after prior printed event; not a published Carson rule.' if span is not None else 'Insufficient calendar context for printed-event distance',
              'research_variants_signal_on_date':variants,
              'alternative_provider_comparison':overlap,
              'eligible_for_signal':False,'safe_to_act':False}
        cases.append(case)
        for day in indices:
            r=data.loc[day]
            row={'case_date':raw,'observation_date':str(day.date()),
                 'advances':_item(r.get('advances')),
                 'declines':_item(r.get('declines')),
                 'unchanged':_item(r.get('unchanged')) if 'unchanged' in data else None,
                 'breadth_ratio':float(ratio.loc[day]) if pd.notna(ratio.loc[day]) else None,
                 'over_70':bool(ratio.loc[day]>.70) if pd.notna(ratio.loc[day]) else None,
                 'eligible_days_in_last_10':_item(count.loc[day]),
                 'is_reference_printed_date':day in historical,
                 'is_focus_candidate':day==date}
            rows.append(row)
    return {'status':'EPISODE_AUDIT_RESEARCH_ONLY','focus_cases':cases,
            'source':source,'source_sha256':sha,
            'comparison_source':comparison_source,'comparison_sha256':comparison_sha,
            'calendar_coverage':[str(sessions.min().date()),str(sessions.max().date())],
            'window_radius_trading_sessions':radius,'rows':rows,
            'universe_comparability':'UNVERIFIED',
            'carson_ndr_duplicate_suppression':'UNVERIFIED',
            'eligible_for_signal':False,'safe_to_act':False,
            'limitations':[
                'Unicorn is a mixed-source median, not independently certified NYSE Composite/NDR.',
                'A near match or cutoff experiment cannot prove Carson event suppression.',
                'Missing source dates remain null and no gap is backfilled.',
                'This audit does not feed daily MBSS run, A/C signals, or trading.']}


def run_episode_audit(input_csv,reference_csv,output_dir,source,as_of,
                      comparison_csv=None,comparison_source=None):
    out=Path(output_dir)
    if out.exists():raise FileExistsError('Output must be an unused immutable directory')
    main,main_sha=_read_observed_csv(input_csv)
    if comparison_csv:
        comp,comp_sha=_read_observed_csv(comparison_csv)
        if not comparison_source:
            raise ValueError('comparison source must be provided')
    else:comp,comp_sha=None,None
    stamp=as_utc(as_of)
    start=max(pd.Timestamp('1970-01-01'),min(main.index.min(),pd.Timestamp(CASE_DATES[0])-pd.Timedelta(days=150)))
    sessions,calendar=market_sessions(start,stamp)
    if not calendar.get('valid') or sessions.empty:
        raise ValueError('validated XNYS calendar missing: '+str(calendar.get('error')))
    if main.index.max()>sessions.max() or (comp is not None and comp.index.max()>sessions.max()):
        raise ValueError('unclosed/future sessions in source')
    data=diagnose_episodes(main,sessions,published_c_dates(reference_csv),source,main_sha,
                           comp,comparison_source,comp_sha)
    data['reference_sha256']=hashlib.sha256(Path(reference_csv).read_bytes()).hexdigest()
    data['as_of_utc']=stamp.isoformat()
    out.mkdir(parents=True)
    (out/'episode_audit.json').write_text(json.dumps({k:v for k,v in data.items() if k!='rows'},indent=2,ensure_ascii=False))
    with (out/'episode_daily_windows.csv').open('w',newline='') as handle:
        fields=['case_date','observation_date','advances','declines','unchanged',
                'breadth_ratio','over_70','eligible_days_in_last_10',
                'is_reference_printed_date','is_focus_candidate']
        writer=csv.DictWriter(handle,fieldnames=fields)
        writer.writeheader()
        writer.writerows(data['rows'])
    lines=['# MBSS C — three unexplained episode audit',
           '',
           '**UNVERIFIED • OBSERVE_ONLY • SAFE_TO_ACT=False**','',
           'Source: '+source,'','SHA256: '+main_sha,
           '', '| Candidate | Case status | Last 10 >70% days | Prior Carson date | Market-session gap | Comparison |',
           '|---|---|---:|---|---:|---|']
    for c in data['focus_cases']:
        lines.append('| '+c['date']+' | '+c['status']+' | '+str(c['strict_70_days_last_10'])+
                     ' | '+str(c['preceding_carson_printed_date'])+
                     ' | '+str(c['trading_sessions_since_preceding_printed_date'])+
                     ' | '+c['alternative_provider_comparison']['status']+' |')
    lines+=['','The 10- and 63-session cooldowns are exploratory; Carson/NDR suppression rules remain unknown.',
            'Absent observations do not imply zero breadth, a missing signal, or a failed published event.',
            'This report does not authorize trading or alter the MBSS signal engine.','']
    (out/'episode_audit.md').write_text('\n'.join(lines))
    return data
