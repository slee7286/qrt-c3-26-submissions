import unittest
import random
from experiments.warm_search import WarmSolver, locate, solve_from_grid
from test_generate_grid import valid

class Tests(unittest.TestCase):
    def test_locate(self):
        req=['ABC','DEF','GHI']
        grid=['ABC','DEF','GHI']
        assignments=locate(grid,req)
        self.assertEqual(len(assignments),3)
        for (cells,text),w in zip(assignments,req):
            self.assertTrue(''.join(grid[p//3][p%3] for p in cells)==''.join(chr(ch+65) for ch in text))
    def test_anchors_preserved(self):
        solver=WarmSolver(4,['ABC','DEF'],[],random.Random(3))
        solver.add(0,(0,1,2),solver.words[0]);original=solver.placed[0]
        import time
        solver.greedy(time.perf_counter()+0.2)
        self.assertEqual(solver.placed[0],original)
        self.assertTrue(valid(solver.fill(),['ABC','DEF'],[]))
    def test_shrink(self):
        grid=['ABCZ','DEFZ','GHIZ','ZZZZ']
        g=solve_from_grid(['ABC','DEF','GHI'],grid,0.3,4)
        self.assertEqual(len(g),3)
        self.assertTrue(valid(g,['ABC','DEF','GHI'],[]))
if __name__=='__main__':unittest.main()
