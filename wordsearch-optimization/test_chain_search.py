import unittest
from experiments.chain_search import pack_chains, solve
from test_generate_grid import valid

class Tests(unittest.TestCase):
    def test_shared_chain(self):
        words=['ABCDE','DEFG','FGHI']
        chains=pack_chains(words,9,3)
        self.assertIsNotNone(chains)
        self.assertTrue(all(any(w in c or w[::-1] in c for c in chains) for w in words))
    def test_sample(self):
        grid=solve(['ACE','FIG','OAK'],3,0.2,3)
        self.assertTrue(valid(grid,['ACE','FIG','OAK'],[]))
if __name__=='__main__':unittest.main()
