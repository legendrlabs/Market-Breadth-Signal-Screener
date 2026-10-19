"""XNYS sessions and completed close cutoff; never substitute weekdays."""
import pandas as pd


def as_utc(value):
    stamp=pd.Timestamp(value)
    if stamp.tzinfo is None:raise ValueError('as-of requires an explicit timezone, e.g. 2026-10-19T08:57:00Z')
    return stamp.tz_convert('UTC')


def market_sessions(start,as_of):
    stamp=as_utc(as_of)
    requested_start=pd.Timestamp(start)
    # Earlier historical holiday rules require a separately validated calendar.
    # Observed 1950–1969 price/calendar discrepancies must not become fake gaps
    # or compressed sessions. Record an explicit coverage floor instead.
    start=max(requested_start,pd.Timestamp('1970-01-01'))
    try:
        import exchange_calendars as xcals
    except ImportError:
        return pd.DatetimeIndex([]),{'valid':False,'source':'exchange_calendars XNYS','error':'DEPENDENCY_MISSING: exchange-calendars; no weekday fallback'}
    try:
        calendar=xcals.get_calendar('XNYS',start=pd.Timestamp(start)-pd.Timedelta(days=20),end=stamp.tz_localize(None).normalize()+pd.Timedelta(days=10))
        schedule=calendar.schedule
        close_col='close' if 'close' in schedule else 'market_close'
        closes=pd.to_datetime(schedule[close_col],utc=True)
        completed=schedule.index[(closes<=stamp).to_numpy()]
        completed=pd.DatetimeIndex(completed).tz_localize(None).normalize()
        completed=completed[completed>=pd.Timestamp(start)]
        return completed,{'valid':True,'source':'exchange_calendars XNYS','package_version':xcals.__version__,
                          'definition':'Completed official-schedule session closes, including early closes',
                          'official_reference':'https://www.nyse.com/trade/hours-calendars',
                          'requested_calendar_start':str(requested_start.date()),'effective_calendar_start':str(start.date()),
                          'coverage_note':'Before 1970 historical holiday rules not validated; earlier years excluded explicitly',
                          'expected_last':str(completed[-1].date()) if len(completed) else None}
    except Exception as exc:
        return pd.DatetimeIndex([]),{'valid':False,'source':'exchange_calendars XNYS','error':type(exc).__name__+': '+str(exc)}
