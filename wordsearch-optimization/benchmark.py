import json
import random
import time
from pathlib import Path
import generate_grid as ws_opt
from test_generate_grid import valid

cases=json.loads(Path('ws_cases.json').read_text())
rng=random.Random(920)
for count in (400,1000):
    req=[''.join(rng.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ') for _ in range(rng.randrange(4,10))) for i in range(count)]
    cases.append(('scale-random26-'+str(count),req,[]))
results=[]
for name,req,forb in cases:
    t=time.perf_counter()
    grid=ws_opt.generate_grid(req,forb)
    elapsed=time.perf_counter()-t
    ok=valid(grid,req,forb)
    assert ok,(name,grid)
    n=len(grid)
    S=sum(map(len,req))
    bn=max(len(req),max(map(len,req),default=1))
    b=[w+'A'*(bn-len(w)) for w in req]+['A'*bn]*(bn-len(req))
    # A baseline is invalid iff it contains a forbidden word: required words are in rows.
    bv=not any(__import__('test_generate_grid').occurs(b,w) for w in forb)
    rec={'case':name,'M':len(req),'S':S,'N':n,'density':S/(n*n),'score':min(100,100*S/(n*n)/1.7),'seconds':elapsed,'valid':ok,'baseline_N':bn,'baseline_valid':bv,'baseline_score':min(100,100*S/(bn*bn)/1.7) if bv else 0}
    results.append(rec)
    print(json.dumps(rec),flush=True)
Path('ws_final_results.json').write_text(json.dumps(results,indent=2))
print('SUMMARY',len(results),'valid',sum(r['valid'] for r in results),'mean score',sum(r['score'] for r in results)/len(results),'baseline',sum(r['baseline_score'] for r in results)/len(results),'max seconds',max(r['seconds'] for r in results),flush=True)
