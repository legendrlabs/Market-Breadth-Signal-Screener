"""Research-only Carson/NDR C date reconciliation; no trading or signal promotion.

Never fit cooldown/denominator rules to the published eight outcomes. Every
variant is named as a researcher hypothesis, not a Carson/NDR definition.
"""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from mbss.collectors.calendar import as_utc, market_sessions
from mbss.indicators.core import breadth_ratio

CARSON_ARTICLE = 'https://www.carsongroup.com/insights/blog/houston-we-have-a-zweig-breadth-thrust-and-four-more-bullish-developments/'
PUBLICATION_DATE = pd.Timestamp('2025-04-25')
DEFAULT_VARIANTS = (
    ('MBSS_PRIMARY_STRICT70_COOLDOWN10', False, 10, False),
    ('STRICT70_FIRST_EDGE_NO_COOLDOWN', False, 0, False),
    ('STRICT70_RESEARCH_COOLDOWN63', False, 63, False),
    ('INCLUSIVE70_RESEARCH_COOLDOWN10', True, 10, False),
    ('UNCHANGED_DENOMINATOR_RESEARCH_COOLDOWN10', False, 10, True),
)


def _ratio(frame, include_unchanged=False):
    fields=['advances','declines']+(['unchanged'] if include_unchanged else [])
    if any(col not in frame for col in fields):
        return None
    values=frame[fields].apply(pd.to_numeric,errors='coerce')
    valid=values.notna().all(axis=1)&np.isfinite(values).all(axis=1)
    valid &= values.ge(0).all(axis=1)&(values%1).eq(0).all(axis=1)
    denom=values.sum(axis=1)
    valid &= denom.gt(0)
    return (values.advances/denom).where(valid)


def _c_events(ratio, inclusive=False, cooldown=10):
    """Research hypothesis: 6/10 + rising threshold edge + fixed cooldown."""
    if cooldown < 0:raise ValueError('negative cooldown')
    active=(ratio.ge(.70) if inclusive else ratio.gt(.70)).astype(float)
    active=active.where(ratio.notna()).rolling(10,min_periods=10).sum()
    results=[]
    prev=False
    last=-10**12
    for i,(date,value) in enumerate(active.items()):
        current=bool(pd.notna(value) and value>=6)
        if current and not prev and i-last>cooldown:
            results.append(pd.Timestamp(date))
            last=i
        prev=current
    return results


def _canonical_date(raw):
    if not isinstance(raw,str):
        raise ValueError('reference date must be an ISO date string')
    date=pd.Timestamp(raw)
    if str(date.date())!=raw or date.tzinfo is not None:
        raise ValueError('reference date not canonical YYYY-MM-DD')
    return date


def published_c_dates(reference_file):
    """Read printed Carson table exactly; no recomputed or inferred event dates."""
    rows=list(csv.DictReader(Path(reference_file).open(encoding='utf-8-sig',newline='')))
    if not rows or 'signal' not in rows[0] or 'date_as_printed' not in rows[0]:
        raise ValueError('source table missing signal/date columns')
    dates=[_canonical_date(row['date_as_printed']) for row in rows if row['signal']=='C']
    if not dates or len(set(dates))!=len(dates):
        raise ValueError('C reference dates unavailable or duplicated')
    if any(x>PUBLICATION_DATE for x in dates):
        raise ValueError('reference event after publication')
    return sorted(dates)


def reconcile_c(frame,sessions,reference_dates,source_label,source_sha256,
                compare_until=PUBLICATION_DATE):
    """Compare date lists only for *complete* rolling windows.

    Coverage and candidate event comparisons are not evidence of a matched
    issue universe. Must remain independent of MBSS's approved signal list.
    """
    if not source_label or not isinstance(source_label,str):
        raise ValueError('source label required')
    if not isinstance(source_sha256,str) or len(source_sha256)!=64:
        raise ValueError('source SHA256 required')
    if frame.empty or not {'advances','declines'}.issubset(frame.columns):
        raise ValueError('research A/D file empty or missing required fields')
    if not isinstance(frame.index,pd.DatetimeIndex) or frame.index.hasnans or frame.index.has_duplicates:
        raise ValueError('research file has duplicate/invalid dates')
    if not frame.index.is_monotonic_increasing:
        raise ValueError('research dates are not sorted')
    if frame.index.tz is not None:
        raise ValueError('research dates need timezone-naive sessions')
    idx=pd.DatetimeIndex(sessions)
    if idx.empty or idx.has_duplicates or not idx.is_monotonic_increasing:
        raise ValueError('completed NYSE calendar unavailable')
    # Calendar floor in MBSS is 1970: never silently compare older 1962 dates.
    pre_floor=int((frame.index<idx.min()).sum())
    non_session=frame.index[(frame.index>=idx.min()) & (~frame.index.isin(idx))]
    if len(non_session):
        # Observation dates from raw sources often include non-session rows.
        # Keep original in raw file; do not feed them into the signal study.
        outside=[str(d.date()) for d in non_session]
    else:
        outside=[]
    data=frame.reindex(idx)
    ratio=_ratio(data)
    good=ratio.notna().astype(int)
    # Eleven valid sessions establish the prior 10-day expansion state too;
    # otherwise a first-edge event is not provably a new state transition.
    complete11=good.rolling(11,min_periods=11).sum().eq(11)
    published=set(reference_dates)
    cutoff=pd.Timestamp(compare_until)
    reference_rows=[]
    for date in reference_dates:
        if date<idx.min():
            flag='OUTSIDE_VALIDATED_CALENDAR_OR_DATA'
        elif date>idx[-1]:
            flag='AFTER_DATA_WINDOW'
        elif date not in idx or not bool(complete11.loc[date]):
            flag='INCOMPLETE_11_SESSION_CONTEXT'
        else:
            flag='OBSERVABLE_DATE'
        reference_rows.append({'date':str(date.date()),'coverage':flag})
    variants=[]
    all_candidates=[]
    for label,inclusive,cooldown,unchanged in DEFAULT_VARIANTS:
        denom_ratio=_ratio(data,include_unchanged=unchanged)
        if denom_ratio is None:
            variants.append({'variant':label,'status':'UNCHANGED_COUNTS_UNAVAILABLE',
                             'matched':None,'extras':None,'missed':None})
            continue
        complete=denom_ratio.notna().astype(int).rolling(11,min_periods=11).sum().eq(11)
        candidates=_c_events(denom_ratio,inclusive,cooldown)
        reliable={date for date in candidates if complete.loc[date] and date<=cutoff}
        uncertain=[str(date.date()) for date in candidates if not complete.loc[date]]
        comparable_ref={date for date in published if date in complete.index and complete.loc[date]}
        matched=sorted(reliable & comparable_ref)
        extras=sorted(reliable - published)
        missed=sorted(comparable_ref - reliable)
        row={'variant':label,'status':'RESEARCH_SENSITIVITY_ONLY',
             'threshold':'>=0.70' if inclusive else '>0.70',
             'eligible_days_in_10':6, 'edge':'first_rising_edge',
             'cooldown_sessions':cooldown,'denominator':'A+D+UNCHANGED' if unchanged else 'A+D',
             'comparable_reference_dates':len(comparable_ref),
             'matched':[str(d.date()) for d in matched],
             'extras':[str(d.date()) for d in extras],
             'missed':[str(d.date()) for d in missed],
             'candidate_dates':[str(d.date()) for d in sorted(reliable)],
             'left_edge_uncertain':uncertain}
        variants.append(row)
        if label=='MBSS_PRIMARY_STRICT70_COOLDOWN10':
            for date in sorted(reliable):
                all_candidates.append({'date':str(date.date()),
                                       'status':'MATCHED_PRINTED_DATE' if date in published else 'EXTRA_UNEXPLAINED',
                                       'eligible_for_signal':False})
    primary=variants[0]
    comparable=primary.get('comparable_reference_dates') or 0
    status='PARTIAL_REFERENCE_DATE_RECONCILIATION_UNVERIFIED' if comparable else 'INSUFFICIENT_REFERENCE_COVERAGE'
    return {'status':status,'source_label':source_label,'source_sha256':source_sha256,
            'published_reference':CARSON_ARTICLE, 'published_at':'2025-04-25',
            'universe_comparability':'UNVERIFIED','suppression_policy':'UNVERIFIED',
            'source_can_substitute_for_NDR':False,'eligible_for_signal':False,'safe_to_act':False,
            'calendar_start':str(idx.min().date()),'calendar_end':str(idx.max().date()),
            'raw_rows_before_calendar_floor':pre_floor,
            'non_session_rows_excluded':outside,
            'validated_observations':int(good.sum()),
            'reference_dates':reference_rows,'variants':variants,'primary_candidates':all_candidates,
            'warnings':['Sample limited by caller source and 1970 NYSE calendar coverage.',
                        'A published date list does not define its cooldown, threshold equality, or denominator.',
                        'Do not select a variant based on maximum agreement with 8 mature Carson cases.',
                        'Zero matched observations in an incomplete historical window is not failed replication.']}


def run_c_audit(input_csv,reference_csv,output_dir,source,as_of):
    """Standalone opt-in research command; immutable outputs; no MBSS run writes."""
    input_csv,reference_csv,out=Path(input_csv),Path(reference_csv),Path(output_dir)
    if out.exists():raise FileExistsError('Use a new immutable audit output path')
    input_bytes=input_csv.read_bytes()
    frame=pd.read_csv(input_csv,dtype={'date':'string'})
    if 'date' not in frame:
        raise ValueError('research input must have date column')
    raw_dates=frame.pop('date').tolist()
    if any(not isinstance(s,str) or len(s)!=10 for s in raw_dates):
        raise ValueError('invalid research input dates')
    index=pd.to_datetime(raw_dates,format='%Y-%m-%d',errors='raise')
    frame.index=pd.DatetimeIndex(index,name='date')
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError('research dates duplicated or unordered')
    refs=published_c_dates(reference_csv)
    stamped=as_utc(as_of)
    sessions,cal=market_sessions(max(frame.index.min(),pd.Timestamp('1970-01-01')),
                                 stamped)
    if not cal.get('valid') or sessions.empty:
        raise ValueError('validated NYSE calendar unavailable: '+str(cal.get('error')))
    if frame.index.max()>sessions.max():
        raise ValueError('future or unclosed observations in historical research CSV')
    audit=reconcile_c(frame,sessions,refs,source,hashlib.sha256(input_bytes).hexdigest())
    audit['reference_sha256']=hashlib.sha256(reference_csv.read_bytes()).hexdigest()
    audit['as_of_utc']=stamped.isoformat()
    out.mkdir(parents=True)
    (out/'c_reconciliation.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
    with (out/'c_candidates.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=['date','status','eligible_for_signal'])
        writer.writeheader()
        writer.writerows(audit['primary_candidates'])
    return audit
