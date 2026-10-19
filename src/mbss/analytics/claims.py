"""Published figures are research targets, never expected engine outputs."""
import pandas as pd

CARSON='https://www.carsongroup.com/insights/blog/houston-we-have-a-zweig-breadth-thrust-and-four-more-bullish-developments/'
SCHWAB='https://www.schwab.com/learn/story/what-2026-midterms-could-mean-markets'


def claim_audit(results,synthetic=False):
    claims=[]
    for signal,n,months,mean,source,scope in [('A',19,12,.234,CARSON,'post-WWII mature signals before April 2025'),
                                              ('B',10,12,.216,CARSON,'historical mature signals before April 2025'),
                                              ('C',8,6,.14,CARSON,'historical mature signals before April 2025'),
                                              ('D',13,6,.124,SCHWAB,'1974 through 2022 midterm elections')]:
        if results.empty:subset=results
        else:
            subset=results[(results.signal==signal)&(results.months==months)&(results.status=='COMPLETE')]
            # A 2025 claim cannot include the subsequent new signal's future outcome.
            cutoff='2022-12-31' if signal=='D' else '2025-04-24'
            subset=subset[subset.signal_date<cutoff] if signal!='D' else subset[subset.signal_date<=cutoff]
            if signal!='D':
                subset=subset[pd.to_datetime(subset.exit_date)<=pd.Timestamp('2025-04-24')]
        count=len(subset)
        reference_means={}
        for label in ('signal_close_calendar_return','signal_close_session_return'):
            reference_means[label]=float(subset[label].mean()) if count and label in subset and subset[label].notna().any() else None
        matches={label: (value>mean if signal=='C' else round(value*100,1)==round(mean*100,1)) if value is not None else False for label,value in reference_means.items()}
        claims.append({'signal':signal,'status':'UNVERIFIED','published_n':n,'published_months':months,
                       'published_win_rate':1.,'published_mean':mean,'published_mean_operator':'>' if signal=='C' else 'approximately',
                       'scope':scope,'source':source,'reproduced_complete_n_in_claim_scope':count,
                       'observed_win_rate':float((subset.return_price>0).mean()) if count else None,
                       'observed_mean_next_open':float(subset.return_price.mean()) if count else None,
                       'reference_means_not_executable':reference_means,
                       'aggregate_count_match':count==n,
                       'aggregate_mean_match_by_reference':matches,
                       'reconciliation':'Aggregate coincidence is conditional on the displayed reference convention; original date list/definition still unverified',
                       'reason':'Synthetic verification fixture; no historical evidence' if synthetic else 'Original event-date list, comparable full-history input and exact publication entry/exit convention not reconciled; matching aggregate numbers alone is insufficient'})
    return claims


def regime_cases(results):
    if results.empty:return pd.DataFrame(columns=['signal','signal_date','entry_date','months','regime','return_price','max_drawdown','status'])
    frame=results.copy();years=pd.to_datetime(frame.entry_date).dt.year
    frame['regime']='Other years'
    frame.loc[years.between(2000,2002),'regime']='2000-2002'
    for year in (2008,2020,2022,2025):frame.loc[years==year,'regime']=str(year)
    return frame[['signal','signal_date','entry_date','months','regime','return_price','max_drawdown','status']]
