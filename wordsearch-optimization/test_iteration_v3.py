import itertools
import json
import random
import unittest
from pathlib import Path
from unittest.mock import patch
import generate_grid_v2 as old
import generate_grid_v3 as new
from test_generate_grid import valid, occurs


def fallback_case():
    rng = random.Random(710677)
    words = [''.join(rng.choice('ACDEGHILMNOPRSTUY') for _ in range(10 if i < 47 else 9)) for i in range(70)]
    return words, ['ZZ']


class IterationV3Tests(unittest.TestCase):
    def test_old_fallback_reproduces_140(self):
        req, forb = fallback_case()
        self.assertEqual(sum(map(len, req)), 677)
        clock = itertools.count(0, .2)
        with patch.object(old._Solver, 'search', return_value=None), patch.object(old.time, 'perf_counter', side_effect=lambda: next(clock)):
            grid = old.generate_grid(req, forb)
        self.assertEqual(len(grid), 140)
        self.assertTrue(valid(grid, req, forb))

    def test_search_exhaustion_keeps_compact_incumbent(self):
        req, forb = fallback_case()
        with patch.object(new._Solver, 'search', return_value=None):
            with patch.object(new, '_TIME_LIMIT', .01):
                grid = new.generate_grid(req, forb)
        self.assertLessEqual(len(grid), 42)
        self.assertTrue(valid(grid, req, forb))
        self.assertTrue(new.LAST_DIAGNOSTICS['fallback_used'])

    def test_fallback_without_forbidden(self):
        req, _ = fallback_case()
        grid = new._compact_fallback(req, req, [], 10, 'Z')
        self.assertLessEqual(len(grid), 30)
        self.assertTrue(valid(grid, req, []))

    def test_separator_boundary_and_long_forbidden(self):
        for req, forb in [(['ABCD'], ['DABC']), (['AB', 'CD', 'EF', 'GH'], ['BC', 'DA', 'AE', 'CG']), (['ABA', 'BAB'], ['ABABABABABAB']), (['A'], ['AA'])]:
            safe = next(c for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if all(c not in w for w in forb))
            grid = new._compact_fallback(req, req, forb, max(map(len, req)), safe)
            self.assertTrue(valid(grid, req, forb), (req, forb, grid))

    def test_examples_and_impossible(self):
        for req, forb, n in [(['ACE','FIG','OAK'], [], 3), (['PYTHON','JAVA','RUBY'], ['BYTE','HEAP','BUG','OX'], 6)]:
            grid = new.generate_grid(req, forb)
            self.assertEqual(len(grid), n)
            self.assertTrue(valid(grid, req, forb))
        for req, forb in [(['ABCD'], ['BC']), (['ABCD'], ['CB']), (['A'], list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')), ([], [''])]:
            with self.assertRaises(ValueError):
                new.generate_grid(req, forb)

    def test_nonmonotone(self):
        req = ['AB','AC','AD','BC','BD','CD'] * 100
        forb = list('EFGHIJKLMNOPQRSTUVWXYZ') + ['AA','BB','CC','DD']
        grid = new.generate_grid(req, forb)
        self.assertEqual(len(grid), 2)
        self.assertTrue(valid(grid, req, forb))

    def test_no_safe_letter(self):
        req = ['CAT', 'DOG']
        forb = [c+c for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ']
        grid = new.generate_grid(req, forb)
        self.assertTrue(valid(grid, req, forb))

    def test_exact_main(self):
        root = Path(__file__).parent
        marker = "if __name__ == '__main__':"
        self.assertEqual((root/'generate_grid_v2.py').read_text().split(marker,1)[1], (root/'generate_grid_v3.py').read_text().split(marker,1)[1])

if __name__ == '__main__':
    unittest.main()
