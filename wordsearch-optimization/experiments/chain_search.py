import heapq
import math
import random
import time


def pack_chains(words,n,seed=0,mode=0):
    rng=random.Random(seed)
    active={i:w for i,w in enumerate(words)}
    heap=[]
    # Bound all merged strings by a row. Reversal-equivalent joins need 4 cases.
    def pair(i,j):
        a,b=active[i],active[j]
        best=None
        for x,y in ((a,b),(a,b[::-1]),(b,a),(b[::-1],a)):
            low=max(0,len(x)+len(y)-n)
            for k in range(min(len(x),len(y)),low-1,-1):
                if k==0 or x.endswith(y[:k]):
                    text=x+y[k:]
                    score=k+(0.03 if mode==0 else 0.15)*len(text)+rng.random()*(0.8 if mode<2 else 2.0)
                    if best is None or score>best[0]:best=(score,text)
                    break
        if best is not None:heapq.heappush(heap,(-best[0],rng.random(),i,j,best[1]))
    for i in active:
        for j in range(i):pair(j,i)
    count=len(words)
    while len(active)>n and heap:
        _,_,i,j,text=heapq.heappop(heap)
        if i not in active or j not in active:continue
        del active[i];del active[j]
        k=count;count+=1
        active[k]=text
        for j in active:
            if j!=k:pair(j,k)
    if len(active)<=n:return list(active.values())
    return None


def solve(words,n,seconds,seed=0):
    end=time.perf_counter()+seconds
    rng=random.Random(seed)
    while time.perf_counter()<end:
        chains=pack_chains(words,n,rng.randrange(1<<30),rng.randrange(3))
        if chains is not None:
            grid=[w+'Z'*(n-len(w)) for w in chains]
            return grid+['Z'*n]*(n-len(grid))
    return None
