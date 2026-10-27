import random
import unittest
import generate_grid_v3 as old
import generate_grid_v4 as new
from test_generate_grid import valid
from unittest.mock import patch

class Tests(unittest.TestCase):
    def test_overlapping_chains_shrink_certified_fallback(self):
        rng = random.Random(82193)
        alphabet = 'ACDEGHILMNOPRSTUY'
        text = ''.join(rng.choice(alphabet) for _ in range(32))
        req = [text[i:i+10] for i in range(20)]
        forb = ['ZZ']
        safe = 'X'
        base = old._compact_fallback(req, req, forb, 10, safe)
        compact = new._overlap_fallback(req, req, forb, 10, safe, len(base))
        self.assertIsNotNone(compact)
        self.assertTrue(valid(compact, req, forb))
        self.assertLess(len(compact), len(base))

    def test_exhausted_search_retains_overlap_incumbent(self):
        rng = random.Random(82193)
        text = ''.join(rng.choice('ACDEGHILMNOPRSTUY') for _ in range(48))
        req = [text[i:i+10] for i in range(32)]
        forb = ['ZZ']
        with patch.object(new._Solver, 'search', return_value=None):
            grid = new.generate_grid(req, forb)
        plain = old._compact_fallback(req, req, forb, 10, 'X')
        self.assertTrue(valid(grid, req, forb))
        self.assertLess(len(grid), len(plain))

    def test_forbidden_junction_rejects_invalid_merge(self):
        req, forbidden = ['ABCD', 'CDEF', 'EFGH'], ['BCDE']
        safe = 'Z'
        base = old._compact_fallback(req, req, forbidden, 4, safe)
        improved = new._overlap_fallback(req, req, forbidden, 4, safe, len(base))
        if improved:
            self.assertTrue(valid(improved, req, forbidden))
        self.assertTrue(valid(base, req, forbidden))

if __name__ == '__main__':
    unittest.main()
