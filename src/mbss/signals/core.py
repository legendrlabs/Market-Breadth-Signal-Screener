from itertools import combinations
import numpy as np
import pandas as pd
from mbss.models import Event
from mbss.indicators.core import strong_streak, expansion_count


def zbt_events(smoothed, inclusive=False, max_distance=10):
    events, setup = [], None
    if max_distance < 1: raise ValueError('max_distance must be positive')
    for i,(date,value) in enumerate(smoothed.items()):
        if not np.isfinite(value):
            setup = None
            continue
        low = value <= .4 if inclusive else value < .4
        high = value >= .615 if inclusive else value > .615
        if low: setup = i
        if high and setup is not None and 1 <= i-setup <= max_distance:
            events.append(Event('A',date,definition='inclusive' if inclusive else 'strict'))
            setup = None
        if setup is not None and i-setup > max_distance: setup = None
    return events


def rally_events(close):
    return [Event('B',date) for date,streak in strong_streak(close).items() if streak == 3]


def expansion_events(ratio, cooldown=10):
    out, previous, last = [], False, -10**9
    for i,(date,value) in enumerate(expansion_count(ratio).items()):
        current = np.isfinite(value) and value >= 6
        if current and not previous and i-last > cooldown:
            out.append(Event('C',date)); last = i
        previous = current
    return out


def election_date(year):
    first = pd.Timestamp(year=year,month=11,day=1)
    return first + pd.Timedelta(days=(0-first.weekday())%7+1)


def election_events(sessions, as_of, first_year=1974):
    """Election day is the information date; entry is strictly after that day."""
    out = []
    if len(sessions)==0: return out
    for year in range(first_year,as_of.year+1):
        if year%4 != 2: continue
        day=election_date(year)
        if day <= as_of and sessions[0] <= day <= sessions[-1]: out.append(Event('D',day))
    return out


def combine_events(events,sessions,required,window,cooldown=10):
    positions={d:i for i,d in enumerate(sessions)}
    grouped={}
    for e in events:
        if e.signal in required and e.date in positions:
            grouped.setdefault(e.date,set()).add(e.signal)
    latest, out, was_active, last = {}, [], False, -10**9
    for date,i in positions.items():
        for signal in grouped.get(date,()): latest[signal]=i
        active = all(s in latest and i-latest[s] <= window for s in required)
        if active and not was_active and grouped.get(date) and i-last>cooldown:
            out.append(Event('+'.join(required)+f'@{window}',date,tuple(required)))
            last=i
        was_active=active
    return out


def all_combinations(events,sessions):
    out=[]
    for n in (2,3):
        for required in combinations(('A','B','C'),n):
            for window in (5,10): out += combine_events(events,sessions,required,window)
    elections=[e.date for e in events if e.signal=='D']
    for e in events:
        if e.signal in ('A','B','C') and any(d < e.date <= d+pd.DateOffset(months=6) for d in elections):
            out.append(Event('D+'+e.signal,e.date,('D',e.signal)))
    return sorted(out,key=lambda e:(e.date,e.signal))
