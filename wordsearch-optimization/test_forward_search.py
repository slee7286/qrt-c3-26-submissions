import random
import unittest
from experiments.forward_search import ForwardSolver,solve
from test_generate_grid import valid

class Tests(unittest.TestCase):
    def test_incremental_domains(self):
        words=['ABC','BCD','DCB','AAA']
        solver=ForwardSolver(4,words,[],random.Random(5))
        changes=solver.push_domains((0,5,14),(0,1,2),skip=-1)
        for p,ch in zip((0,5,14),(0,1,2)):solver.set_cell(p,ch)
        for wi,w in enumerate(solver.words):self.assertEqual(solver.domain_all[wi],solver.domains(w))
        solver.pop_domains(changes)
        self.assertTrue(all(x==solver.geo.all for ds in solver.domain_all for x in ds))
    def test_local_repair(self):
        from experiments.forward_search import solve_lns
        req=['ACE','FIG','OAK']
        grid=solve_lns(req,3,0.2,4)
        self.assertTrue(valid(grid,req,[]))

    def test_solve_sample(self):
        grid=solve(['ACE','FIG','OAK'],3,0.3,5)
        self.assertIsNotNone(grid)
        self.assertTrue(valid(grid,['ACE','FIG','OAK'],[]))

if __name__=='__main__':unittest.main()
