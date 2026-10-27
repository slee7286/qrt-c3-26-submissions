import math
import random
import time
from experiments.soft_search import _Soft
LAST_STATS={}


def solve(words,n,seconds,seed=0,mode=0):
    global LAST_STATS
    start=time.perf_counter();end=start+seconds
    rng=random.Random(seed)
    canon=sorted({min(w,w[::-1]) for w in words if w},key=lambda w:(-len(w),w))
    texts=[]
    for w in canon:
        if not any(w in old or w[::-1] in old for old in texts):texts.append(w)
    state=_Soft(texts,n,rng,'majority')
    order=list(range(len(texts)));rng.shuffle(order);order.sort(key=lambda i:-len(texts[i])*(.75+.5*rng.random()))
    for i in order:state.add(i,*state.candidate(i))
    best=state.energy;snapshot=state.assignments[:];stale=0;iterations=0
    weights=[1]*len(texts)
    while state.energy and time.perf_counter()<end:
        troubled=[i for i,v in enumerate(state.conflicts) if v]
        if mode==0 or (mode==1 and iterations%5==0):
            # Remove a mutually blocking set together instead of moving only one word.
            rng.shuffle(troubled)
            block=set(troubled[:rng.randint(2,max(2,len(troubled)))])
            if mode==0:
                neighbors=0
                for wi in block.copy():
                    d,pos=state.assignments[wi]
                    for p in state.cells(d//2,pos,len(state.words[wi])):
                        neighbors|=state.owners[p]
                near=[]
                while neighbors:
                    bit=neighbors&-neighbors;near.append(bit.bit_length()-1);neighbors^=bit
                rng.shuffle(near);block.update(near[:rng.randrange(1,min(12,len(near))+1)] if near else [])
            else:
                block.update(rng.sample(range(len(texts)),min(len(texts),max(2,len(texts)//10))))
            for i in block:state.remove(i)
            order=list(block);rng.shuffle(order)
            if rng.random()<.6:order.sort(key=lambda i:-len(texts[i])*(.65+.7*rng.random()))
            for i in order:state.add(i,*state.candidate(i,0,compact=rng.random()<.6))
        else:
            wi=rng.choice(troubled) if rng.random()<.65 else rng.randrange(len(texts))
            old=state.assignments[wi];energy=state.energy
            state.remove(wi)
            # Allow larger uphill moves during reheating, unlike one-conflict slack.
            phase=(iterations%160)/160
            slack=rng.choices((0,1,2,3),(65,20,10,5))[0] if phase<.6 else 0
            state.add(wi,*state.candidate(wi,slack,False))
            delta=state.energy-energy;temperature=1.5*(1-phase)+.1
            if delta>0 and rng.random()>=math.exp(-delta/temperature):
                state.remove(wi);state.add(wi,*old)
        iterations+=1
        if state.energy<best:
            best=state.energy;snapshot=state.assignments[:];stale=0
        else:stale+=1
        threshold=15 if mode==0 else 100
        if stale>=threshold:
            for i in range(len(texts)):state.remove(i)
            for i,a in enumerate(snapshot):state.add(i,*a)
            stale=0
    LAST_STATS=dict(best=best,final=state.energy,iterations=iterations,seconds=time.perf_counter()-start)
    return state.grid()
