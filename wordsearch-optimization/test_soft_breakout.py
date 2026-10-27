import unittest
from experiments.soft_breakout import solve
from test_generate_grid import valid
class Tests(unittest.TestCase):
    def test_small(self):
        for req,n in [(['ACE','FIG','OAK'],3),(['A','B'],2),(['ABC','CBA','ABC'],3)]:
            self.assertTrue(valid(solve(req,n,0.2,2),req,[]))
if __name__=='__main__':unittest.main()
