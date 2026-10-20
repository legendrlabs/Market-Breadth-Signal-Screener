"""Current SPY traded-holdings breadth proxy, isolated from NYSE signal inputs."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import io
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request,urlopen
import numpy as np
import pandas as pd
from mbss.collectors.calendar import market_sessions,as_utc
from mbss.collectors.sources import utc_now

HOLDINGS_URL='https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx'


def parse_spy_holdings(body):
    rows=pd.read_excel(io.BytesIO(body),header=None,engine='openpyxl').fillna('').values.tolist()
    dates=[str(r[1]).strip() for r in rows if len(r)>1 and str(r[0]).strip()=='Holdings:']
    if len(dates)!=1 or not dates[0].startswith('As of '):raise ValueError('holdings date missing or ambiguous')
    date=pd.to_datetime(dates[0][6:],format='%d-%b-%Y',errors='raise')
    headers=[i for i,r in enumerate(rows) if r[:4]==['Name','Ticker','Identifier','Weight']]
    # Production sheets may place SEDOL between Identifier and Weight.
    if not headers:headers=[i for i,r in enumerate(rows) if r[:3]==['Name','Ticker','Identifier'] and 'Weight' in r]
    if len(headers)!=1:raise ValueError('holdings header missing or ambiguous')
    header=rows[headers[0]];wi=header.index('Weight');constituents=[];excluded=[];seen=set()
    for row in rows[headers[0]+1:]:
        if len(row)<=wi or row[wi]=='':continue
        ticker=str(row[1]).strip();weight=float(row[wi])
        if not np.isfinite(weight) or weight<0:raise ValueError('invalid holding weight')
        record={'original_ticker':ticker,'name':str(row[0]),'identifier':str(row[2]),'weight_pct':weight}
        if not re.fullmatch(r'[A-Z]+(?:[.\-][A-Z]+)?',ticker):
            excluded.append({**record,'reason':'MISSING_OR_UNSUPPORTED_TICKER'});continue
        symbol=ticker.replace('.','-')
        if symbol in seen:raise ValueError('duplicate Yahoo-mapped holding symbol')
        seen.add(symbol);constituents.append({**record,'symbol':symbol})
    if not constituents:raise ValueError('no traded holdings')
    return {'holdings_date':str(date.date()),'constituents':constituents,'excluded_holdings':excluded}


def parse_spark(body,symbols):
    root=json.loads(body)
    if not isinstance(root,dict):raise ValueError('spark response must map symbols')
    result={}
    for symbol in symbols:
        r=root.get(symbol)
        if not isinstance(r,dict) or r.get('symbol')!=symbol:raise ValueError('missing or mismatched spark symbol: '+symbol)
        if r.get('dataGranularity') not in ('1d',86400):raise ValueError('daily spark granularity not confirmed')
        stamps=r.get('timestamp',[]);closes=r.get('close',[])
        if not stamps or len(stamps)!=len(closes):raise ValueError('invalid spark daily arrays')
        dates=pd.to_datetime(stamps,unit='s',utc=True).tz_convert('America/New_York').tz_localize(None).normalize()
        if dates.has_duplicates:raise ValueError('spark requires one daily close per session')
        result[symbol]={str(d.date()):float(v) if v is not None and not isinstance(v,bool) and np.isfinite(float(v)) and float(v)>0 else None for d,v in zip(dates,closes)}
    return result


def assess_snapshot(snapshot,sessions,as_of):
    flags=list(snapshot.get('flags',[]));sessions=pd.DatetimeIndex(sessions);as_of=as_utc(as_of)
    r={'label':'SPY holdings breadth proxy','status':'DATA_HOLD','eligible_for_signal':False,
       'universe':'SPY published holdings with supported traded symbols; S&P500 proxy, not official index membership',
       'holdings_date':snapshot.get('holdings_date'),'observation_date':None,
       'source':snapshot.get('source',HOLDINGS_URL),'price_source':'Yahoo daily spark close',
       'retrieval_timestamp':snapshot.get('retrieval_timestamp'),'expected_count':0,'covered_count':0,
       'missing_count':0,'coverage':0.,'advances':None,'declines':None,'unchanged':None,
       'advancing_share_all':None,'advancing_share_active':None,
       'original_value':None,'adjusted_value':None,'freshness':'UNKNOWN',
       'excluded_holdings':snapshot.get('excluded_holdings',[]),'errors':snapshot.get('errors',[])}
    if len(sessions)<2:flags.append('CALENDAR_UNAVAILABLE')
    else:
        r['observation_date']=str(sessions[-1].date())
        if r['holdings_date']!=r['observation_date']:flags.append('HOLDINGS_DATE_MISMATCH')
    try:
        stamp=as_utc(r['retrieval_timestamp'])
        if stamp>as_of:flags.append('FUTURE_RETRIEVAL')
    except (ValueError,TypeError):flags.append('INVALID_RETRIEVAL_TIMESTAMP')
    if snapshot.get('collection_finished_at'):
        try:
            if as_utc(snapshot['collection_finished_at'])>as_of:flags.append('FUTURE_RETRIEVAL')
        except (ValueError,TypeError):flags.append('INVALID_RETRIEVAL_TIMESTAMP')
    constituents=snapshot.get('constituents',[]);symbols=[x.get('symbol') for x in constituents]
    if not symbols:flags.append('SOURCE_UNAVAILABLE')
    if any(not isinstance(s,str) or not re.fullmatch(r'[A-Z]+(?:-[A-Z]+)?',s) for s in symbols) or len(set(symbols))!=len(symbols):flags.append('INVALID_UNIVERSE')
    r['expected_count']=len(symbols);changes=[]
    if len(sessions)>=2:
        previous,target=[str(s.date()) for s in sessions[-2:]]
        for symbol in symbols:
            values=snapshot.get('prices',{}).get(symbol,{})
            a,b=values.get(previous),values.get(target)
            if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not np.isfinite(v) or v<=0 for v in [a,b]):continue
            changes.append(b/a-1)
    r['covered_count']=len(changes);r['missing_count']=len(symbols)-len(changes)
    r['coverage']=len(changes)/len(symbols) if symbols else 0.
    if r['missing_count']:flags.append('INSUFFICIENT_PRICE_COVERAGE')
    r['freshness']='CURRENT' if len(sessions)>=2 and r['holdings_date']==r['observation_date'] else 'STALE_OR_UNKNOWN'
    if not flags and symbols:
        a=sum(x>0 for x in changes);d=sum(x<0 for x in changes);u=len(changes)-a-d
        r.update(status='REFERENCE_ONLY_PROXY',advances=a,declines=d,unchanged=u,
                 advancing_share_all=a/len(symbols),advancing_share_active=a/(a+d) if a+d else None,
                 original_value=a/len(symbols),adjusted_value=a/len(symbols))
    r['flags']=sorted(set(flags));r['validation_status']=r['status']
    return r


def load_auxiliary(directory,sessions,as_of):
    p=Path(directory)/'auxiliary_breadth.json'
    try:
        s=json.loads(p.read_text()) if p.exists() else {'flags':['NOT_COLLECTED']}
        if not isinstance(s,dict):raise ValueError('auxiliary snapshot must be an object')
        return assess_snapshot(s,sessions,as_of)
    except (ValueError,TypeError,KeyError,AttributeError,OSError) as exc:
        return assess_snapshot({'flags':['AUXILIARY_LOAD_FAILED'],'errors':[str(exc)]},sessions,as_of)


def collect_auxiliary(destination,raw,timeout=8):
    destination=Path(destination);raw=Path(raw);raw.mkdir(parents=True,exist_ok=True)
    stamp=utc_now();attempts=[]
    snapshot={'source':HOLDINGS_URL,'retrieval_timestamp':stamp,'constituents':[],'excluded_holdings':[],
              'prices':{},'flags':[],'errors':[],'eligible_for_signal':False}
    def fetch(url,name):
        with urlopen(Request(url,headers={'User-Agent':'MBSS/0.1.3 public-data research'}),timeout=timeout) as response:body=response.read(5000000)
        p=raw/name;p.write_bytes(body)
        return body,{'source':url,'raw_file':str(p),'raw_sha256':sha256(body).hexdigest(),'retrieval_timestamp':utc_now()}
    holdings_meta={}
    try:
        body,meta=fetch(HOLDINGS_URL,'spy-holdings.xlsx');holdings_meta=meta;snapshot.update(parse_spy_holdings(body))
        snapshot['holdings_provenance']=meta
        # Broad sanity check prevents a top-ten/partial table from becoming a full breadth denominator.
        if not 450<=len(snapshot['constituents'])<=550:raise ValueError('unexpected proxy universe size; inspect source contract')
        attempts.append({'dataset':'auxiliary_holdings',**meta,'status':'DOWNLOADED_NOT_YET_VALIDATED','rows':len(snapshot['constituents'])})
        sessions,calendar=market_sessions(pd.Timestamp(stamp).tz_localize(None).normalize()-pd.Timedelta(days=20),stamp)
        if not calendar['valid'] or len(sessions)<2:snapshot['flags'].append('CALENDAR_UNAVAILABLE')
        elif snapshot['holdings_date']!=str(sessions[-1].date()):snapshot['flags'].append('HOLDINGS_DATE_MISMATCH')
        else:
            symbols=[r['symbol'] for r in snapshot['constituents']];batches=[symbols[i:i+20] for i in range(0,len(symbols),20)]
            def batch(job):
                i,symbols=job
                url='https://query1.finance.yahoo.com/v8/finance/spark?'+urlencode({'symbols':','.join(symbols),'range':'5d','interval':'1d'})
                meta={}
                try:
                    body,meta=fetch(url,f'spark-{i:03d}.json');prices=parse_spark(body,symbols)
                    return prices,{'dataset':'auxiliary_prices',**meta,'status':'DOWNLOADED_NOT_YET_VALIDATED','rows':len(prices)}
                except Exception as exc:return {},{'dataset':'auxiliary_prices','source':url,**meta,'status':'FAILED','error':str(exc),'retrieval_timestamp':utc_now()}
            with ThreadPoolExecutor(max_workers=4) as pool:
                for prices,attempt in pool.map(batch,enumerate(batches)):
                    snapshot['prices'].update(prices);attempts.append(attempt)
                    if attempt['status']=='FAILED':snapshot['flags'].append('SOURCE_UNAVAILABLE');snapshot['errors'].append(attempt['error'])
    except Exception as exc:
        snapshot['flags'].append('SOURCE_UNAVAILABLE');snapshot['errors'].append(type(exc).__name__+': '+str(exc))
        attempts.append({'dataset':'auxiliary_holdings','source':HOLDINGS_URL,**holdings_meta,'status':'FAILED','error':str(exc),'retrieval_timestamp':stamp})
    snapshot['collection_finished_at']=utc_now()
    # Replace collector-owned snapshot even on failure; never silently reuse old success.
    (destination/'auxiliary_breadth.json').write_text(json.dumps(snapshot,indent=2,allow_nan=False))
    return attempts
