import math
import random
import re
import time
from generate_grid_v1 import _Solver, _valid, _patterns


def _score_info(required):
    total=sum(map(len,required))
    lower=max(1,max(map(len,required),default=1))
    bound=min(100.0,100.0*total/(1.7*lower*lower))
    goal=max(lower,math.isqrt(10*total//17))
    return total,lower,bound,goal


def generate_grid(required_words, forbidden_words):
    required=list(required_words)
    forbidden=sorted(set(forbidden_words))
    if any(any(not 'A'<=c<='Z' for c in w) for w in required+forbidden):
        raise ValueError('Words must use uppercase A-Z.')
    if '' in forbidden or len({w for w in forbidden if len(w)==1})==26:
        raise ValueError('Impossible forbidden constraints.')
    forbidden_regex=re.compile('|'.join(_patterns(forbidden,max(map(len,forbidden),default=1)))) if forbidden else None
    if forbidden_regex and any(forbidden_regex.search(w) for w in required):
        raise ValueError('A required word contains a forbidden word or its reverse.')
    canonical=sorted({min(w,w[::-1]) for w in required if w},key=lambda w:(-len(w),w))
    words=[]
    for w in canonical:
        if not any(w in v or w[::-1] in v for v in words):
            words.append(w)
    score_sum,raw_lower,upper_score,score_goal=_score_info(required)
    lower=raw_lower
    letter_counts=[0]*26
    for w in words:
        counts=[0]*26
        for c in w:counts[ord(c)-65]+=1
        letter_counts=[max(a,b) for a,b in zip(letter_counts,counts)]
    lower=max(lower,math.isqrt(max(0,sum(letter_counts)-1))+1)
    if forbidden:
        pats=_patterns(forbidden,lower)
        matcher=re.compile('|'.join(sorted(pats))) if pats else None
        if matcher and any(len(w)==lower and matcher.search(w+w[:-1]) for w in words):
            lower+=1
    goal=max(lower,score_goal)
    reduced_sum=sum(map(len,words))
    start=time.perf_counter()
    budget=min(3.5,0.25+0.014*len(words)+0.001*reduced_sum)
    deadline=start+budget
    rng=random.Random(61789)
    safe=next((c for c in 'ZXQJKVBPYGFWMUCDLHRSNIATOE' if not any(c in w for w in forbidden)),None)
    fallback_n=max(lower,len(words),1) if not forbidden else max(lower+1,2*len(words),1)
    best=None
    # Longest-word-sized instances get first refusal, with cheap bounded probes.
    # This catches nonmonotone forbidden feasibility and immediately optimal cases.
    if reduced_sum<=lower*lower or forbidden:
        probe_deadline=min(deadline,start+budget*0.10)
        probe_stop=min(goal,lower+4) if forbidden else lower
        for n in range(lower,probe_stop+1):
            if time.perf_counter()>=probe_deadline:break
            solver=_Solver(n,words,forbidden,rng)
            grid=solver.search(probe_deadline,max(8,len(words)//3))
            if grid is not None and _valid(grid,required,forbidden):
                best=grid
                break
    if best is not None and len(best)<=goal:
        return best
    # Estimate a useful feasible starting density using the effective alphabet.
    freq=[0]*26
    for w in words:
        for c in w:freq[ord(c)-65]+=1
    concentration=sum(v*v for v in freq)/max(1,reduced_sum*reduced_sum)
    effective=1/max(concentration,1/26)
    packing=1.05+5.0/effective
    n=max(lower,goal,math.ceil(math.sqrt(reduced_sum/packing)))
    while best is None and time.perf_counter()<deadline:
        solver=_Solver(n,words,forbidden,rng)
        grid=solver.search(min(deadline,time.perf_counter()+budget*0.16),max(25,2*len(words)))
        if grid is not None and _valid(grid,required,forbidden):
            best=grid
            break
        n+=1
    if best is not None:
        while len(best)>goal and time.perf_counter()<deadline:
            n=len(best)-1
            solver=_Solver(n,words,forbidden,rng)
            grid=solver.search(min(deadline,time.perf_counter()+max(0.04,budget*0.20)),max(80,8*len(words)))
            if grid is not None and _valid(grid,required,forbidden):
                best=grid
        return best
    if safe is not None:
        n=fallback_n
        rows=[safe*n for _ in range(n)]
        for i,w in enumerate(words):rows[i if not forbidden else 2*i]=w+safe*(n-len(w))
        if _valid(rows,required,forbidden):return rows
    raise RuntimeError('No valid grid found within the search budget.')
