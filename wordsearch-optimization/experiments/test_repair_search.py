"""Independent tests for the experimental consistent-word repair search."""
import random
import time
import unittest

from generate_grid import _Solver
from test_generate_grid import valid

try:
    from experiments.repair_search import RepairSolver, solve
except ImportError:
    RepairSolver = solve = None


class RepairTests(unittest.TestCase):
    def test_solve_interface_returns_independently_valid_grid(self):
        self.assertIsNotNone(solve, 'experimental solve must be implemented')
        words = ['ACE', 'FIG', 'OAK', 'CAT']
        grid = solve(words, 5, 0.2, 17)
        self.assertTrue(valid(grid, words, []), grid)

    def test_candidates_minimize_distinct_owners_over_all_starts(self):
        self.assertIsNotNone(RepairSolver)
        rng = random.Random(125)
        words = ['ABCD', 'DABC', 'ABBA', 'CCAD', 'BCDA', 'DACB', 'ABCD']
        solver = RepairSolver(4, words, [], rng)
        for wi in range(len(words) - 1):
            solver.greedy_place(wi)
        expected = 100
        for direction in range(8):
            word = solver.words[-1][::1 if direction % 2 == 0 else -1]
            for start in range(16):
                cells = solver.geo.cells(direction // 2, start, len(word))
                victims = 0
                for p, ch in zip(cells, word):
                    if solver.board[p] >= 0 and solver.board[p] != ch:
                        victims |= solver.owners[p]
                expected = min(expected, victims.bit_count())
        candidates = solver.conflict_candidates(len(words) - 1)
        self.assertTrue(candidates)
        self.assertEqual(min(c[3].bit_count() for c in candidates), expected)
        for _, cells, word, victims in candidates:
            actual = 0
            for p, ch in zip(cells, word):
                if solver.board[p] >= 0 and solver.board[p] != ch:
                    actual |= solver.owners[p]
            self.assertEqual(victims, actual)

    def test_reinsert_places_multiple_pending_words(self):
        self.assertIsNotNone(RepairSolver)
        words = ['ABCD', 'EFGH', 'IJKL', 'MNOP']
        solver = RepairSolver(4, words, [], random.Random(31))
        self.assertTrue(solver.greedy_place(0))
        self.assertTrue(solver.reinsert([1, 2, 3], time.perf_counter() + 0.5))
        self.assertTrue(valid(solver.fill(), words, []))

    def test_failed_repair_rolls_back_board_owners_and_assignments(self):
        self.assertIsNotNone(RepairSolver)
        words = ['AAA', 'BBB', 'CCC', 'DDD']
        solver = RepairSolver(3, words, [], random.Random(11))
        for wi in range(3):
            self.assertTrue(solver.add(wi, tuple(range(wi*3, wi*3+3)), solver.words[wi]))
        before = (solver.board[:], solver.owners[:], solver.placed[:],
                  [mask[:] for mask in solver.masks], solver.blank[:])
        self.assertFalse(solver.repair(3, time.perf_counter() + 0.5))
        self.assertEqual(before, (solver.board, solver.owners, solver.placed,
                                  solver.masks, solver.blank))

    def test_search_exercises_transactional_repair_and_keeps_best(self):
        self.assertIsNotNone(RepairSolver)
        solver = RepairSolver(3, ['AAA', 'BBB', 'CCC', 'DDD'], [], random.Random(4))
        self.assertIsNone(solver.search(time.perf_counter() + 0.03, 100))
        self.assertGreater(solver.stats['repairs'], 0)
        self.assertEqual(solver.stats['best'], 3)
        self.assertEqual(sum(item is not None for item in solver.placed), 3)
        self.assertConsistent(solver)

    def assertConsistent(self, solver):
        expected = [-1] * solver.geo.size
        owners = [0] * solver.geo.size
        for wi, assignment in enumerate(solver.placed):
            if assignment is None:
                continue
            for p, ch in zip(*assignment):
                self.assertIn(expected[p], (-1, ch))
                expected[p] = ch
                owners[p] |= 1 << wi
        self.assertEqual(expected, solver.board)
        self.assertEqual(owners, solver.owners)
        reference = _Solver(solver.geo.n, ['A'], [], random.Random(0))
        for p, ch in enumerate(expected):
            reference.set_cell(p, ch)
        self.assertEqual(reference.masks, solver.masks)
        self.assertEqual(reference.blank, solver.blank)

    def test_reinsert_can_relocate_a_conflict_chain(self):
        self.assertIsNotNone(RepairSolver)
        words = ['BEAE', 'EFEA', 'DDCC', 'CAFE', 'FBBE', 'EDCA',
                 'EAFA', 'EBEF', 'DEAF', 'ECEB']
        solver = RepairSolver(5, words, [], random.Random(1))
        solver.greedy(time.perf_counter() + 1)
        self.assertIsNone(solver.placed[0])
        snapshot = solver.placed[:]
        self.assertFalse(solver.reinsert([0], time.perf_counter() + 1))
        self.assertEqual(snapshot, solver.placed)
        self.assertTrue(solver.reinsert([0], time.perf_counter() + 1,
                                       chain_depth=3, width=4, nodes=200))
        self.assertTrue(valid(solver.fill(), words, []))

    def test_benchmark_reports_paired_equal_budget_valid_runs(self):
        import experiments.repair_search as module
        self.assertTrue(hasattr(module, 'benchmark'), 'paired benchmark is missing')
        records = module.benchmark([('easy', ['AB', 'CD'], [])],
                                   {'easy': 3}, 0.1, [3, 4])
        self.assertEqual(len(records), 4)
        self.assertEqual({record['solver'] for record in records},
                         {'_Solver', 'RepairSolver'})
        self.assertTrue(all(record['valid'] for record in records))
        self.assertTrue(all(record['budget'] == 0.1 for record in records))
        self.assertEqual({record['seed'] for record in records}, {3, 4})

    def test_owner_conflicts_beat_minimum_cell_mismatch_fixture(self):
        words = ['DCCC', 'BCAA', 'BDDC', 'CDBA', 'BBBB', 'CAAC',
                 'DADB', 'DCAD', 'CACA', 'DCAD', 'BABB', 'CACA']
        solver = RepairSolver(4, words, [], random.Random(17))
        # These are fixed consistent placements, independent of greedy policy.
        assignments = [(11, 12, 1, 6), (7, 6, 5, 4), (7, 11, 15, 3),
                       (10, 15, 0, 5), (2, 7, 8, 13), (3, 4, 9, 14)]
        for wi, cells in enumerate(assignments):
            self.assertTrue(solver.add(wi, cells, solver.words[wi]))
        mismatch_costs = []
        for direction in range(8):
            word = solver.words[-1][::1 if direction % 2 == 0 else -1]
            for start in range(16):
                victims = mismatches = 0
                for p, ch in zip(solver.geo.cells(direction // 2, start, 4), word):
                    if solver.board[p] >= 0 and solver.board[p] != ch:
                        victims |= solver.owners[p]
                        mismatches += 1
                mismatch_costs.append((mismatches, victims.bit_count()))
        minimum = min(cost[0] for cost in mismatch_costs)
        self.assertEqual(min(cost[1] for cost in mismatch_costs if cost[0] == minimum), 2)
        self.assertEqual(min(c[3].bit_count() for c in solver.conflict_candidates(11)), 1)

    def test_protected_candidates_cannot_evict_locked_words(self):
        solver = RepairSolver(3, ['AAA', 'BBB', 'CCC', 'DDD'], [], random.Random(2))
        for wi in range(3):
            solver.add(wi, tuple(range(wi*3, wi*3+3)), solver.words[wi])
        self.assertEqual(solver.conflict_candidates(3, protected=7), [])
        self.assertEqual(solver.conflict_candidates(3, limit=0), [])

    def test_expired_or_exhausted_chain_is_transactional(self):
        words = ['BEAE', 'EFEA', 'DDCC', 'CAFE', 'FBBE', 'EDCA',
                 'EAFA', 'EBEF', 'DEAF', 'ECEB']
        for kwargs in ({'nodes': 0}, {'nodes': 1}, {'protected': (1 << 10) - 1}):
            solver = RepairSolver(5, words, [], random.Random(1))
            solver.greedy(time.perf_counter() + 1)
            snapshot = solver.placed[:]
            self.assertFalse(solver.reinsert([0], time.perf_counter() + 1,
                                             chain_depth=3, **kwargs))
            self.assertEqual(snapshot, solver.placed)
            self.assertConsistent(solver)
        self.assertFalse(solver.reinsert([0], time.perf_counter() - 1, chain_depth=3))
        self.assertEqual(snapshot, solver.placed)

    def test_edge_sizes_and_duplicate_words(self):
        for words, n in (([], 1), (['A', 'A', ''], 1), (['AB', 'BA'], 2)):
            self.assertTrue(valid(solve(words, n, 0.1, 3), words, []))
        self.assertIsNone(solve(['ABCD'], 3, 0.1, 0))
        self.assertIsNone(solve(['A'], 0, 0.1, 0))
        self.assertIsNone(solve(['ABC'], 3, 0.0, 0))

    def test_planted_fuzz_returns_no_invalid_grids_and_preserves_state(self):
        rng = random.Random(714)
        for n in range(2, 7):
            for seed in range(4):
                planted = [''.join(rng.choice('ABCDE') for _ in range(n)) for _ in range(n)]
                words = []
                for _ in range(n*2):
                    r, c = rng.randrange(n), rng.randrange(n)
                    dr, dc = rng.choice(((1, 0), (0, 1), (1, 1), (1, -1)))
                    words.append(''.join(planted[(r+i*dr) % n][(c+i*dc) % n]
                                         for i in range(rng.randint(1, n))))
                solver = RepairSolver(n, words, [], random.Random(seed))
                grid = solver.search(time.perf_counter() + 0.02, 30)
                if grid is not None:
                    self.assertTrue(valid(grid, words, []), (n, seed, grid))
                    self.assertEqual(solver.stats['best'], len(words))
                else:
                    self.assertConsistent(solver)


if __name__ == '__main__':
    unittest.main()
