import random
import time
from generate_grid_v1 import _Solver,_Geometry

class WarmSolver(_Solver):
    def greedy(self,deadline):
        remaining=[wi for wi,p in enumerate(self.placed) if p is None]
        self.rng.shuffle(remaining)
        remaining.sort(key=lambda wi:-len(self.words[wi])*(0.80+0.40*self.rng.random()))
        while remaining:
            if time.perf_counter()>deadline:return False
            options=[]
            for wi in remaining[:4]:
                domains=self.domains(self.words[wi])
                options.append((sum(x.bit_count() for x in domains),wi,domains))
            _,wi,ds=min(options,key=lambda x:x[0])
            self.greedy_place(wi,ds);remaining.remove(wi)
        return all(p is not None for p in self.placed)


def locate(grid,words):
    n=len(grid);geo=_Geometry(n)
    lines=[]
    for d in range(4):
        for base in range(0,n*n,n):
            cells=geo.inverse[d][base:base+n]
            line=''.join(grid[p//n][p%n] for p in cells)
            lines.append((d,base,line+line[:-1]))
    assignments=[]
    for word in words:
        found=None
        for d,base,line in lines:
            for text in (word,word[::-1]):
                pos=line.find(text)
                if 0<=pos<n:
                    found=(geo.cells(d,base+pos,len(text)),tuple(ord(c)-65 for c in text))
                    break
            if found:break
        if found is None:raise ValueError('Word not in source grid')
        assignments.append(found)
    return assignments


def solve_from_grid(words,grid,seconds,seed=0,forbidden=()):
    end=time.perf_counter()+seconds
    n=len(grid)-1
    if n<max(map(len,words),default=1):return None
    rng=random.Random(seed)
    assignments=locate(grid,words)
    oldn=n+1
    rowowners=[0]*oldn;colowners=[0]*oldn
    for wi,(cells,text) in enumerate(assignments):
        bit=1<<wi
        for p in cells:
            r,c=divmod(p,oldn);rowowners[r]|=bit;colowners[c]|=bit
    cuts=[]
    for r in range(oldn):
        for c in range(oldn):
            destroyed=rowowners[r]|colowners[c]
            cuts.append((destroyed.bit_count()+rng.random()*2,r,c,destroyed))
    cuts.sort()
    for attempt,(_,r,c,destroyed) in enumerate(cuts[:8]):
        if time.perf_counter()>=end:return None
        solver=WarmSolver(n,words,forbidden,rng)
        for wi,(cells,text) in enumerate(assignments):
            if destroyed>>wi&1:continue
            newcells=[]
            for p in cells:
                y,x=divmod(p,oldn)
                newcells.append((y-(y>r))*n+x-(x>c))
            solver.add(wi,tuple(newcells),text)
        t=time.perf_counter()
        result=solver.search(min(end,t+max(0.015,seconds*0.25)),max(100,len(words)*5))
        if result is not None:return result
    return None
