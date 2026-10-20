"""External intraday observations remain separate from every signal input."""
import json
import math
import numbers
from pathlib import Path
import pandas as pd


def finite_number(value):
    try:return not isinstance(value,bool) and isinstance(value,numbers.Real) and math.isfinite(value)
    except (ValueError,TypeError,OverflowError):return False


def external_context(directory,as_of):
    path=Path(directory)/'external_context.json'
    result={'status':'REFERENCE_ONLY','eligible_for_signal':False,'observations':[],'errors':[]}
    if not path.exists():return result
    try:
        rows=json.loads(path.read_text())
        if not isinstance(rows,list):raise ValueError('external_context must be a list')
    except (ValueError,OSError) as exc:
        result.update(status='UNVERIFIED',errors=['EXTERNAL_CONTEXT_LOAD_FAILED: '+str(exc)]);return result
    for row in rows:
        if not isinstance(row,dict):
            result['observations'].append({'original_value':row,'eligible_for_signal':False,'status':'UNVERIFIED','flags':['INVALID_RECORD']});continue
        flags=[]
        if row.get("value") is None:flags.append("MISSING_VALUE")
        elif not finite_number(row["value"]):
            flags.append("INVALID_VALUE");row={**row,"value":None}
        for key in ['metric','universe','source','session_type','retrieval_timestamp']:
            if not row.get(key):flags.append('MISSING_'+key.upper())
        for key in ['observed_at','retrieval_timestamp']:
            value=row.get(key)
            if not value:
                flags.append('OBSERVATION_TIME_UNKNOWN' if key=='observed_at' else 'RETRIEVAL_TIME_UNKNOWN');continue
            try:
                stamp=pd.Timestamp(value)
                if pd.isna(stamp) or stamp.tzinfo is None:raise ValueError('timezone required')
                if stamp.tz_convert('UTC')>as_of:flags.append('FUTURE_'+key.upper())
            except (ValueError,TypeError):flags.append('INVALID_'+key.upper())
        result['observations'].append({**row,'eligible_for_signal':False,'status':'UNVERIFIED' if flags else 'REFERENCE_ONLY','flags':sorted(set(flags))})
    return result
