import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from mbss.collectors.sources import collect,utc_now
from mbss.pipeline import run
from mbss.c_reference_audit import run_c_audit
from mbss.c_episode_audit import run_episode_audit


def main(argv=None):
    parser=argparse.ArgumentParser(description='MBSS v0.1.3 independent signal research; no automated trading')
    sub=parser.add_subparsers(dest='command',required=True)
    c=sub.add_parser('collect',help='Attempt keyless public price/VIX downloads; never infer NYSE breadth')
    c.add_argument('--input',default='data/normalized');c.add_argument('--start',default='1999-01-01');c.add_argument('--timeout',type=float,default=8)
    c.add_argument('--aux-breadth',action='store_true',help='Collect current SPY traded-holdings breadth proxy; separate from NYSE signals')
    a=sub.add_parser('audit-c',help='Research-only Carson C date comparison; never drives signals or orders')
    a.add_argument('--input-csv',required=True,help='Local dated A/D observations with explicit provenance')
    a.add_argument('--reference-csv',default='docs/reference/carson-2025-04-25-events-as-printed.csv')
    a.add_argument('--source',required=True,help='Original research source label or URL; do not claim NDR comparability')
    a.add_argument('--output',required=True,help='New directory for immutable research outputs')
    a.add_argument('--as-of',default=None,help='Timezone-aware timestamp, default current UTC time')
    e=sub.add_parser('audit-c-episodes',help='Research-only Carson extra C episode windows; cannot drive signals')
    e.add_argument('--input-csv',required=True,help='Lawfully obtained dated observed NYSE A/D CSV')
    e.add_argument('--reference-csv',default='docs/reference/carson-2025-04-25-events-as-printed.csv')
    e.add_argument('--source',required=True,help='Original data publisher and/or URL')
    e.add_argument('--comparison-csv',default=None,help='Optional separate dated source, never auto-spliced')
    e.add_argument('--comparison-source',default=None,help='Required if comparison CSV supplied')
    e.add_argument('--output',required=True)
    e.add_argument('--as-of',default=None)
    r=sub.add_parser('run',help='Validate local inputs and generate an immutable research report')
    r.add_argument('--input',default='data/normalized');r.add_argument('--output')
    r.add_argument('--as-of',default=None,help='UTC timestamp with timezone; default now')
    r.add_argument('--start',default=None);r.add_argument('--config',default='config/default.json')
    r.add_argument('--cost-bps',type=float,default=None);r.add_argument('--seed',type=int,default=None)
    args=parser.parse_args(argv)
    if args.command=='audit-c':
        audit=run_c_audit(args.input_csv,args.reference_csv,args.output,args.source,args.as_of or utc_now())
        print(json.dumps({'output':args.output,'status':audit['status'],
                          'reference_comparable':audit['variants'][0]['comparable_reference_dates'],
                          'SAFE_TO_ACT':False},ensure_ascii=False,indent=2))
        return 0
    if args.command=='audit-c-episodes':
        audit=run_episode_audit(args.input_csv,args.reference_csv,args.output,args.source,
                                args.as_of or utc_now(),
                                comparison_csv=args.comparison_csv,
                                comparison_source=args.comparison_source)
        print(json.dumps({'output':args.output,'status':audit['status'],
                          'focus_statuses':{x['date']:x['status'] for x in audit['focus_cases']},
                          'SAFE_TO_ACT':False},ensure_ascii=False,indent=2))
        return 0
    if args.command=='collect':
        if args.timeout<=0:parser.error('--timeout must be positive')
        attempts=collect(args.input,args.start,args.timeout,aux_breadth=args.aux_breadth)
        print(json.dumps(attempts,ensure_ascii=False,indent=2))
        # Acquisition failure is operationally visible; report generation should still run.
        return 0 if all(a['status']!='FAILED' for a in attempts) else 2
    config_path=Path(args.config);config=json.loads(config_path.read_text()) if config_path.exists() else {}
    output=args.output or 'runs/'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    result=run(args.input,output,args.as_of or utc_now(),args.start or config.get('start','2000-01-01'),
               seed=args.seed if args.seed is not None else config.get('seed',42),
               cost_bps=args.cost_bps if args.cost_bps is not None else config.get('cost_bps_per_side',0),
               bootstrap_draws=config.get('bootstrap_draws',2000),config=config)
    print(json.dumps({'output':str(Path(output).resolve()),'SIGNAL_STATUS':result['assessment']['SIGNAL_STATUS'],'SAFE_TO_ACT':False},indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
