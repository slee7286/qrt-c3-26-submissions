import random
import time
from generate_grid_v1 import _Solver


class MultiSolver(_Solver):
    def greedy(self,deadline):
        remaining=[wi for wi,p in enumerate(self.placed) if p is None]
        self.rng.shuffle(remaining)
        remaining.sort(key=lambda wi:-len(self.words[wi])*(.60+.80*self.rng.random())*(1+0.13*self.hardness[wi]))
        while remaining:
            if time.perf_counter()>deadline:return False
            options=[]
            for wi in remaining[:4]:
                ds=self.domains(self.words[wi]);count=sum(x.bit_count() for x in ds)
                options.append((count/(1+0.05*self.hardness[wi]),wi,ds))
            _,wi,ds=min(options,key=lambda x:x[0])
            self.greedy_place(wi,ds);remaining.remove(wi)
        return all(p is not None for p in self.placed)

    def search(self,deadline,steps):
        self.hardness=[0.0]*len(self.words)
        self.best_count=0;self.restarts=0
        for restart in range(steps):
            if time.perf_counter()>=deadline:return None
            self.restarts+=1
            self.greedy(deadline)
            if all(p is not None for p in self.placed):return self.fill()
            for _ in range(max(2,min(20,len(self.words)//5))):
                missing=[wi for wi,p in enumerate(self.placed) if p is None]
                if not missing:return self.fill()
                if time.perf_counter()>=deadline:return None
                wi=max(missing,key=lambda i:self.hardness[i]+self.rng.random()*2)
                if not self.greedy_place(wi):self.eject(wi)
            self.best_count=max(self.best_count,sum(p is not None for p in self.placed))
            self.hardness=[v*.985+(.5 if p is None else 0) for v,p in zip(self.hardness,self.placed)]
            for wi in range(len(self.words)):self.remove(wi)
        return None


def solve(words,n,seconds,seed=0):
    rng=random.Random(seed);deadline=time.perf_counter()+seconds
    s=MultiSolver(n,words,[],rng)
    return s.search(deadline,1000000)
