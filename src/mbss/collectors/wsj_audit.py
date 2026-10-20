"""Compare explicitly supplied WSJ NYSE snapshots with McClellan issue counts.

Not a WSJ downloader, source authentication, NDR comparability check, or signal input.
No missing/future/preliminary observation may be synthesized or upgraded to final.
"""
import json
from pathlib import Path
import pandas as pd

WSJ_URL = 'https://www.wsj.com/market-data/stocks/marketsdiary'
MCCLELLAN_URL = 'https://www.mcoscillator.com/data/osc_data/OSC-DATA.xls'


def _timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        stamp = pd.Timestamp(value)
        return stamp if not pd.isna(stamp) and stamp.tzinfo is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def _count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def audit_wsj_reference(input_dir, breadth, metadata, sessions, as_of):
    """Return an inert, source-labeled audit. WSJ data are user-supplied, never fetched."""
    result = {
        'status': 'NO_WSJ_REFERENCE', 'source_type': 'USER_SUPPLIED_SNAPSHOT',
        'reference_source': WSJ_URL, 'mcclellan_source': metadata.get('source'),
        'same_universe_verified': False, 'ndr_comparability_validated': False,
        'eligible_for_signal': False, 'safe_to_act': False,
        'final_reference_rows': 0, 'compared_rows': 0, 'exact_matches': 0,
        'mismatches': 0, 'rows': [], 'errors': [],
    }
    path = Path(input_dir) / 'wsj_reference.json'
    if not path.exists():
        return result
    try:
        records = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(records, list):
            raise ValueError('wsj_reference must be a JSON list')
    except (OSError, ValueError, UnicodeError) as exc:
        result['status'] = 'INVALID_WSJ_REFERENCE'
        result['errors'].append(type(exc).__name__ + ': ' + str(exc))
        return result

    if metadata.get('source') != MCCLELLAN_URL:
        result['errors'].append('MCCLELLAN_SOURCE_NOT_CONFIRMED')
    if not isinstance(breadth, pd.DataFrame) or breadth.index.has_duplicates:
        result['errors'].append('MCCLELLAN_DATES_INVALID')
    valid_sessions = set(pd.DatetimeIndex(sessions))
    asof_ts = pd.Timestamp(as_of)
    if asof_ts.tzinfo is None:
        raise ValueError('as_of must have timezone')
    last_completed = max(valid_sessions) if valid_sessions else None
    parsed = []
    final_dates = set()
    duplicate_final_dates = set()
    for position, row in enumerate(records):
        audit = {'index': position, 'date': None, 'status': 'INVALID_REFERENCE',
                 'reported_stage': None, 'wsj_advances': None, 'wsj_declines': None,
                 'mcclellan_advances': None, 'mcclellan_declines': None,
                 'difference_advances': None, 'difference_declines': None,
                 'captured_at': None, 'evidence_url': None, 'flags': []}
        if not isinstance(row, dict):
            audit['flags'].append('RECORD_NOT_OBJECT')
            parsed.append(audit)
            continue
        date = row.get('date')
        audit['date'] = date
        audit['reported_stage'] = row.get('stage')
        audit['captured_at'] = row.get('captured_at')
        audit['evidence_url'] = row.get('evidence_url')
        audit['wsj_advances'] = row.get('advances')
        audit['wsj_declines'] = row.get('declines')
        try:
            parsed_date = pd.Timestamp(date)
            if (not isinstance(date, str) or
                str(parsed_date.date()) != date or parsed_date.tzinfo is not None):
                raise ValueError('not a canonical YYYY-MM-DD date')
        except (TypeError, ValueError, OverflowError):
            audit['flags'].append('INVALID_DATE')
            parsed.append(audit)
            continue
        if parsed_date not in valid_sessions or (last_completed is not None and parsed_date > last_completed):
            audit['flags'].append('NOT_COMPLETED_XNYS_SESSION')
        if row.get('source') != WSJ_URL:
            audit['flags'].append('UNRECOGNIZED_REFERENCE_SOURCE')
        if row.get('universe') != 'NYSE':
            audit['flags'].append('UNIVERSE_NOT_NYSE')
        if not (_count(row.get('advances')) and _count(row.get('declines')) and
                row['advances'] + row['declines'] > 0):
            audit['flags'].append('INVALID_COUNTS')
        captured = _timestamp(row.get('captured_at'))
        if captured is None:
            audit['flags'].append('INVALID_CAPTURE_TIMESTAMP')
        elif captured > asof_ts:
            audit['flags'].append('FUTURE_CAPTURE_TIMESTAMP')
        elif captured < parsed_date.tz_localize('America/New_York') + pd.Timedelta(hours=20):
            # WSJ overview diary may continue updating until 20:00 US/Eastern.
            # This is a conservative timing gate, not proof of provider finality.
            audit['flags'].append('CAPTURE_BEFORE_WSJ_FINAL_WINDOW')
        evidence = row.get('evidence_url')
        if not isinstance(evidence, str) or not evidence.startswith(('https://','http://')):
            audit['flags'].append('EVIDENCE_MISSING')
        if row.get('stage') != 'FINAL':
            audit['status'] = 'PRELIMINARY_OR_UNKNOWN_STAGE'
            audit['flags'].append('NOT_FINAL_REPORTED')
        else:
            if parsed_date in final_dates:
                duplicate_final_dates.add(parsed_date)
            final_dates.add(parsed_date)
        parsed.append(audit)

    for audit in parsed:
        if audit['date'] is None or audit['reported_stage'] != 'FINAL':
            continue
        try:
            date = pd.Timestamp(audit['date'])
        except (TypeError, ValueError, OverflowError):
            continue
        if date in duplicate_final_dates:
            audit['flags'].append('DUPLICATE_FINAL_DATE')
        if audit['flags']:
            continue
        result['final_reference_rows'] += 1
        if result['errors'] or breadth.empty or not {'advances','declines'}.issubset(breadth):
            audit['status'] = 'MCCLELLAN_SOURCE_UNAVAILABLE'
            continue
        if date not in breadth.index:
            audit['status'] = 'MCCLELLAN_DATE_MISSING'
            continue
        row = breadth.loc[date]
        a, d = row['advances'], row['declines']
        if (pd.isna(a) or pd.isna(d) or not pd.api.types.is_number(a) or
            not pd.api.types.is_number(d) or
            not float(a).is_integer() or not float(d).is_integer() or
            a < 0 or d < 0 or a + d <= 0):
            audit['status'] = 'INVALID_MCCLELLAN_COUNTS'
            continue
        a, d = int(a), int(d)
        audit['mcclellan_advances'] = a
        audit['mcclellan_declines'] = d
        audit['difference_advances'] = audit['wsj_advances'] - a
        audit['difference_declines'] = audit['wsj_declines'] - d
        matched = audit['difference_advances'] == 0 and audit['difference_declines'] == 0
        audit['status'] = 'COUNTS_MATCH_REFERENCE_ONLY' if matched else 'COUNTS_DIFFER'
        result['compared_rows'] += 1
        result['exact_matches' if matched else 'mismatches'] += 1

    result['rows'] = parsed
    if result['errors'] or any('DUPLICATE_FINAL_DATE' in row['flags'] for row in parsed):
        result['status'] = 'REVIEW_REQUIRED'
    elif result['mismatches']:
        result['status'] = 'MISMATCH_OBSERVED'
    elif result['compared_rows']:
        result['status'] = 'COUNTS_MATCH_REFERENCE_ONLY'
    else:
        result['status'] = 'NO_COMPARABLE_ROWS'
    return result
