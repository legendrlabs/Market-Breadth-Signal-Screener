"""Recover true Cboe VIX calendar gaps using observed FRED VIXCLS values.

FRED republishes Cboe-derived observations; this is not an independent
producer. No forward fill, interpolation, zeros, synthetic close or
unreviewed replacement of an existing Cboe observation is permitted.
"""
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
import math
import os
import re
import uuid

import pandas as pd

from mbss.collectors.calendar import market_sessions

CBOE_URL = 'https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv'
FRED_GRAPH_URL = 'https://fred.stlouisfed.org/graph/fredgraph.csv'
FRED_TABLE_URL = 'https://fred.stlouisfed.org/data/VIXCLS'
FRED_SERIES_URL = 'https://fred.stlouisfed.org/series/VIXCLS'


def parse_fred_vixcls(body):
    """Read FRED date/value CSV; keep missing '.' as missing, never zero."""
    if not isinstance(body, bytes) or not body:
        raise ValueError('empty FRED VIXCLS response')
    frame = pd.read_csv(BytesIO(body), dtype=str, keep_default_na=False)
    frame.columns = [col.strip() for col in frame.columns]
    date_column = next((c for c in ('observation_date', 'DATE') if c in frame), None)
    if date_column is None or 'VIXCLS' not in frame:
        raise ValueError('FRED CSV requires observation_date/DATE and VIXCLS columns')
    if frame[date_column].duplicated().any():
        raise ValueError('duplicate FRED observation dates')
    if not frame[date_column].map(lambda x: bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', x))).all():
        raise ValueError('invalid FRED observation date shape')
    dates = pd.to_datetime(frame[date_column], format='%Y-%m-%d', errors='raise')
    return pd.Series(frame['VIXCLS'].tolist(), index=pd.DatetimeIndex(dates), name='VIXCLS').sort_index()



class _FREDVisibleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.visible = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script','style','noscript'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('script','style','noscript') and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.visible.append(data)


def parse_fred_vixcls_table(body):
    """Fallback parser for FRED's server-rendered public VIXCLS data table."""
    if not isinstance(body, bytes) or not body:
        raise ValueError('empty FRED table response')
    parser = _FREDVisibleHTML()
    parser.feed(body.decode('utf-8', errors='replace'))
    text = ' '.join(parser.visible)
    if (not re.search(r'\bSeries\s+ID\s+VIXCLS\b', text, re.I)
            or not re.search(r'\bCBOE Volatility Index\b', text, re.I)
            or not re.search(r'\bChicago Board Options Exchange\b', text, re.I)
            or not re.search(r'\bDATE\s+VALUE\b', text, re.I)):
        raise ValueError('FRED VIXCLS issuer, series, or data-table header not verified')
    text = re.split(r'\bDATE\s+VALUE\b', text, maxsplit=1, flags=re.I)[-1]
    rows = re.findall(r'(?<!\d)(\d{4}-\d{2}-\d{2})\s*(?:\|\s*)?(\d+(?:\.\d+)?|\.)(?=\s|$)',text)
    if not rows:
        raise ValueError('FRED table has no dated close observations')
    dates = [date for date,value in rows]
    if len(set(dates)) != len(dates):
        raise ValueError('duplicate FRED table observation date')
    index = pd.to_datetime(dates, format='%Y-%m-%d',errors='raise')
    return pd.Series([value for date,value in rows],
                     index=pd.DatetimeIndex(index),name='VIXCLS').sort_index()


def _positive_real(raw):
    """No numeric inference for unavailable/malformed observations."""
    if not isinstance(raw, str) or not re.fullmatch(r'\d+(?:\.\d+)?', raw.strip()):
        return None
    value = float(raw)
    return value if math.isfinite(value) and value > 0 else None


def _snapshot(directory, snapshot):
    path = Path(directory) / 'vix_recovery.json'
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
    return path


def _csv_atomic(path, frame):
    path = Path(path)
    temp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        frame.to_csv(temp, index_label='date')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def recover_missing_vix(directory, raw_directory, metadata, start='2000-01-01',
                        timeout=8, opener=None, now=None, primary_downloaded=False):
    """Patch only XNYS sessions absent from a freshly downloaded Cboe VIX file.

    Caller persists modified metadata only after this function returns.
    Input raw Cboe bytes and FRED bytes remain separate and immutable.
    """
    directory, raw_directory = Path(directory), Path(raw_directory)
    stamp = pd.Timestamp(now if now is not None else datetime.now(timezone.utc))
    if stamp.tzinfo is None:
        raise ValueError('recovery timestamp must be timezone-aware')
    snapshot = {'status': 'NOT_ATTEMPTED', 'primary_source': CBOE_URL,
                'secondary_source': FRED_SERIES_URL, 'independent_provider': False,
                'method': 'observed_values_only; no imputation; Cboe-origin secondary publication',
                'as_of_utc': stamp.isoformat(), 'requested_start': str(start),
                'identified_missing_xnys_dates': [], 'recovered': [],
                'unresolved_xnys_dates': [], 'raw_sha256': None, 'raw_file': None,
                'download_url': None, 'eligible_for_signal': False, 'errors': []}
    attempt = {'dataset': 'vix_observed_recovery', 'source': FRED_SERIES_URL,
               'retrieval_timestamp': stamp.isoformat(), 'status': 'NOT_ATTEMPTED'}
    def finish(status, error=None):
        snapshot['status'] = status
        attempt['status'] = status
        if error is not None:
            snapshot['errors'].append(error)
            attempt['error'] = error
        attempt['identified_missing_xnys_dates'] = snapshot['identified_missing_xnys_dates']
        attempt['recovered_dates'] = [r['date'] for r in snapshot['recovered']]
        attempt['raw_sha256'] = snapshot['raw_sha256']
        _snapshot(directory, snapshot)
        return attempt

    if not primary_downloaded or metadata.get('vix', {}).get('source') != CBOE_URL:
        return finish('PRIMARY_CBOE_NOT_VERIFIED')
    file = directory / 'vix.csv'
    if not file.is_file():
        return finish('PRIMARY_CBOE_NOT_VERIFIED')
    try:
        frame = pd.read_csv(file, parse_dates=['date']).set_index('date').sort_index()
        if frame.empty or 'close' not in frame or frame.index.has_duplicates:
            return finish('PRIMARY_CBOE_INVALID')
        if not pd.api.types.is_datetime64_any_dtype(frame.index):
            return finish('PRIMARY_CBOE_INVALID')
        if not pd.to_numeric(frame.close, errors='coerce').map(
                lambda x: pd.notna(x) and math.isfinite(x) and x > 0).all():
            return finish('PRIMARY_CBOE_INVALID')
    except (OSError, ValueError, KeyError) as exc:
        return finish('PRIMARY_CBOE_INVALID', type(exc).__name__ + ': ' + str(exc))

    start_date = pd.Timestamp(start).normalize() - pd.Timedelta(days=365)
    sessions, calendar = market_sessions(start_date, stamp)
    if not calendar.get('valid') or sessions.empty:
        return finish('CALENDAR_UNAVAILABLE', calendar.get('error'))
    active = sessions[(sessions >= frame.index.min()) & (sessions <= frame.index.max())]
    gaps = active.difference(frame.index)
    snapshot['identified_missing_xnys_dates'] = [d.strftime('%Y-%m-%d') for d in gaps]
    if not len(gaps):
        return finish('NO_MISSING_XNYS_SESSIONS')
    if len(gaps) > 20:
        snapshot['unresolved_xnys_dates'] = snapshot['identified_missing_xnys_dates']
        return finish('TOO_MANY_GAPS_FOR_AUTOMATIC_REPAIR')

    params = urlencode({'id': 'VIXCLS',
                        'cosd': gaps.min().strftime('%Y-%m-%d'),
                        'coed': gaps.max().strftime('%Y-%m-%d')})
    url = FRED_GRAPH_URL + '?' + params
    snapshot['download_url'] = url
    snapshot['download_attempts'] = []
    observations = None
    any_parsed = False
    raw_directory.mkdir(parents=True, exist_ok=True)
    for source_url, parser, filename in (
        (url, parse_fred_vixcls, 'fred_vixcls.csv'),
        (FRED_TABLE_URL, parse_fred_vixcls_table, 'fred_vixcls_table.html'),
    ):
        source_attempt = {'url': source_url, 'status': 'PENDING', 'raw_sha256': None}
        snapshot['download_attempts'].append(source_attempt)
        try:
            request = Request(source_url, headers={'User-Agent':'MBSS/0.1.3 observational VIX research'})
            with (opener or urlopen)(request, timeout=timeout) as response:
                body = response.read(5_000_000)
            raw_file = raw_directory / filename
            raw_file.write_bytes(body)
            digest = sha256(body).hexdigest()
            source_attempt.update(raw_file=str(raw_file),raw_sha256=digest)
            candidate = parser(body)
            any_parsed = True
            if any(day not in candidate.index or _positive_real(candidate.loc[day]) is None for day in gaps):
                source_attempt.update(status='OBSERVED_DATES_INCOMPLETE')
                continue
            observations = candidate
            source_attempt['status'] = 'OBSERVATIONS_COMPLETE'
            snapshot['download_url'] = source_url
            snapshot['raw_file'] = str(raw_file)
            snapshot['raw_sha256'] = digest
            break
        except Exception as exc:
            source_attempt.update(status='FETCH_OR_PARSE_FAILED',
                                  error=type(exc).__name__+': '+str(exc))
    if observations is None:
        snapshot['unresolved_xnys_dates'] = snapshot['identified_missing_xnys_dates']
        errors = [a.get('error',a['status']) for a in snapshot['download_attempts']]
        return finish('FRED_OBSERVATIONS_INCOMPLETE' if any_parsed else 'FRED_DOWNLOAD_OR_PARSE_FAILED',
                      '; '.join(errors))

    recovered = []
    unresolved = []
    for date in gaps:
        date_string = date.strftime('%Y-%m-%d')
        value = _positive_real(observations.loc[date]) if date in observations.index else None
        if value is None:
            unresolved.append(date_string)
            continue
        recovered.append({'date': date_string, 'close': value, 'source': FRED_SERIES_URL,
                          'retrieval_timestamp': stamp.isoformat(),
                          'source_raw_sha256': snapshot['raw_sha256'],
                          'origin': 'Cboe VIX (FRED redistribution)',
                          'independent_confirmation': False})
    snapshot['unresolved_xnys_dates'] = unresolved
    if unresolved:
        # Fail atomic: never partially fill if any expected session lacks an
        # actual FRED observation; original Cboe CSV and metadata remain intact.
        return finish('FRED_OBSERVATIONS_INCOMPLETE')

    additions = pd.DataFrame({'close': [x['close'] for x in recovered]},
                             index=pd.DatetimeIndex([x['date'] for x in recovered], name='date'))
    merged = pd.concat([frame, additions]).sort_index()
    if merged.index.has_duplicates or merged.index.difference(frame.index).difference(gaps).size:
        return finish('MERGE_VALIDATION_FAILED')
    original_meta = dict(metadata['vix'])
    supplemental = {x['date']: x for x in recovered}
    original_meta['adjustment_method'] = 'Cboe close; identified XNYS gaps supplied by FRED VIXCLS observed closes, not imputed'
    original_meta['supplemental_observations'] = supplemental
    original_meta['secondary_source'] = FRED_SERIES_URL
    original_meta['secondary_source_is_independent'] = False
    original_meta['secondary_raw_sha256'] = snapshot['raw_sha256']
    _csv_atomic(file, merged)
    metadata['vix'] = original_meta
    snapshot['recovered'] = recovered
    return finish('RECOVERED_OBSERVED_FRED_CBOE_REPUBLICATION')
