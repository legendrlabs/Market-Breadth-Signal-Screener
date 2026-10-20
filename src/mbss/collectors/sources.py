"""Free source adapters; no credentials, scraping paywalls, or inferred breadth."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import quote
import io
import json
import time
import pandas as pd


def utc_now():return datetime.now(timezone.utc).isoformat()


def parse_yahoo(body):
    root=json.loads(body)
    result=root['chart']['result'][0]
    quote_data=result['indicators']['quote'][0]
    dates=pd.to_datetime(result['timestamp'],unit='s',utc=True).tz_convert('America/New_York').tz_localize(None).normalize()
    frame=pd.DataFrame({c:quote_data[c] for c in ('open','high','low','close')},index=dates)
    frame['adj_close']=result['indicators']['adjclose'][0]['adjclose']
    frame['dividend']=0.
    for event in result.get('events',{}).get('dividends',{}).values():
        date=pd.Timestamp(event['date'],unit='s',tz='UTC').tz_convert('America/New_York').tz_localize(None).normalize()
        if date in frame.index:frame.loc[date,'dividend']=float(event['amount'])
    frame.index.name='date'
    return frame


def parse_cboe(body):
    frame=pd.read_csv(io.BytesIO(body))
    frame.columns=[c.strip().lower() for c in frame.columns]
    frame['date']=pd.to_datetime(frame.date,format='%m/%d/%Y')
    return frame.set_index('date')[['close']].sort_index()


def parse_mcclellan_rows(rows,datemode=0):
    import xlrd
    headers=[i for i,row in enumerate(rows[:-1]) if len(row)>=3 and
             [str(x).strip().upper() for x in row[:3]]==['DATE','NYSE','NYSE'] and
             [str(x).strip().upper() for x in rows[i+1][1:3]]==['ADV.','DEC.']]
    if len(headers)!=1:raise ValueError('NYSE DATE/ADV./DEC. XLS header not identified uniquely')
    observations=[];note_rows=0
    def numeric(value):
        try:float(value);return True
        except (ValueError,TypeError):return False
    for row in rows[headers[0]+2:]:
        if len(row)<3:continue
        date,a,d=row[:3]
        if not numeric(a) and not numeric(d):
            if str(a or '').strip() or str(d or '').strip():note_rows+=1
            continue
        if not isinstance(date,(int,float)):raise ValueError('breadth observation has invalid Excel date')
        stamp=pd.Timestamp(xlrd.xldate_as_datetime(date,datemode)).normalize()
        observations.append((stamp,a,d))
    if not observations:raise ValueError('no actual breadth observations')
    frame=pd.DataFrame(observations,columns=['date','advances','declines']).set_index('date')
    frame.attrs['non_observation_note_rows']=note_rows
    return frame


def parse_mcclellan(body):
    import xlrd
    book=xlrd.open_workbook(file_contents=body);sheet=book.sheet_by_name('A')
    return parse_mcclellan_rows([sheet.row_values(i) for i in range(sheet.nrows)],book.datemode)


def collect(destination,start='2000-01-01',timeout=8,aux_breadth=False):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    raw=destination.parent/'raw'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');raw.mkdir(parents=True)
    jobs=[('spx','^GSPC'),('spy','SPY'),('qqq','QQQ')]
    sources=[]
    period=int(pd.Timestamp(start,tz='UTC').timestamp())
    end=int(pd.Timestamp.now(tz='UTC').timestamp())
    for name,symbol in jobs:
        url=f'https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol,safe="")}?period1={period}&period2={end}&interval=1d&events=div%2Csplits'
        sources.append((name,url,parse_yahoo))
    sources.append(('vix','https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv',parse_cboe))
    sources.append(('breadth','https://www.mcoscillator.com/data/osc_data/OSC-DATA.xls',parse_mcclellan))
    meta_path=destination/'metadata.json'
    metadata=json.loads(meta_path.read_text()) if meta_path.exists() else {}

    def download(job):
        name,url,parser=job;begin=time.monotonic();stamp=utc_now()
        attempt={'dataset':name,'source':url,'retrieval_timestamp':stamp}
        try:
            request=Request(url,headers={'User-Agent':'MBSS/0.1.3 (independent public-data research)'})
            with urlopen(request,timeout=timeout) as response:body=response.read(30_000_000)
            raw_path=raw/(name+('.xls' if name=='breadth' else '.csv' if name=='vix' else '.json'));raw_path.write_bytes(body)
            frame=parser(body)
            if frame.empty:raise ValueError('empty dataset')
            attempt.update(status='DOWNLOADED_NOT_YET_VALIDATED',rows=len(frame),raw_sha256=sha256(body).hexdigest(),raw_file=str(raw_path))
            if frame.attrs:attempt['parser_notes']=dict(frame.attrs)
            return name,frame,attempt
        except Exception as exc:
            attempt.update(status='FAILED',error=type(exc).__name__+': '+str(exc))
            return name,None,attempt
        finally:attempt['elapsed_seconds']=round(time.monotonic()-begin,3)

    attempts=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for name,frame,attempt in pool.map(download,sources):
            attempts.append(attempt)
            if frame is None:continue
            new_meta={'source':attempt['source'],'retrieval_timestamp':attempt['retrieval_timestamp'],
                            'definition':'S&P 500 index price OHLC' if name=='spx' else 'Cboe VIX daily close' if name=='vix' else name.upper()+' split-adjusted OHLC, dividend-adjusted close and cash distributions',
                            'adjustment_method':'Index price only; no dividend total-return series' if name=='spx' else 'Cboe published close' if name=='vix' else 'Yahoo adj_close/close factor; adjusted OHLC total-return proxy',
                            'review_status':'documented','raw_sha256':attempt['raw_sha256'],
                            'raw_file':attempt['raw_file'],'redistribution':'Provider terms apply; raw data not shipped in source release',
                            'adjustment_reference':'https://in.help.yahoo.com/kb/adjusted-close-sln28256.html' if name!='vix' else 'https://www.cboe.com/tradable-products/vix/vix-historical-data'}
            if name=='breadth':
                new_meta.update(definition='McClellan published NYSE composite advancing/declining issue counts; recent window only',
                    adjustment_method='Published final WSJ/Barrons-based counts; no price reconstruction or gap filling',
                    adjustment_reference='https://www.mcoscillator.com/market_breadth_data/',
                    universe={'exchange':'NYSE','etf_included':None,'preferred_included':None,'closed_end_fund_included':None,'point_in_time_membership':None},
                    universe_evidence='https://www.mcoscillator.com/learning_center/kb/market_data/a-d_data_composite_or_operating_companies_only/',
                    reference_comparability={'status':'unverified','evidence':None},
                    limitations=['Recent rolling window, not continuous 2000-present history','Exact historical universe and NDR comparability unverified'],collector_managed=True)
                existing=metadata.get('breadth',{})
                if (destination/'breadth.csv').exists() and not (existing.get('collector_managed') is True and
                        existing.get('source')==attempt['source'] and existing.get('review_status')!='reviewed'):
                    frame.to_csv(destination/'breadth_candidate.csv',index_label='date')
                    (destination/'breadth_candidate_metadata.json').write_text(json.dumps(new_meta,indent=2))
                    attempt['application_status']='CANDIDATE_ONLY_EXISTING_INPUT_PRESERVED'
                    continue
            frame.to_csv(destination/(name+'.csv'),index_label='date')
            metadata[name]=new_meta
    # Publisher HTML is an independent *format*, not an independent provider.
    # A missing/invalid page never replaces or validates the NYSE XLS signal input.
    from mbss.collectors.mcclellan_page import collect_publisher_page
    attempts.append(collect_publisher_page(destination,raw,timeout,opener=urlopen))
    if aux_breadth:
        from mbss.collectors.auxiliary import collect_auxiliary
        attempts.extend(collect_auxiliary(destination,raw,timeout))
    meta_path.write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
    (destination/'collection_attempts.json').write_text(json.dumps(attempts,ensure_ascii=False,indent=2))
    return attempts


def load_inputs(directory):
    directory=Path(directory);metadata={};frames={};errors={}
    try:
        if (directory/'metadata.json').exists():metadata=json.loads((directory/'metadata.json').read_text())
        if not isinstance(metadata,dict) or not all(isinstance(v,dict) for v in metadata.values()):
            raise ValueError('metadata must be an object mapping dataset names to objects')
    except (ValueError,OSError) as exc:errors['metadata']=str(exc);metadata={}
    for name in ('spx','spy','qqq','vix','breadth'):
        file=directory/(name+'.csv')
        if not file.exists():frames[name]=pd.DataFrame();continue
        try:
            frame=pd.read_csv(file)
            frame['date']=pd.to_datetime(frame.date,format='%Y-%m-%d',errors='raise')
            if frame.date.dt.tz is not None:raise ValueError('session dates must be timezone-naive YYYY-MM-DD')
            frames[name]=frame.set_index('date')
        except (ValueError,KeyError,OSError) as exc:errors[name]=str(exc);frames[name]=pd.DataFrame()
    return frames,metadata,errors
