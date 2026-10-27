import argparse
import importlib
import json
import math
import time
from pathlib import Path
from test_generate_grid import valid

p=argparse.ArgumentParser()
p.add_argument('modules',nargs='+')
p.add_argument('--input',default='suite_v2.json')
p.add_argument('--output',default='paired_v2_results.json')
p.add_argument('--filter',default='')
p.add_argument('--trials',type=int,default=1)
a=p.parse_args()
cases=json.loads(Path(a.input).read_text())
modules=[(name,importlib.import_module(name)) for name in a.modules]
records=[]
for case in cases:
    if a.filter and a.filter not in case['name']:
        continue
    req,forb=case['required'],case['forbidden']
    S=sum(map(len,req));lower=max(map(len,req),default=1)
    bound=100*min(1,S/(lower*lower*1.7))
    for trial in range(a.trials):
        # Alternate execution order to reduce systematic warmup/load effects.
        order=modules if trial%2==0 else modules[::-1]
        for name,module in order:
            t=time.perf_counter()
            error=None
            try:
                grid=module.generate_grid(req,forb)
                runtime=time.perf_counter()-t
                ok=valid(grid,req,forb)
            except Exception as exc:
                error=repr(exc);runtime=time.perf_counter()-t;ok=False;grid=[]
            n=len(grid)
            score=100*min(1,S/(n*n*1.7)) if ok else 0.0
            row=dict(case=case['name'],module=name,trial=trial,M=len(req),S=S,longest=lower,N_lower=lower,N=n,score=score,upper_bound=bound,gap=bound-score,seconds=runtime,valid=ok,error=error)
            records.append(row)
            print(json.dumps(row),flush=True)
            Path(a.output).write_text(json.dumps(records,indent=2))
            if error is None:
                assert ok,(name,case['name'],grid)
for name,_ in modules:
    rows=[r for r in records if r['module']==name]
    print('SUMMARY',name,'valid',sum(r['valid'] for r in rows),'/',len(rows),'mean_score',sum(r['score'] for r in rows)/len(rows),'mean_gap',sum(r['gap'] for r in rows)/len(rows),'seconds',sum(r['seconds'] for r in rows),flush=True)
