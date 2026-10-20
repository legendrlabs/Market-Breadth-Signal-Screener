import base64
from html import escape
import io
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mbss.indicators.core import breadth_ratio,ema,expansion_count


def plots(data,events,results,curves,cases,synthetic=False,display_start=None):
    images={}
    titles=['S&P 500 and confirmed signal dates','ZBT: 10-session EMA of NYSE breadth','Repeated breadth expansion: eligible sessions in trailing 10',
            'Hypothetical forward price-return distributions','Hypothetical SPY strategies vs buy & hold','Hypothetical strategy drawdowns','Historical cases by predefined regime']
    for i,title in enumerate(titles,1):
        fig,ax=plt.subplots(figsize=(10.5,3.5));drawn=False
        if i==1 and 'spx' in data:
            close=data['spx'].close
            if display_start is not None:close=close.loc[close.index>=display_start]
            ax.plot(close.index,close,color='#345be0',lw=.9,label='Observed index price')
            for signal,color in [('A','#e15656'),('B','#1e9b72'),('C','#a162cf'),('D','#c28a14')]:
                dates=[e.date for e in events if e.signal==signal and e.date in close.index]
                if dates:ax.scatter(dates,close.reindex(dates),s=22,label=signal,color=color,zorder=5)
            drawn=True
        if i in (2,3) and 'breadth' in data:
            b=data['breadth'];ratio=breadth_ratio(b.advances,b.declines)
            series=ema(ratio) if i==2 else expansion_count(ratio)
            if series.notna().any():
                ax.plot(series.index,series,color='#345be0',lw=.9,label='Observed-data indicator');drawn=True
                for line in ((.4,.615) if i==2 else (6,)):ax.axhline(line,color='#bf4f42',ls='--',lw=.9,label=str(line))
        if i==4 and not results.empty:
            r=results[(results.status=='COMPLETE')&results.months.isin([6,12])]
            values=[];labels=[]
            for (s,m),g in r.groupby(['signal','months']):
                if g.return_price.notna().any():values.append(g.return_price.dropna().to_numpy()*100);labels.append(f'{s} {m}m n={len(g)}')
            if values:
                ax.boxplot(values,tick_labels=labels,showmeans=True);ax.tick_params(axis='x',labelrotation=65,labelsize=7);ax.set_ylabel('Price return (%)');drawn=True
        if i in (5,6):
            for label,curve in curves.items():
                if curve.empty:continue
                y=curve.equity if i==5 else curve.equity/curve.equity.cummax().clip(lower=1)-1
                ax.plot(curve.index,y,lw=1.4 if label=='SPY Buy & Hold' else .7,label=label)
                drawn=True
        if i==7 and not cases.empty:
            frame=cases[(cases.status=='COMPLETE')&(cases.months==6)]
            if not frame.empty:
                groups=frame.groupby('regime').return_price.mean().sort_index()*100
                ax.bar(groups.index,groups.to_numpy(),color=['#1c9d7a' if x>0 else '#d55151' for x in groups]);ax.axhline(0,color='black',lw=.6)
                ax.set_ylabel('Mean hypothetical 6m price return (%)');drawn=True
        if not drawn:
            ax.text(.5,.5,'DATA_HOLD — required validated observations unavailable',ha='center',va='center',transform=ax.transAxes,color='#8c3c3c',fontsize=11)
            ax.set_xticks([]);ax.set_yticks([])
        elif i!=7:
            handles,labels=ax.get_legend_handles_labels()
            if handles:ax.legend(loc='best',fontsize=6,ncol=3)
        if drawn and i in (1,2,3):
            dates=data['spx'].index if 'spx' in data else data['breadth'].index
            if len(dates)>1:ax.set_xlim(max(dates[0],display_start) if display_start is not None else dates[0],dates[-1])
        if drawn and i in (5,6) and curves:
            first_curve=next(iter(curves.values()))
            if len(first_curve)>1:ax.set_xlim(first_curve.index[0],first_curve.index[-1])
        ax.set_title(title+(' — SYNTHETIC TEST ONLY' if synthetic else ''),fontsize=11)
        ax.grid(alpha=.15);fig.tight_layout()
        buffer=io.BytesIO();fig.savefig(buffer,format='png',dpi=115);plt.close(fig)
        images[f'{i:02d}']=base64.b64encode(buffer.getvalue()).decode()
    return images


def md_table(headers,rows):
    def cell(v):
        if v is None:return '—'
        return str(v).replace('|','/').replace('\n',' ')
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(cell(x) for x in row)+' |' for row in rows])


def render(output,assessment,quality,summary,claims,images,manifest,strategy_summary,synthetic=False,external_context=None):
    def pct(v):return f'{v*100:+.2f}%' if v is not None and np.isfinite(v) else '—'
    title='MBSS v0.1.3 — '+('SYNTHETIC TEST ONLY' if synthetic else 'Independent research report')
    status=assessment['SIGNAL_STATUS'];last=assessment['as_of_session'] or 'unknown'
    lines=[f'# {title}',f"As of UTC: {manifest['as_of_utc']} / completed NYSE session: {last}",
           f"**{status} · SAFE_TO_ACT=False · OBSERVE_ONLY**",'',
           '기존 장기 주식모으기·인컴 분배금 TQQQ 재투자·Mechanical Top15·K-Mechanical·SSM 규칙은 변경하지 않습니다. 전술 유동성 판단 보조용 연구 결과이며 자금 투입 비중은 아직 승인되지 않았습니다.',
           '', '## Daily signal states','',md_table(['Signal','Current state','Current signal date','Last signal','Last lifecycle','Seasonality','Data quality','Hold reasons'],[[s,r['SIGNAL_STATUS'],r['SIGNAL_DATE'],r.get('LAST_SIGNAL_DATE'),r.get('LAST_SIGNAL_STATUS'),r.get('SEASONALITY_STATUS'),r['DATA_QUALITY'],', '.join(r.get('DATA_HOLD_REASONS',[]))] for s,r in assessment['signals'].items()]),
           '', '## Observed market data and indicators','',md_table(['Metric','Value'],list(assessment['metrics'].items())),
           '', '## Data quality','',md_table(['Dataset','Rows','From','Through','History valid','Freshness','Missing XNYS sessions','Excluded non-XNYS','Reason codes','Flags'],[[n,q.get('rows'),q.get('start'),q.get('end'),q.get('history_valid'),q.get('freshness'),q.get('missing_count'),q.get('excluded_non_xnys_session_count',0),', '.join(q.get('reason_codes',[])),', '.join(q.get('flags',[]))] for n,q in quality['datasets'].items()]),
           '',f"Calendar valid: {quality['calendar'].get('valid')}. {quality['calendar'].get('error','')}",
           '', '## Independent claim audit','',md_table(['Signal','Published n','Horizon','Status','Complete n','Published mean','Next-open mean'],[[c['signal'],c['published_n'],str(c['published_months'])+'m',c['status'],c['reproduced_complete_n_in_claim_scope'],pct(c['published_mean']),pct(c['observed_mean_next_open'])] for c in claims]),
           '', 'Reference-only comparison (same-day close is not an executable after-close entry):','',
           md_table(['Signal','Signal close → calendar horizon','Signal close → 21/63/126/252 sessions'],[[c['signal'],pct(c.get('reference_means_not_executable',{}).get('signal_close_calendar_return')),pct(c.get('reference_means_not_executable',{}).get('signal_close_session_return'))] for c in claims]),
           '', 'These are validation targets. UNVERIFIED means the published date list, data universe, or return convention has not been independently reconciled. A 2000 start cannot replicate the WWII sample or all 13 elections since 1974.',
           '', '## Event study (hypothetical next-open entries)','']
    if summary:
        lines.append(md_table(['Signal','Months','Complete n','Immature','Mean','Median','Win rate','Overlap clusters','Cluster-bootstrap 95%'],[[s['signal'],s['months'],s['n'],s['immature'],pct(s.get('mean')),pct(s.get('median')),pct(s.get('win_rate')),s.get('overlap_clusters'),' / '.join(pct(v) for v in s['mean_cluster_bootstrap_95']) if s.get('mean_cluster_bootstrap_95') else '—'] for s in summary]))
    else:lines.append('DATA_HOLD: no validated historical outcome sample. Performance and win rates are unavailable; no zero return is imputed.')
    diagnostics=quality.get('breadth_diagnostics',{})
    lines+=['','## NYSE recent observations — UNVERIFIED_REFERENCE_ONLY','',
            'Source-only NYSE observations, not Carson/NDR-validated A/C signals. As-of versus last observed NYSE session, consecutive valid sessions, and 100-session EMA warmup are reported separately. Missing sessions reset the EMA and ten-session window. SAFE_TO_ACT remains False.',
            '',md_table(['Metric','Value'],list(diagnostics.items()))]
    aux=quality.get('auxiliary_breadth',{})
    lines+=['','## SPY holdings breadth proxy — auxiliary only','',
            'Not official S&P500 breadth or NYSE A/D. Only same-session holdings and complete prior/current daily closes qualify. Advancing share all includes unchanged holdings; active denominator excludes unchanged. No historical constituent backfill, ZBT substitution, or allocation use.',
            '',md_table(['Metric','Value'],[(k,v) for k,v in aux.items() if k not in ['excluded_holdings']]),
            '', 'Excluded holding records: '+json.dumps(aux.get('excluded_holdings',[]),ensure_ascii=False)]
    context=external_context or {'observations':[]}
    lines+=['','## External intraday references — excluded from MBSS signals','',
            md_table(['Metric','Value','Universe','Session','Observed at','Retrieved at','Source','Status','Flags'],[[r.get('metric'),r.get('value'),r.get('universe'),r.get('session_type'),r.get('observed_at'),r.get('retrieval_timestamp'),r.get('source'),r.get('status'),', '.join(r.get('flags',[]))] for r in context['observations']]) if context['observations'] else 'External reference load failed: '+'; '.join(context['errors']) if context.get('errors') else 'No external reference supplied.']
    lines += ['', '## SPY buy-and-hold comparison','']
    if strategy_summary:
        lines.append(md_table(['Strategy','Cumulative return','CAGR','Volatility','Sharpe rf=0','Max drawdown','Exposure','Opportunity cost vs B&H'],[[s['strategy'],pct(s.get('cumulative_return')),pct(s.get('cagr')),pct(s.get('annualized_volatility')),f"{s['sharpe_rf_zero']:.3f}" if s.get('sharpe_rf_zero') is not None else '—',pct(s.get('max_drawdown')),pct(s.get('exposure')),pct(s.get('opportunity_cost_vs_buy_hold'))] for s in strategy_summary]))
        window=strategy_summary[0].get('comparison_window',{})
        if window:lines.append(f"Common comparison window: {window['start']} through {window['end']}. No history outside this observed intersection is treated as known cash waiting.")
    else:lines.append('UNVERIFIED: SPY adjusted history and valid signals are not available for a same-window comparison.')
    lines += ['', '## Tactical assessment','',assessment['REASON'], '', 'Risk flags: '+', '.join(assessment['RISK_FLAGS']),
              '', '## Assumptions and limits','',
              '- Signal after close; entry at the next session open; horizons from actual entry; holiday targets roll forward. Immature horizons stay unavailable.',
              '- Same-close calendar/session reference returns are source-reconciliation diagnostics only. They never feed executable strategy returns, entry decisions or allocation; 252 sessions is not substituted for the primary calendar-year holding period.',
              '- S&P 500 is a non-investable price index. Its total-return series is unavailable. SPY/QQQ adjusted OHLC produces an approximate dividend-reinvestment proxy, not index total return. Dividend cash is not added twice.',
              '- Drawdown is close-to-close with entry open included; max upside/adverse excursion uses daily high/low. Intraday event order is unknowable.',
              '- Event returns can overlap. Cluster bootstrap and Wilson intervals are descriptive; small samples including 8–19 perfect wins cannot guarantee future success.',
              '- 5/10-session combinations and regimes create multiple comparisons. No parameter search or best-combination selection is performed; no significance claim is made.',
              '- Cash earns zero; signal strategy holds one unlevered SPY position, ignores overlapping entries, and marks open tails to market. Opportunity cost is B&H terminal return minus strategy return.',
              '- Provider revisions and historical universe changes can affect results. No point-in-time certification is implied by a structurally valid file.',
              '', '## Sources','']
    lines += ['- '+c['source'] for c in (claims[0],claims[-1])]
    lines += ['- https://www.mcoscillator.com/learning_center/weekly_chart/zweig_breadth_thrust_signal/',
              '- https://www.nyse.com/trade/hours-calendars','- https://www.cboe.com/tradable-products/vix/vix-historical-data',
              '- https://in.help.yahoo.com/kb/adjusted-close-sln28256.html','', 'The original Zweig book page and original NDR breadth/event archive remain unavailable. See docs/research.md for definition conflicts and acquisition limits.']
    markdown='\n\n'.join(lines)+'\n';(output/'latest.md').write_text(markdown)
    # A small escaped Markdown-like renderer: tables remain exact preformatted text.
    parts=[]
    for block in markdown.split('\n\n'):
        if block.startswith('# '):parts.append('<h1>'+escape(block[2:])+'</h1>')
        elif block.startswith('## '):parts.append('<h2>'+escape(block[3:])+'</h2>')
        elif block.startswith('| '):
            rows=block.splitlines();body=[]
            for j,line in enumerate(rows):
                if j==1:continue
                tag='th' if j==0 else 'td'
                body.append('<tr>'+''.join(f'<{tag}>'+escape(c.strip())+f'</{tag}>' for c in line.strip('|').split('|'))+'</tr>')
            parts.append('<div class="table"><table>'+''.join(body)+'</table></div>')
        else:parts.append('<p>'+escape(block).replace('\n','<br>')+'</p>')
    parts.append('<h2>Observed inputs and hypothetical backtests — charts</h2>')
    for key,b64 in images.items():parts.append(f'<img alt="MBSS chart {key}" src="data:image/png;base64,{b64}">')
    details=escape(json.dumps({'assessment':assessment,'data_quality':quality,'claim_audit':claims},ensure_ascii=False,indent=2,default=str))
    parts.append('<details><summary>Inspectable evidence / provenance</summary><pre>'+details+'</pre></details>')
    style='body{font:15px/1.6 system-ui,sans-serif;max-width:1120px;margin:32px auto;padding:0 24px;color:#18213b;background:#fafbff}h1{color:#203e8b}h2{margin-top:36px}table{border-collapse:collapse;font-size:12px;width:100%}td,th{border:1px solid #d5dced;padding:7px;text-align:left}th{background:#eaf0ff}.table{overflow:auto}img{width:100%;height:auto;margin:16px 0;background:white;border:1px solid #dce2f0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:11px}details{background:#eef2fa;padding:14px}'
    (output/'latest.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(title)+'</title><style>'+style+'</style><body>'+''.join(parts)+'</body></html>')
