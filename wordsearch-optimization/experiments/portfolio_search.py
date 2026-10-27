import random
import time
from generate_grid_v1 import _Solver

class PortfolioSolver(_Solver):
    def search(self,deadline,steps):
        self.greedy(deadline)
        best=sum(p is not None for p in self.placed)
        snapshot=self.placed[:]
        stale=0;shakes=0
        for step in range(max(steps,100000)):
            missing=[i for i,p in enumerate(self.placed) if p is None]
            if not missing:return self.fill()
            if time.perf_counter()>=deadline:return None
            wi=max(missing,key=lambda i:self.weights[i]+self.rng.random()*.8)
            self.weights[wi]=min(6.0,self.weights[wi]+.15)
            if not self.greedy_place(wi):self.eject(wi)
            count=sum(p is not None for p in self.placed)
            if count>best:
                best=count;snapshot=self.placed[:];stale=0;shakes=0
            else:stale+=1
            if stale>=max(20,len(self.words)//2) or count<best-max(2,len(self.words)//40):
                for j in range(len(self.words)):self.remove(j)
                shakes+=1
                if shakes%4:
                    for j,assignment in enumerate(snapshot):
                        if assignment is not None:self.add(j,*assignment)
                    occupied=[j for j,p in enumerate(self.placed) if p is not None]
                    self.rng.shuffle(occupied)
                    for j in occupied[:min(len(occupied),2+shakes)]:self.remove(j)
                    pending=[j for j,p in enumerate(self.placed) if p is None]
                    self.rng.shuffle(pending)
                    pending.sort(key=lambda j:-len(self.words[j])*(.7+.6*self.rng.random()))
                    for j in pending:self.greedy_place(j)
                else:
                    self.greedy(deadline)
                count=sum(p is not None for p in self.placed)
                if count>best:best=count;snapshot=self.placed[:];shakes=0
                stale=0
        return None
