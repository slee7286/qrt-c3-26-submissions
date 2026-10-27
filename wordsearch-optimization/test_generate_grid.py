import random
import unittest
from generate_grid import generate_grid, _Geometry, _Solver, _valid

D = [(dr,dc) for dr in (-1,0,1) for dc in (-1,0,1) if dr or dc]
def occurs(g,w):
    n=len(g)
    return any(all(g[(r+i*dr)%n][(c+i*dc)%n]==ch for i,ch in enumerate(w))
               for r in range(n) for c in range(n) for dr,dc in D)
def valid(g,req,forb):
    return bool(g) and len(g)>=max(map(len,req),default=1) and all(len(x)==len(g) and all('A'<=c<='Z' for c in x) for x in g) and all(occurs(g,w) for w in req) and not any(occurs(g,w) for w in forb)

class Tests(unittest.TestCase):
    def test_popcount(self):
        import generate_grid as ws_opt
        for n in (0, 1, 127, 1 << 300, (1 << 200)-1):
            self.assertEqual(ws_opt._popcount(n), bin(n).count('1'))

    def test_wrap_bitset_rotation(self):
        rng=random.Random(42)
        for n in range(1,9):
            geo=_Geometry(n)
            for _ in range(5):
                mask=rng.getrandbits(n*n)
                for k in range(n):
                    expected=sum(((mask >> (line*n+(i+k)%n))&1) << (line*n+i) for line in range(n) for i in range(n))
                    self.assertEqual(geo.rotate(mask,k),expected)
    def test_domains_equal_bruteforce(self):
        rng=random.Random(34)
        for n in range(2,8):
            sol=_Solver(n,['ABC'],[],rng)
            for p in range(n*n):
                if rng.random()<0.55:
                    sol.set_cell(p,rng.randrange(3))
            for text in ('A','AB','ABC'[:n]):
                candidates=sol.domains(tuple(ord(c)-65 for c in text))
                expected=0
                for direction,mask in enumerate(candidates):
                    family=direction//2
                    word=text if direction%2==0 else text[::-1]
                    for start in range(n*n):
                        cells=sol.geo.cells(family,start,len(word))
                        ok=all(sol.board[p]<0 or sol.board[p]==ord(c)-65 for p,c in zip(cells,word))
                        self.assertEqual(bool((mask>>start)&1),ok)
    def test_examples(self):
        for req,forb in [(['ACE','FIG','OAK'],[]),(['A','B','A'],[]),(['CAT','TAC'],['AAA','CATC']),(['ABCD'],['DABC']),(['A'],['AA']),([],['A','BB']),(['ABAB'],['ABAABA']),(['ABC'],['CBACBA'])]:
            if (req,forb) in [(['ABCD'],['DABC']),(['A'],['AA']),(['ABC'],['CBACBA'])]:
                # Feasible only with N larger than longest required, in some cases.
                pass
            g=generate_grid(req,forb)
            self.assertTrue(valid(g,req,forb),(req,forb,g))
    def test_impossible(self):
        for req,forb in [(['CAT'],['AT']),(['ABC'],['CBA']),(['A'],['A']),([],[''])]:
            with self.assertRaises(ValueError):
                generate_grid(req,forb)
    def test_nonmonotone_feasibility_with_duplicates(self):
        req=['AB','AC','AD','BC','BD','CD']*100
        forbidden=list('EFGHIJKLMNOPQRSTUVWXYZ')+['AA','BB','CC','DD']
        grid=generate_grid(req,forbidden)
        self.assertTrue(valid(grid,req,forbidden))
        self.assertEqual(len(grid),2)

    def test_all_singletons_forbidden_is_impossible(self):
        with self.assertRaises(ValueError):
            generate_grid([],list('ABCDEFGHIJKLMNOPQRSTUVWXYZ'))

    def test_independent_validator(self):
        rng=random.Random(743)
        for n in range(1,7):
            for _ in range(15):
                g=[''.join(rng.choice('ABC') for _ in range(n)) for r in range(n)]
                req=[''.join(rng.choice('ABC') for _ in range(rng.randint(1,n))) for _ in range(3)]
                forb=[''.join(rng.choice('ABC') for _ in range(rng.randint(1,3*n))) for _ in range(4)]
                self.assertEqual(_valid(g,req,forb),valid(g,req,forb))

if __name__=='__main__':
    unittest.main()
