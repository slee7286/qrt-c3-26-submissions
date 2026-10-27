import itertools
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import generate_grid_v2 as v2
from test_generate_grid import valid,occurs

class IterationTests(unittest.TestCase):
    def test_score_bounds_and_examples(self):
        cases=[(['ACE','FIG','OAK'],[],3,100/1.7),(['PYTHON','JAVA','RUBY'],['BYTE','HEAP','BUG','OX'],6,100*14/(36*1.7))]
        for req,forb,n,bound in cases:
            S,L,B,goal=v2._score_info(req)
            self.assertEqual(L,n)
            self.assertAlmostEqual(B,bound)
            grid=v2.generate_grid(req,forb)
            self.assertTrue(valid(grid,req,forb));self.assertEqual(len(grid),n)
    def test_stops_at_full_score_not_only_length_bound(self):
        req=[''.join(pair) for pair in itertools.product('ABCD',repeat=2)]
        grid=['AABB','CCDD','ABCD','ABCD']
        self.assertTrue(valid(grid,req,[]))
        with patch.object(v2._Solver,'search',return_value=grid) as search:
            self.assertEqual(v2.generate_grid(req,[]),grid)
            self.assertEqual(search.call_count,1)
    def test_nonmonotone(self):
        req=['AB','AC','AD','BC','BD','CD']*100
        forb=list('EFGHIJKLMNOPQRSTUVWXYZ')+['AA','BB','CC','DD']
        grid=v2.generate_grid(req,forb)
        self.assertTrue(valid(grid,req,forb));self.assertEqual(len(grid),2)
    def test_planted_fuzz(self):
        rng=random.Random(8126)
        for case in range(90):
            n=rng.randrange(2,8);alpha='ABCD' if case%3 else 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            board=[''.join(rng.choice(alpha) for _ in range(n)) for _ in range(n)]
            req=[]
            for _ in range(rng.randrange(1,16)):
                r,c=rng.randrange(n),rng.randrange(n);dr,dc=rng.choice(((0,1),(1,0),(1,1),(1,-1)))
                req.append(''.join(board[(r+i*dr)%n][(c+i*dc)%n] for i in range(rng.randrange(1,n+1))))
            forb=[]
            for _ in range(18):
                text=''.join(rng.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ') for _ in range(rng.randrange(1,3*n+1)))
                if not occurs(board,text):forb.append(text)
            self.assertTrue(valid(v2.generate_grid(req,forb),req,forb),(case,req,forb))
    def test_exact_starter_main_and_subprocess_io(self):
        root=Path(__file__).parent
        marker="if __name__ == '__main__':"
        self.assertEqual((root/'generate_grid_v2.py').read_text().split(marker,1)[1],(root/'generate_grid_v1.py').read_text().split(marker,1)[1])
        cases=[(['ACE','FIG','OAK'],[]),(['PYTHON','JAVA','RUBY'],['BYTE','HEAP','BUG','OX']),(['ABCD'],['DABC']),(['CAT','DOG'],[c+c for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'])]
        out=root/'io_v2_test_output.txt'
        try:
            for req,forb in cases:
                text='\n'.join([str(len(req))]+req+[str(len(forb))]+forb)+'\n'
                process=subprocess.run([sys.executable,str(root/'generate_grid_v2.py')],input=text,text=True,capture_output=True,env=dict(os.environ,OUTPUT_PATH=str(out)),check=True)
                self.assertFalse(process.stdout);self.assertFalse(process.stderr)
                rows=out.read_text().splitlines();grid=[''.join(row.split()) for row in rows]
                self.assertEqual(rows,[' '.join(row) for row in grid])
                self.assertTrue(valid(grid,req,forb))
        finally:
            if out.exists():out.unlink()

if __name__=='__main__':unittest.main()
