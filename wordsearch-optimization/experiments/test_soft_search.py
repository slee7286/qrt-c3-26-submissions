"""Independent eight-direction validation; never imports production geometry."""
import unittest
try:
    from experiments import soft_search
except ImportError:
    soft_search = None


def valid_required(grid, words):
    if not grid or any(len(row) != len(grid) for row in grid):
        return False
    n = len(grid)
    if any(not 'A' <= ch <= 'Z' for row in grid for ch in row):
        return False
    directions = [(dr, dc) for dr in (-1, 0, 1)
                  for dc in (-1, 0, 1) if dr or dc]
    return all(len(w) <= n and any(
        all(grid[(r + i*dr) % n][(c + i*dc) % n] == ch
            for i, ch in enumerate(w))
        for r in range(n) for c in range(n) for dr, dc in directions)
        for w in words)


class SoftSearchTests(unittest.TestCase):
    def test_pairwise_planes_equal_independent_counts(self):
        import random
        import inspect
        self.assertIn('objective', inspect.signature(soft_search._Soft).parameters,
                      'pairwise objective is missing')
        state = soft_search._Soft(['ABCA', 'BCAB', 'CABA'], 4,
                                 random.Random(8), objective='pairwise')
        state.add(0, 0, 0)
        state.add(1, 2, 0)
        for d in range(8):
            word = state.words[2] if d % 2 == 0 else state.words[2][::-1]
            planes = state.cost_planes(word, d // 2)
            for start in range(16):
                actual = sum(((plane >> start) & 1) << j
                             for j, plane in enumerate(planes))
                expected = sum(sum(state.counts[p].values()) - state.counts[p].get(ch, 0)
                               for p, ch in zip(state.cells(d//2, start, 4), word))
                self.assertEqual(actual, expected, (d, start))
        pair_energy = sum(sum(count*(sum(c.values())-count)
                                  for count in c.values())//2 for c in state.counts)
        self.assertEqual(state.pair_energy, pair_energy)
        state.remove(0)
        self.assertEqual(state.pair_energy, 0)

    def test_repair_can_move_off_compact_local_minimum(self):
        import random
        import inspect
        self.assertIn('compact', inspect.signature(soft_search._Soft.candidate).parameters,
                      'repair must be able to sample all equal-cost placements')
        state = soft_search._Soft(['AAAA', 'AAAA'], 4, random.Random(1))
        state.add(0, 0, 0)
        choices = [state.candidate(1, compact=False) for _ in range(20)]
        self.assertTrue(any(any(not state.counts[p] for p in state.cells(d//2, start, 4))
                            for d, start in choices))

    def test_independent_module_validator_rejects_missing_word(self):
        self.assertTrue(callable(getattr(soft_search, 'validate_required', None)),
                        'independent benchmark validator is missing')
        grid = ['ABCA', 'BCAB', 'CABC', 'ABCA']
        words = ['AABC', 'ACBA', 'BBBA']
        self.assertEqual(soft_search.validate_required(grid, words),
                         valid_required(grid, words))
        self.assertFalse(soft_search.validate_required(grid, ['ZZZ']))
        self.assertTrue(soft_search.validate_required(['A'], ['A']))
        self.assertFalse(soft_search.validate_required(['A'], ['AA']))

    def test_edge_cases_and_small_planted_instances(self):
        import random
        for words, n in [([], 1), (['A', 'A'], 1), (['AB', 'BA'], 2),
                         (['ABCD', 'DCBA', 'BC'], 4)]:
            grid = soft_search.solve(words, n, 0.1, 8)
            self.assertTrue(valid_required(grid, words), (words, grid))
        self.assertIsNone(soft_search.solve(['ABCD'], 3, 0.01, 1))
        self.assertIsNone(soft_search.solve(['A', 'B'], 1, 0.01, 1))
        with self.assertRaises(ValueError):
            soft_search.solve(['lower'], 8, 0.01, 1)
        rng = random.Random(31)
        for n in (3, 4, 5):
            planted = [''.join(rng.choice('ABC') for _ in range(n)) for _ in range(n)]
            words = [planted[0], planted[1][::-1],
                     ''.join(planted[r][r] for r in range(n))]
            for objective in ('majority', 'pairwise'):
                grid = soft_search.solve(words, n, 0.2, 8, objective)
                self.assertTrue(valid_required(grid, words), (n, words, grid))

    def test_guided_breakout_penalizes_conflict_cells(self):
        import random
        self.assertTrue(callable(getattr(soft_search._Soft, 'penalize', None)),
                        'guided breakout penalties are missing')
        state = soft_search._Soft(['AAAA', 'BBBB', 'ABBA'], 4,
                                 random.Random(3), objective='guided')
        state.add(0, 0, 0)
        state.add(1, 0, 0)
        self.assertEqual(state.energy, 4)
        state.penalize()
        self.assertEqual(state.guided_energy, 8)
        for d in range(8):
            word = state.words[2] if d % 2 == 0 else state.words[2][::-1]
            planes = state.cost_planes(word, d//2)
            for start in range(16):
                expected = sum(state.penalty[p]*int(state.counts[p].get(ch, 0) <
                               max(state.counts[p].values(), default=0))
                               for p, ch in zip(state.cells(d//2, start, 4), word))
                actual = sum(((plane >> start) & 1) << j
                             for j, plane in enumerate(planes))
                self.assertEqual(actual, expected)
        state.remove(0)
        self.assertEqual(state.guided_energy, 0)
        grid = soft_search.solve(['ABBA', 'BAAB'], 4, 0.1, 3, objective='guided')
        self.assertTrue(valid_required(grid, ['ABBA', 'BAAB']))

    def test_unknown_objective_is_rejected(self):
        with self.assertRaises(ValueError):
            soft_search.solve(['A'], 1, 0.1, 1, objective='typo')

    def test_rotation_and_both_objective_planes_on_overfull_cells(self):
        import random
        rng = random.Random(57)
        for objective in ('majority', 'pairwise'):
            state = soft_search._Soft(['ABBA']*8, 4, rng, objective)
            for wi in range(8):
                state.add(wi, rng.randrange(8), rng.randrange(16))
            for k in range(4):
                bits = rng.getrandbits(16)
                expected = sum(((bits >> (4*r+(c+k) % 4)) & 1) << (4*r+c)
                               for r in range(4) for c in range(4))
                self.assertEqual(state.rotate(bits, k), expected)
            for d in range(8):
                word = state.words[0] if d % 2 == 0 else state.words[0][::-1]
                planes = state.cost_planes(word, d//2)
                for start in range(16):
                    expected = 0
                    for p, ch in zip(state.cells(d//2, start, 4), word):
                        counts = state.counts[p]
                        if objective == 'pairwise':
                            expected += sum(counts.values())-counts.get(ch, 0)
                        else:
                            expected += int(counts.get(ch, 0) < max(counts.values(), default=0))
                    actual = sum(((plane >> start) & 1) << j
                                 for j, plane in enumerate(planes))
                    self.assertEqual(actual, expected, (objective, d, start))
            for wi in rng.sample(range(8), 8):
                state.remove(wi)
            self.assertEqual(state.energy, 0)
            self.assertEqual(state.pair_energy, 0)
            self.assertEqual(state.conflicts, [0]*8)
            self.assertTrue(all(mask == state.all for masks in state.free for mask in masks))

    def test_solve_returns_required_grid(self):
        self.assertTrue(callable(getattr(soft_search, 'solve', None)),
                        'experimental solve API is missing')
        words = ['STONE', 'TONES', 'NOTES', 'ONES', 'TONE', 'STONE']
        grid = soft_search.solve(words, 6, 0.3, 17)
        self.assertTrue(valid_required(grid, words), grid)


if __name__ == '__main__':
    unittest.main()
