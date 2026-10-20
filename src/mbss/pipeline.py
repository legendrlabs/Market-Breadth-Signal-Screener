from dataclasses import asdict
from hashlib import sha256
from importlib.metadata import version,PackageNotFoundError
from pathlib import Path
import json
import os
import platform
import re
import shutil
import subprocess
import uuid
import numpy as np
import pandas as pd
from mbss import __version__
from mbss.collectors.calendar import market_sessions,as_utc
from mbss.collectors.sources import load_inputs,utc_now
from mbss.collectors.quality import validate_dataset,reason_codes,breadth_diagnostics
from mbss.collectors.context import external_context
from mbss.collectors.auxiliary import load_auxiliary
from mbss.indicators.core import breadth_ratio,ema
from mbss.signals.core import zbt_events,rally_events,expansion_events,election_events,all_combinations
from mbss.backtest.events import event_study
from mbss.backtest.portfolio import portfolio_curve,curve_metrics
from mbss.analytics.stats import summarize,random_baseline
from mbss.analytics.claims import claim_audit,regime_cases
from mbss.risk.core import daily_assessment
from mbss.reports.render import plots,render


def digest(file):return sha256(Path(file).read_bytes()).hexdigest()


def publication_context(commit,environ=None):
    """Record a matching GitHub run; never guess remote release existence."""
    env=os.environ if environ is None else environ
    result={'github_repository':'UNKNOWN_NOT_CHECKED','release':'NOT_CHECKED',
            'workflow_run_url':None,'execution_context':'LOCAL_OR_UNVERIFIED'}
    repository=env.get('GITHUB_REPOSITORY','');run_id=env.get('GITHUB_RUN_ID','')
    if (env.get('GITHUB_ACTIONS')=='true'
        and isinstance(commit,str) and re.fullmatch(r'[0-9a-f]{40}',commit)
        and env.get('GITHUB_SHA')==commit
        and re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository)
        and re.fullmatch(r'\d+',run_id)):
        url='https://github.com/'+repository
        result.update(github_repository=url,workflow_run_url=url+'/actions/runs/'+run_id,
                      execution_context='GITHUB_ACTIONS_MATCHING_CHECKOUT')
    return result


def json_safe(value):
    if isinstance(value,dict):return {str(k):json_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [json_safe(v) for v in value]
    if isinstance(value,(pd.Timestamp,Path)):return str(value)
    if isinstance(value,(float,np.floating)):return float(value) if np.isfinite(value) else None
    if isinstance(value,np.integer):return int(value)
    if isinstance(value,np.bool_):return bool(value)
    return value


def dump(path,value):path.write_text(json.dumps(json_safe(value),ensure_ascii=False,indent=2,allow_nan=False))


def observations(frames,metadata,quality):
    rows=[]
    for name,frame in frames.items():
        meta=metadata.get(name,{});q=quality.get(name,{})
        for date,row in frame.iterrows():
            for field,val in row.items():
                adjusted=val
                if name in ('spy','qqq') and field in ('open','high','low','close'):
                    close=pd.to_numeric(row.get('close'),errors='coerce')
                    adj=pd.to_numeric(row.get('adj_close'),errors='coerce')
                    numeric=pd.to_numeric(val,errors='coerce')
                    adjusted=numeric*adj/close if pd.notna(close) and close>0 else np.nan
                rows.append({'dataset':name,'observation_date':str(date.date()),'field':field,
                             'source':meta.get('source'),'retrieval_timestamp':meta.get('retrieval_timestamp'),
                             'original_value':val,'adjusted_value':adjusted,'missing_count':q.get('missing_count'),
                             'freshness':q.get('freshness'),'validation_status':q.get('validation_status')})
    return pd.DataFrame(rows,columns=['dataset','observation_date','field','source','retrieval_timestamp','original_value','adjusted_value','missing_count','freshness','validation_status'])


def run(input_dir,output_dir,as_of=None,start='2000-01-01',seed=42,cost_bps=0,
        bootstrap_draws=2000,sessions_override=None,synthetic=False,config=None):
    """One immutable run. Synthetic session injection is available only to tests."""
    if sessions_override is not None and not synthetic:raise ValueError('Session override requires synthetic=True; unavailable for actual research')
    if not 0<=cost_bps<10000:raise ValueError('invalid cost_bps')
    if bootstrap_draws<20:raise ValueError('bootstrap_draws must be >=20')
    as_of=as_utc(as_of or utc_now());start=pd.Timestamp(start).normalize()
    if start.tzinfo is not None or start>as_of.tz_localize(None):raise ValueError('invalid start')
    cfg=config or {};input_dir=Path(input_dir);output=Path(output_dir)
    primary_zbt={'ema_span':10,'ema_seed':'sma','warmup_sessions':100,'inclusive':False,'max_distance':10}
    if any(k not in primary_zbt or v!=primary_zbt[k] for k,v in cfg.get('zbt',{}).items()):
        raise ValueError('Primary ZBT definition is fixed in v0.1.0; use exported definition sensitivities')
    if cfg.get('expansion_cooldown_sessions',10)!=10:
        raise ValueError('Primary expansion cooldown is fixed at 10 sessions')
    if output.exists():raise FileExistsError('Use a new output directory to preserve an immutable run')
    output.parent.mkdir(parents=True,exist_ok=True)
    stage=output.parent/('.mbss-'+uuid.uuid4().hex);stage.mkdir()
    try:
        if sessions_override is None:
            sessions,calendar=market_sessions(start-pd.Timedelta(days=365),as_of)
        else:
            sessions=pd.DatetimeIndex(sessions_override);sessions=sessions[sessions<=as_of.tz_localize(None).normalize()]
            calendar={'valid':True,'source':'SYNTHETIC TEST CALENDAR','expected_last':str(sessions[-1].date()) if len(sessions) else None}
        frames,metadata,load_errors=load_inputs(input_dir)
        expected_last=sessions[-1] if len(sessions) else as_of.tz_convert('America/New_York').tz_localize(None).normalize()-pd.Timedelta(days=1)
        quality={};excluded={}
        for name,frame in frames.items():
            if not frame.empty:
                excluded[name]=int((frame.index>expected_last).sum())
                frame=frame.loc[frame.index<=expected_last]
                if len(sessions):frame=frame.loc[frame.index>=sessions[0]]
                frames[name]=frame
            q=validate_dataset(name,frame,metadata.get(name,{}),sessions,expected_last)
            if not calendar['valid']:
                q['history_valid']=False;q['validation_status']='DATA_HOLD';q['flags'].append('CALENDAR_UNVERIFIED')
            if name in load_errors or 'metadata' in load_errors:
                q['history_valid']=False;q['validation_status']='DATA_HOLD';q['flags'].append('PARSE_ERROR')
            q['future_or_unclosed_rows_excluded']=excluded.get(name,0)
            q['reason_codes']=reason_codes(q['flags'],q['fresh'],q['rows'])
            quality[name]=q
        usable={n:f.reindex(sessions) for n,f in frames.items() if quality[n]['history_valid']}
        events=[];sensitivities=[]
        if 'spx' in usable:events+=rally_events(usable['spx'].close)
        if 'breadth' in usable:
            b=usable['breadth'];r=breadth_ratio(b.advances,b.declines);z=cfg.get('zbt',{})
            smooth=ema(r,span=z.get('ema_span',10),warmup=z.get('warmup_sessions',100),seed=z.get('ema_seed','sma'))
            events+=zbt_events(smooth,inclusive=z.get('inclusive',False),max_distance=z.get('max_distance',10))
            events+=expansion_events(r,cooldown=cfg.get('expansion_cooldown_sessions',10))
            for label,series,inclusive,distance in [('inclusive',smooth,True,10),('strict_distance9',smooth,False,9),('first_seed',ema(r,seed='first'),False,10)]:
                sensitivities += [{**e.record(),'sensitivity':label} for e in zbt_events(series,inclusive,distance) if e.date>=start]
        if calendar['valid']:events+=election_events(sessions,expected_last,first_year=max(1974,sessions[0].year))
        # Buffered constituents and prior election context are available causally.
        # Filter confirmations only after combinations have consumed that context.
        events+=all_combinations(events,sessions)
        events=sorted([e for e in events if e.date>=start],key=lambda e:(e.date,e.signal))
        study_sessions=sessions[sessions>=start]
        results=event_study(events,usable,study_sessions,as_of=expected_last,cost_bps=cost_bps)
        summary=summarize(results,seed=seed,draws=bootstrap_draws)
        baselines={}
        if 'spx' in usable:
            for month in (1,3,6,12):
                baselines[str(month)]=random_baseline(usable['spx'],study_sessions,month,seed,bootstrap_draws,cost_bps)
            for s in summary:
                baseline=baselines.get(str(s['months']),{})
                s['random_entry_mean']=baseline.get('mean')
                s['excess_over_unconditional_mean']=s.get('mean')-baseline['mean'] if s.get('mean') is not None and baseline.get('mean') is not None else None
            if not results.empty:
                results['random_entry_mean']=results.months.map(lambda m:baselines[str(m)].get('mean'))
                results['excess_over_random_mean']=results.return_price-results.random_entry_mean
        curves={};strategy_summary=[];trades=[]
        if 'spy' in usable:
            # Same common valid window for every strategy and benchmark.
            spy=usable['spy']
            bounds=['spy']+(['spx'] if 'spx' in usable else [])+(['breadth'] if 'spx' in usable and 'breadth' in usable else [])
            common_start=max([start]+[frames[n].index.min() for n in bounds])
            common_end=min(frames[n].index.max() for n in bounds)
            if 'breadth' in bounds:
                # No strategy may treat unavailable EMA warmup history as known no-signal cash.
                warmup=cfg.get('zbt',{}).get('warmup_sessions',100)
                first_breadth=sessions.searchsorted(frames['breadth'].index.min())+warmup-1
                if first_breadth<len(sessions):common_start=max(common_start,sessions[first_breadth])
                else:common_start=common_end+pd.Timedelta(days=1)
            common=study_sessions[(study_sessions>=common_start)&(study_sessions<=common_end)]
            if len(common):
                bh,_=portfolio_curve([],spy,common,cost_bps=cost_bps,buy_hold=True)
                if not bh.empty:
                    curves['SPY Buy & Hold']=bh;bh_metrics=curve_metrics(bh)
                    comparison_window={'start':str(common[0].date()),'end':str(common[-1].date()),'coverage_datasets':bounds}
                    strategy_summary.append({'strategy':'SPY Buy & Hold',**bh_metrics,'opportunity_cost_vs_buy_hold':0.,'comparison_window':comparison_window})
                    # Include only data-valid signal families; zero events is a meaningful cash baseline.
                    valid_labels=[]
                    if 'spx' in usable:valid_labels+=['B','D']
                    if 'spx' in usable and 'breadth' in usable:valid_labels+=['A','C','A+B@5','A+B@10','A+C@5','A+C@10','B+C@5','B+C@10','A+B+C@5','A+B+C@10','D+A','D+B','D+C']
                    for signal in valid_labels:
                        for month in (6,12):
                            label=f'{signal} {month}m';curve,t=portfolio_curve([e for e in events if e.signal==signal],spy,common,month,cost_bps)
                            if curve.empty:continue
                            curves[label]=curve;m=curve_metrics(curve)
                            strategy_summary.append({'strategy':label,**m,'opportunity_cost_vs_buy_hold':bh_metrics['cumulative_return']-m['cumulative_return'],'comparison_window':comparison_window})
                            trades += [{'strategy':label,**x} for x in t]
        # D is calendar context; the hypothetical D portfolio is a research comparison only.
        assessment=daily_assessment(events,usable,quality,sessions,calendar['valid'],cfg.get('risk'))
        claims=claim_audit(results,synthetic);cases=regime_cases(results)
        data_quality={'status':assessment['DATA_QUALITY'],'calendar':calendar,'datasets':quality,
                      'load_errors':load_errors,'synthetic':synthetic,'raw_observations_used_for_trading':False,
                      'breadth_diagnostics':breadth_diagnostics(frames['breadth'],sessions,expected_last)}
        context=external_context(input_dir,as_of)
        auxiliary=load_auxiliary(input_dir,sessions,as_of)
        data_quality["auxiliary_breadth"]=auxiliary
        versions={}
        for package in ('pandas','numpy','matplotlib','exchange-calendars','xlrd','openpyxl'):
            try:versions[package]=version(package)
            except PackageNotFoundError:versions[package]='NOT_INSTALLED'
        try:commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=Path(__file__).resolve().parents[2],stderr=subprocess.DEVNULL,text=True).strip()
        except (subprocess.CalledProcessError,OSError):commit=None
        manifest={'project':'MBSS','version':__version__,'run_id':output.name,'created_at':utc_now(),'as_of_utc':as_of.isoformat(),
                  'requested_start':str(start.date()),'expected_last_session':calendar.get('expected_last'),
                  'seed':seed,'bootstrap_draws':bootstrap_draws,'cost_bps_per_side':cost_bps,'synthetic':synthetic,
                  'configuration':cfg,'python':platform.python_version(),'packages':versions,'git_commit':commit,
                  'input_sha256':{f.name:digest(f) for f in sorted(input_dir.glob('*')) if f.is_file()},
                  'definitions':{'A':'EMA10 A/(A+D), strict 0.4->0.615 within distance<=10, SMA10 seed, warmup100','B':'3 consecutive daily close gains >=1.5%, first third day','C':'>70% on 6 of 10 sessions, first edge, cooldown10','D':'midterm election next session open, no future elections'},
                  'return_convention':'next-open entry; calendar-month target rolled forward; close exit; no shortened immature horizons',
                  'assumptions':{'cash_return':0,'rf_for_sharpe':0,'leverage':1,'position_limit':1,'dividend_proxy':'Yahoo adjusted OHLC','allocation_enabled':False},
                  'limitations':['Original book/NDR archive unverified','Full published event-date lists unreconciled','Single-source price revisions possible','Multiple comparisons; no optimized thresholds','Calendar library is a third-party schedule, not an official exchange feed'],
                  'publication':publication_context(commit)}
        project_root=Path(__file__).resolve().parents[2]
        manifest['source_sha256']={str(f.relative_to(project_root)):digest(f) for f in sorted((project_root/'src').rglob('*.py'))}
        try:manifest['git_dirty']=bool(subprocess.check_output(['git','status','--porcelain'],cwd=project_root,text=True).strip())
        except (subprocess.CalledProcessError,OSError):manifest['git_dirty']=None
        attempt_path=input_dir/'collection_attempts.json'
        if attempt_path.exists():manifest['collection_attempts']=json.loads(attempt_path.read_text())
        pd.DataFrame([e.record() for e in events],columns=['signal','signal_date','components','definition']).to_csv(stage/'signals.csv',index=False)
        results.to_csv(stage/'backtest_results.csv',index=False)
        dump(stage/'signal_events.json',{'assessment':assessment,'events':[e.record() for e in events],'synthetic':synthetic})
        dump(stage/'external_context.json',context)
        dump(stage/'auxiliary_breadth.json',auxiliary)
        if (input_dir/'auxiliary_breadth.json').exists():
            shutil.copyfile(input_dir/'auxiliary_breadth.json',stage/'auxiliary_snapshot.json')
        dump(stage/'data_quality.json',data_quality);dump(stage/'summary.json',summary);dump(stage/'claim_audit.json',claims)
        dump(stage/'random_baselines.json',baselines);dump(stage/'strategy_summary.json',strategy_summary)
        dump(stage/'strategy_trades.json',trades)
        pd.DataFrame(sensitivities,columns=['signal','signal_date','components','definition','sensitivity']).to_csv(stage/'definition_sensitivity.csv',index=False)
        cases.to_csv(stage/'regime_cases.csv',index=False)
        observations(frames,metadata,quality).to_csv(stage/'observations.csv',index=False)
        if curves:pd.concat({k:v.equity for k,v in curves.items()},axis=1).to_csv(stage/'strategy_equity.csv',index_label='date')
        images=plots(usable,events,results,curves,cases,synthetic,display_start=start)
        render(stage,assessment,data_quality,summary,claims,images,manifest,strategy_summary,synthetic,external_context=context)
        manifest['output_sha256']={f.name:digest(f) for f in sorted(stage.glob('*')) if f.is_file()}
        dump(stage/'run_manifest.json',manifest)
        os.replace(stage,output)
        return {'assessment':assessment,'claims':claims,'summary':summary,'manifest':manifest}
    except Exception:
        shutil.rmtree(stage,ignore_errors=True)
        raise
