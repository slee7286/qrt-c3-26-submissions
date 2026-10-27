import unittest
from experiments.schedule_search import generate_grid, _score_info
from test_generate_grid import valid

class Tests(unittest.TestCase):
    def test_score_bounds(self):
        for words,n,S,score in [(['ACE','FIG','OAK'],3,9,100/1.7),(['PYTHON','JAVA','RUBY'],6,14,100*14/(36*1.7)),(['A']*20,1,20,100)]:
            got=_score_info(words)
            self.assertEqual(got[0],S)
            self.assertEqual(got[1],n)
            self.assertAlmostEqual(got[2],score)
    def test_bound_examples(self):
        for req,forb,n in [(['ACE','FIG','OAK'],[],3),(['PYTHON','JAVA','RUBY'],['BYTE','HEAP','BUG','OX'],6)]:
            grid=generate_grid(req,forb)
            self.assertTrue(valid(grid,req,forb))
            self.assertEqual(len(grid),n)
    def test_nonmonotone_sizes(self):
        req=['AB','AC','AD','BC','BD','CD']*100
        forb=list('EFGHIJKLMNOPQRSTUVWXYZ')+['AA','BB','CC','DD']
        grid=generate_grid(req,forb)
        self.assertTrue(valid(grid,req,forb))
        self.assertEqual(len(grid),2)

if __name__=='__main__':unittest.main()
