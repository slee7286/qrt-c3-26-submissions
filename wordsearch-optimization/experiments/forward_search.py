import random
import time
from generate_grid_v1 import _Solver,_extreme,_pick

class ForwardSolver(_Solver):
    def __init__(self,n,words,forbidden,rng):
        super().__init__(n,words,forbidden,rng)
        self.domain_all=[[self.geo.all]*8 for _ in words]
        self.local_bad=[]
        self.small=(1<<n)-1
        for w in self.words:
            pair=[]
            for text in (w,w[::-1]):
                masks=[0]*26
                allmask=0
                for i,ch in enumerate(text):
                    bit=1<<((-i)%n)
                    allmask|=bit
                    masks[ch]|=bit
                pair.append([allmask^m for m in masks])
            self.local_bad.append(pair)
        self.nodes=0
        self.best_depth=0
        self.calls=0

    def push_domains(self,cells,word,skip):
        n=self.geo.n;small=self.small
        changed=[]
        mappings=[(self.geo.maps[d][p]//n*n,self.geo.maps[d][p]%n,ch,d) for p,ch in zip(cells,word) for d in range(4)]
        for wi,domains in enumerate(self.domain_all):
            if wi==skip or self.placed[wi] is not None:continue
            previous=domains[:]
            local=self.local_bad[wi]
            for base,k,ch,family in mappings:
                d=family*2
                for rev in (0,1):
                    pattern=local[rev][ch]
                    bad=((pattern<<k)|(pattern>>(n-k)))&small
                    domains[d+rev]&=~(bad<<base)
            if previous!=domains:changed.append((wi,previous))
        return changed

    def pop_domains(self,changed):
        for wi,old in changed:self.domain_all[wi]=old

    def search_forward(self,deadline,node_limit=4000):
        M=len(self.words)
        def visit(depth):
            self.nodes+=1
            if self.nodes>node_limit or time.perf_counter()>deadline:return False
            self.best_depth=max(self.best_depth,depth)
            if depth>getattr(self,'saved_depth',-1):
                self.saved_depth=depth
                self.saved_placed=self.placed[:]
            if depth==M:return True
            remaining=[wi for wi in range(M) if self.placed[wi] is None]
            wi=min(remaining,key=lambda j:(sum(m.bit_count() for m in self.domain_all[j]),-len(self.words[j]),self.rng.random()))
            ds=self.domain_all[wi][:]
            if not any(ds):return False
            word=self.words[wi]
            # Explore a few high-overlap placements. Near-leaf retries get more branches.
            width=8 if depth>M-12 else 3
            for attempt in range(width):
                best=-1;choices=[]
                for d,domain in enumerate(ds):
                    if not domain:continue
                    occupied=self.geo.all^self.blank[d//2]
                    overlap,starts=_extreme(domain,(self.geo.rotate(occupied,k) for k in range(len(word))),True)
                    if overlap>best:best=overlap;choices=[(d,starts)]
                    elif overlap==best:choices.append((d,starts))
                if not choices:return False
                d,starts=self.rng.choice(choices)
                start=_pick(starts,self.rng);ds[d]&=~(1<<start)
                text=word if d%2==0 else word[::-1]
                cells=self.geo.cells(d//2,start,len(word))
                newcells=tuple(p for p in cells if self.board[p]<0)
                if not self.add(wi,cells,text):continue
                changed=self.push_domains(newcells,tuple(self.board[p] for p in newcells),wi)
                if all(any(self.domain_all[j]) for j in remaining if j!=wi) and visit(depth+1):return True
                self.pop_domains(changed);self.remove(wi)
                if time.perf_counter()>=deadline:return False
            return False
        return self.fill() if visit(sum(p is not None for p in self.placed)) else None


def solve_lns(words,n,seconds,seed=0):
    rng=random.Random(seed)
    end=time.perf_counter()+seconds
    base=ForwardSolver(n,words,[],rng)
    base.greedy(end)
    snapshot=base.placed[:]
    best=sum(p is not None for p in snapshot)
    if best==len(words):return base.fill()
    failures=0
    while time.perf_counter()<end:
        for wi in range(len(words)):base.remove(wi)
        for wi,assignment in enumerate(snapshot):
            if assignment is not None:base.add(wi,*assignment)
        missing=[wi for wi,p in enumerate(base.placed) if p is None]
        victims=set()
        rng.shuffle(missing)
        for wi in missing:
            word=base.words[wi]
            choices=[]
            for d in range(8):
                w=word if d%2==0 else word[::-1]
                masks=[base.geo.rotate(base.geo.all^(base.blank[d//2]|base.masks[d//2][ch]),i) for i,ch in enumerate(w)]
                bad,starts=_extreme(base.geo.all,masks,False)
                start=_pick(starts,rng)
                cells=base.geo.cells(d//2,start,len(w))
                owners=0
                for p,ch in zip(cells,w):
                    if base.board[p]>=0 and base.board[p]!=ch:owners|=base.owners[p]
                choices.append((owners.bit_count()+rng.random()*2,owners))
            _,owners=min(choices)
            while owners:
                bit=owners&-owners;victims.add(bit.bit_length()-1);owners^=bit
        placed=[wi for wi,p in enumerate(base.placed) if p is not None and wi not in victims]
        rng.shuffle(placed)
        victims.update(placed[:rng.randrange(1,min(8,len(placed))+1)] if placed else [])
        for wi in victims:base.remove(wi)
        for wi,w in enumerate(base.words):
            base.domain_all[wi]=base.domains(w) if base.placed[wi] is None else [0]*8
        base.saved_depth=-1
        base.nodes=0
        grid=base.search_forward(min(end,time.perf_counter()+max(0.01,seconds*0.05)),max(60,len(victims)*12))
        if grid is not None:return grid
        if base.saved_depth>best:
            snapshot=base.saved_placed[:];best=base.saved_depth;failures=0
        else:failures+=1
        if failures%20==0:
            # Fresh construction keeps a poor first greedy layout from fixing the backbone forever.
            alt=ForwardSolver(n,words,[],rng);alt.greedy(end)
            count=sum(p is not None for p in alt.placed)
            if count>=best:snapshot=alt.placed[:];best=count
    return None


def solve(words,n,seconds,seed=0):
    rng=random.Random(seed)
    end=time.perf_counter()+seconds
    while time.perf_counter()<end:
        solver=ForwardSolver(n,words,[],rng)
        grid=solver.search_forward(min(end,time.perf_counter()+seconds*0.25),max(100,len(words)*5))
        if grid is not None:return grid
    return None
