"""Optional same-publisher audit of the public McClellan daily table vs its XLS.

This is NOT independent WSJ verification or NDR comparability, and never
changes NYSE A/C inputs, event selection, or risk permissions.
"""
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
import json
import re
import pandas as pd

PAGE_URL = 'https://www.mcoscillator.com/market_breadth_data/'
XLS_URL = 'https://www.mcoscillator.com/data/osc_data/OSC-DATA.xls'


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self.hidden += 1
        if tag in ('tr', 'td', 'th', 'h1', 'h2', 'h3', 'p', 'br'):
            self.parts.append(' ')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript') and self.hidden:
            self.hidden -= 1
        if tag in ('tr', 'td', 'th', 'h1', 'h2', 'h3', 'p', 'br'):
            self.parts.append(' ')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def parse_mcclellan_page(body):
    """Extract the displayed NYSE Issues A/D only; never oscillator/volume."""
    if not isinstance(body, bytes) or not body:
        raise ValueError('empty HTML body')
    parser = _VisibleText()
    parser.feed(body.decode('utf-8', errors='replace'))
    visible = re.sub(r'\s+', ' ', ' '.join(parser.parts))
    header = re.search(r'\bNYSE\s*:\s*(\d{1,2}/\d{1,2}/\d{4})\b', visible, re.I)
    if not header:
        raise ValueError('dated NYSE table not found')
    date = pd.to_datetime(header.group(1), format='%m/%d/%Y', errors='raise')
    # Bound to table text, rather than matching a narrative article or another market.
    section = visible[header.end():header.end()+1700]
    # Published site: "Advances [issues] [volume]" and "Declines [issues] [volume]".
    values = {}
    for label in ('Advances', 'Declines', 'Difference'):
        match = re.search(r'\b' + label + r'\s+(-?\d[\d,]*)\b', section, re.I)
        if not match:
            raise ValueError('NYSE Issues ' + label + ' missing')
        values[label.lower()] = int(match.group(1).replace(',', ''))
    if values['advances'] < 0 or values['declines'] < 0 or values['advances'] + values['declines'] <= 0:
        raise ValueError('invalid NYSE issue counts')
    if values['advances'] - values['declines'] != values['difference']:
        raise ValueError('published difference does not match issue counts')
    return {'date': str(date.date()), 'advances': values['advances'],
            'declines': values['declines'], 'difference': values['difference']}


def collect_publisher_page(destination, raw_dir, timeout=8, opener=None):
    """Archive raw page and write a new fail-closed snapshot on every attempt."""
    destination, raw_dir = Path(destination), Path(raw_dir)
    destination.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    retrieved = datetime.now(timezone.utc).isoformat()
    snapshot = {'status': 'SOURCE_UNAVAILABLE', 'source': PAGE_URL,
                'retrieval_timestamp': retrieved, 'eligible_for_signal': False,
                'independent_source': False, 'ndr_comparability_validated': False,
                'date': None, 'advances': None, 'declines': None,
                'difference': None, 'raw_sha256': None, 'raw_file': None}
    attempt = {'dataset': 'mcclellan_publisher_page', 'source': PAGE_URL,
               'retrieval_timestamp': retrieved}
    try:
        request = Request(PAGE_URL, headers={'User-Agent': 'MBSS/0.1.3 research publisher cross-check'})
        with (opener or urlopen)(request, timeout=timeout) as response:
            body = response.read(2_000_000)
        raw_file = raw_dir / 'mcclellan_publisher_page.html'
        raw_file.write_bytes(body)
        checksum = sha256(body).hexdigest()
        snapshot.update(raw_sha256=checksum, raw_file=str(raw_file))
        attempt.update(raw_sha256=checksum, raw_file=str(raw_file))
        values = parse_mcclellan_page(body)
        snapshot.update(values, status='DOWNLOADED_REFERENCE_ONLY')
        attempt.update(status='DOWNLOADED_REFERENCE_ONLY', **values)
    except Exception as exc:
        snapshot['status'] = 'SOURCE_UNAVAILABLE_OR_PARSE_FAILED'
        attempt.update(status='FAILED', error=type(exc).__name__ + ': ' + str(exc))
        snapshot['error'] = attempt['error']
    # Failed collection replaces old snapshot; no successful stale snapshot reuse.
    (destination / 'publisher_page_snapshot.json').write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2))
    return attempt


def audit_publisher_page(input_dir, breadth, meta, sessions, as_of):
    """Compare dated publisher-page A/D with XLS if both are present and proven."""
    result = {'status': 'NO_PUBLISHER_PAGE', 'source': PAGE_URL,
              'xls_source': meta.get('source'), 'publisher_date': None,
              'expected_last_session': str(sessions[-1].date()) if len(sessions) else None,
              'advances': None, 'declines': None, 'xls_advances': None,
              'xls_declines': None, 'delta_advances': None, 'delta_declines': None,
              'raw_sha256': None, 'flags': [], 'eligible_for_signal': False,
              'independent_source': False, 'wsj_independently_verified': False,
              'ndr_comparability_validated': False, 'safe_to_act': False}
    file = Path(input_dir) / 'publisher_page_snapshot.json'
    if not file.exists():
        return result
    try:
        s = json.loads(file.read_text())
        if not isinstance(s, dict):
            raise ValueError('snapshot not a JSON object')
    except (ValueError, OSError, UnicodeError) as exc:
        result.update(status='INVALID_PUBLISHER_SNAPSHOT', flags=['INVALID_SNAPSHOT:' + type(exc).__name__])
        return result
    result.update(publisher_date=s.get('date'), advances=s.get('advances'),
                  declines=s.get('declines'), raw_sha256=s.get('raw_sha256'))
    if s.get('status') != 'DOWNLOADED_REFERENCE_ONLY':
        result['flags'].append('PUBLISHER_DOWNLOAD_OR_PARSE_FAILED')
    if s.get('source') != PAGE_URL:
        result['flags'].append('UNRECOGNIZED_PUBLISHER_SOURCE')
    stamp = s.get('retrieval_timestamp')
    try:
        observed_at = pd.Timestamp(stamp)
        if pd.isna(observed_at) or observed_at.tzinfo is None or observed_at > pd.Timestamp(as_of):
            raise ValueError('missing, naive or future timestamp')
    except (TypeError, ValueError, OverflowError):
        result['flags'].append('INVALID_OR_FUTURE_RETRIEVAL_TIMESTAMP')
    date = None
    try:
        date = pd.Timestamp(s.get('date'))
        if (not isinstance(s.get('date'), str) or str(date.date()) != s['date']
                or date.tzinfo is not None or date not in sessions):
            raise ValueError('not a completed NYSE session')
    except (TypeError, ValueError, OverflowError):
        result['flags'].append('INVALID_OR_UNCOMPLETED_SESSION_DATE')
        date = None
    for field in ('advances', 'declines'):
        value = s.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            result['flags'].append('INVALID_' + field.upper())
    if (type(s.get('advances')) is int and type(s.get('declines')) is int
            and s['advances'] >= 0 and s['declines'] >= 0):
        if s['advances'] + s['declines'] <= 0 or s.get('difference') != s['advances'] - s['declines']:
            result['flags'].append('INVALID_PUBLISHED_DIFFERENCE')
    if not isinstance(s.get('raw_sha256'), str) or not re.fullmatch('[0-9a-f]{64}', s['raw_sha256']):
        result['flags'].append('RAW_HASH_MISSING')
    if date is not None and date != sessions[-1]:
        result['flags'].append('PUBLISHER_PAGE_STALE')
    if meta.get('source') != XLS_URL:
        result['flags'].append('MCCLELLAN_XLS_SOURCE_NOT_CONFIRMED')
    if result['flags']:
        result['status'] = 'REFERENCE_NOT_COMPARABLE'
        return result
    if breadth.empty or not {'advances','declines'}.issubset(breadth) or breadth.index.has_duplicates or date not in breadth.index:
        result['status'] = 'XLS_DATE_MISSING_OR_INVALID'
        return result
    a, d = pd.to_numeric(breadth.loc[date, ['advances','declines']], errors='coerce')
    if (not pd.notna(a) or not pd.notna(d) or
            not float(a).is_integer() or not float(d).is_integer() or a < 0 or d < 0):
        result['status'] = 'XLS_DATE_MISSING_OR_INVALID'
        return result
    result.update(xls_advances=int(a), xls_declines=int(d),
                  delta_advances=s['advances']-int(a), delta_declines=s['declines']-int(d))
    result['status'] = ('COUNTS_MATCH_SAME_PUBLISHER_ONLY'
                        if result['delta_advances'] == 0 and result['delta_declines'] == 0
                        else 'COUNTS_DIFFER_SAME_PUBLISHER')
    return result
