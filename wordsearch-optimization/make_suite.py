import itertools
import json
import math
import random
from pathlib import Path
from test_generate_grid import occurs


def build_suite():
    rng = random.Random(260126)
    cases = [
        dict(name='example-ACE', required=['ACE','FIG','OAK'], forbidden=[]),
        dict(name='example-languages', required=['PYTHON','JAVA','RUBY'], forbidden=['BYTE','HEAP','BUG','OX']),
    ]
    def add(name, req, forb=()):
        cases.append(dict(name=name, required=req, forbidden=list(forb)))
    def random_words(m, lo, hi, letters):
        return [''.join(rng.choice(letters) for j in range(rng.randint(lo,hi))) for i in range(m)]
    for m in (10,25,50,100,200):
        add('random26-short-'+str(m),random_words(m,4,8,'ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
        add('random26-mixed-'+str(m),random_words(m,3,13,'ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
        add('random8-'+str(m),random_words(m,5,9,'ABCDEFGH'))
        # Word-like strings assembled from a fixed inventory of common fragments.
        fragments=['ST','ON','ER','AT','IN','RE','AN','ED','OR','AL','EN','IT','AR','TE','ES','LE']
        req=[]
        while len(req)<m:
            w=''.join(rng.choice(fragments) for j in range(rng.randint(2,5)))
            if w not in req:
                req.append(w)
        add('morphemes-'+str(m),req)
        # Shared literal prefixes/suffixes. Include reversals and duplicates only incidentally.
        roots=random_words(max(5,m//3),3,5,'ACDEILNORSSTU')
        req=[]
        while len(req)<m:
            w=rng.choice(['','RE','UN','IN'])+rng.choice(roots)+rng.choice(['','S','ED','ING'])
            if w not in req:
                req.append(w)
        add('affixes-'+str(m),req)
        # Guaranteed feasible instances: draw words from a planted torus, then
        # select forbidden patterns absent in all eight toroidal directions.
        n=max(7,math.isqrt(m*4)+2)
        planted=[''.join(rng.choice('ABCDEFGH') for c in range(n)) for r in range(n)]
        req=[]
        for _ in range(m):
            r,c=rng.randrange(n),rng.randrange(n)
            dr,dc=rng.choice(((0,1),(1,0),(1,1),(1,-1)))
            length=rng.randint(3,min(n,10))
            req.append(''.join(planted[(r+i*dr)%n][(c+i*dc)%n] for i in range(length)))
        forb=[]
        while len(forb)<50:
            w=''.join(rng.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ') for j in range(rng.randint(2,5)))
            if not occurs(planted,w) and w not in forb:
                forb.append(w)
        add('forbidden-planted-'+str(m),req,forb)
    return cases


if __name__=='__main__':
    suite=build_suite()
    Path('suite_v2.json').write_text(json.dumps(suite,indent=2))
    print('Frozen cases:',len(suite))
