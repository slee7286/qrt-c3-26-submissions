"""Independent read-only V2 audit and proposed compact shelf geometry checks.
Run python -B audit_v3.py; the only output file is audit_v3_results.json.
Does not import repository tests or modify solver code.
"""
import importlib.util
import itertools
import json
import random
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('audited_v2', ROOT / 'generate_grid_v2.py')
v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2)
DIRECTIONS = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc]
RESULTS = {'checks': {}, 'counterexamples': {}, 'failures': []}


def check(ok, detail):
    if not ok:
        RESULTS['failures'].append(detail)
        raise AssertionError(detail)


def observed(grid, length):
    n = len(grid)
    return {''.join(grid[(r + i * dr) % n][(c + i * dc) % n] for i in range(length))
            for r in range(n) for c in range(n) for dr, dc in DIRECTIONS}


def independent_valid(grid, required, forbidden):
    n = len(grid)
    if not n or n < max(map(len, required), default=1):
        return False
    if any(len(row) != n or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' for c in row) for row in grid):
        return False
    by_length = {length: observed(grid, length) for length in {len(w) for w in required + forbidden}}
    return all(w in by_length[len(w)] for w in required) and not any(w in by_length[len(w)] for w in forbidden)


def reduce_required(required):
    # Mirrors only the proposed preprocessing rule; retained correctness is
    # verified using original required words and an independent 8-ray oracle.
    reduced = []
    for w in sorted({min(w, w[::-1]) for w in required if w}, key=lambda w: (-len(w), w)):
        if not any(w in v or w[::-1] in v for v in reduced):
            reduced.append(w)
    return reduced


def shelf(required, n, separated=True):
    words = reduce_required(required)
    bins = []
    for word in sorted(words, key=lambda w: (-len(w), w)):
        needed = len(word) + int(separated)
        if needed > n:
            return None
        candidates = [(n - load - needed, i) for i, (load, _) in enumerate(bins) if load + needed <= n]
        if candidates:
            _, i = min(candidates)
            load, contents = bins[i]
            bins[i] = (load + needed, contents + word + ('Z' if separated else ''))
        else:
            bins.append((needed, word + ('Z' if separated else '')))
    capacity = n // 2 if separated else n
    if len(bins) > capacity:
        return None
    grid = ['Z' * n for _ in range(n)]
    for i, (_, content) in enumerate(bins):
        grid[2 * i if separated else i] = content.ljust(n, 'Z')
    return grid


def assert_isolation(grid, required):
    """Check every maximal safe-free 8-direction run is a required substring.

    Bounding a run by N+1 samples proves it cannot wind indefinitely. All
    forbiddens over non-Z letters, of any finite length, are thereby covered.
    """
    n = len(grid)
    containers = required + [w[::-1] for w in required]
    for r in range(n):
        for c in range(n):
            for dr, dc in DIRECTIONS:
                run = ''
                for i in range(n + 1):
                    ch = grid[(r + i * dr) % n][(c + i * dc) % n]
                    if ch == 'Z':
                        break
                    run += ch
                else:
                    check(False, {'unbounded_safe_free_run': grid})
                check(not run or any(run in w for w in containers),
                      {'unexpected_run': run, 'grid': grid, 'required': required})
    check(independent_valid(grid, required, []), {'missing_required': required, 'grid': grid})


def test_shelves():
    words = [''.join(chars) for k in range(1, 4) for chars in itertools.product('AB', repeat=k)]
    separated_count = plain_count = 0
    inputs = 0
    for count in range(5):
        for subset in itertools.combinations(words, count):
            # Originals include empty, reversed, duplicated and substring words.
            required = list(subset) + [w[::-1] for w in subset] + list(subset) + ['']
            if subset:
                required += [subset[-1][:-1], subset[-1][1:]]
            reduced = reduce_required(required)
            longest = max(map(len, required), default=0)
            last = max(longest + 1, 2 * len(reduced), 2)
            upper_grid = shelf(required, last)
            check(upper_grid is not None, {'missing_upper_bound': required, 'n': last})
            for n in range(max(1, longest + 1), last + 3):
                grid = shelf(required, n)
                if grid is not None:
                    assert_isolation(grid, required)
                    separated_count += 1
            upper_plain = max(longest, len(reduced), 1)
            check(shelf(required, upper_plain, False) is not None, {'missing_plain_upper': required})
            for n in range(max(1, longest), upper_plain + 2):
                grid = shelf(required, n, False)
                if grid is not None:
                    check(independent_valid(grid, required, []), {'plain_missing': required, 'n': n})
                    plain_count += 1
            inputs += 1
    # Safe letter may itself occur in required words; isolation remains valid.
    for required in (['AZB', 'ZZ', 'ZA'], ['Z'], ['AZ', 'BZ', 'CZZD'], []):
        for n in range(max(map(len, required), default=0) + 1, 12):
            grid = shelf(required, n)
            if grid is not None:
                assert_isolation(grid, required)
                separated_count += 1
    RESULTS['checks']['shelf_exhaustive'] = dict(input_multisets=inputs,
        separated_grids=separated_count, no_forbidden_grids=plain_count,
        scope='All subsets of size 0..4 from binary words of lengths 1..3; all indicated sides; original reversal/duplicate/substrings retained in oracle.')


def test_validator():
    comparisons = 0
    boards = 0
    for n, alphabet in ((1, 'ABZ'), (2, 'ABZ'), (3, 'AB')):
        candidates = [''.join(p) for k in range(1, 2 * n + 3) for p in itertools.product('AB', repeat=k)]
        for cells in itertools.product(alphabet, repeat=n * n):
            grid = [''.join(cells[r * n:(r + 1) * n]) for r in range(n)]
            by_length = {k: observed(grid, k) for k in range(1, 2 * n + 3)}
            for word in candidates:
                expected = word not in by_length[len(word)]
                actual = v2._valid(grid, [], [word])
                check(actual == expected, {'validator_disagreement': grid, 'forbidden': word})
                comparisons += 1
                if len(word) <= n:
                    expected_required = word in by_length[len(word)]
                    check(v2._valid(grid, [word], []) == expected_required,
                          {'required_validator_disagreement': grid, 'required': word})
                    comparisons += 1
            boards += 1
    rng = random.Random(9543)
    for n in range(1, 9):
        for _ in range(30):
            grid = [''.join(rng.choice('ABCZ') for _ in range(n)) for _ in range(n)]
            required = [''.join(rng.choice('ABCZ') for _ in range(rng.randrange(0, n + 1))) for _ in range(3)]
            forbidden = [''.join(rng.choice('ABCZ') for _ in range(rng.randrange(1, 4 * n + 1))) for _ in range(5)]
            check(v2._valid(grid, required, forbidden) == independent_valid(grid, required, forbidden),
                  {'random_validator_disagreement': grid, 'required': required, 'forbidden': forbidden})
            comparisons += 1
            boards += 1
    RESULTS['checks']['validator'] = dict(boards=boards, comparisons=comparisons,
        exhaustive='Every ABC-safe grid for N=1,2; every binary grid for N=3; every binary forbidden of lengths 1..2N+2; required of lengths <=N.',
        random='240 additional grids, mixed lists, N=1..8, forbidden lengths up to 4N.')


def test_solver_internals():
    rng = random.Random(7584)
    domains = rotations = legal_checks = 0
    for n in range(1, 9):
        for _ in range(8):
            required = [''.join(rng.choice('ABC') for _ in range(rng.randrange(1, n + 1)))]
            forbidden = [''.join(rng.choice('ABC') for _ in range(rng.randrange(1, 3 * n + 1))) for _ in range(4)]
            sol = v2._Solver(n, required, forbidden, rng)
            for p in range(n * n):
                if rng.random() < 0.6:
                    sol.set_cell(p, rng.randrange(3))
            mask = rng.getrandbits(n * n)
            for k in range(n):
                expected = sum(((mask >> (a * n + (j + k) % n)) & 1) << (a * n + j)
                               for a in range(n) for j in range(n))
                check(sol.geo.rotate(mask, k) == expected, {'rotate_failure': n, 'k': k})
                rotations += 1
            word = tuple(ord(c) - 65 for c in required[0])
            for d, mask in enumerate(sol.domains(word)):
                w = word if d % 2 == 0 else word[::-1]
                for start in range(n * n):
                    cells = sol.geo.cells(d // 2, start, len(w))
                    expected = all(sol.board[p] in (-1, ch) for p, ch in zip(cells, w))
                    check(bool(mask & (1 << start)) == expected, {'domain_failure': n, 'word': word})
                    domains += 1
            # '[' is a genuinely unknown symbol, never a literal forbidden letter.
            grid = sol.grid()
            expected = not any(w in observed(grid, len(w)) for w in forbidden)
            check(sol.legal(range(n * n)) == expected, {'partial_legal_failure': n, 'forbidden': forbidden})
            legal_checks += 1
    RESULTS['checks']['solver_internals'] = dict(domain_start_comparisons=domains,
        block_rotations=rotations, partial_board_legality=legal_checks)


def test_solver_transitions():
    rng = random.Random(8493)
    transitions = fills = searches = returned_grids = 0
    for trial in range(72):
        n = 1 + trial % 6
        required = [''.join(rng.choice('ABCD') for _ in range(rng.randrange(1, n + 1)))
                    for _ in range(rng.randrange(1, 10))]
        forbidden = ([c + c for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'] if trial % 3 == 0 else
                     [''.join(rng.choice('ABCD') for _ in range(rng.randrange(2, 2 * n + 2)))
                      for _ in range(3)])
        sol = v2._Solver(n, required, forbidden, rng)
        for step in range(50):
            placed = [i for i, p in enumerate(sol.placed) if p is not None]
            missing = [i for i, p in enumerate(sol.placed) if p is None]
            if placed and (not missing or rng.random() < 0.25):
                sol.remove(rng.choice(placed))
            elif missing:
                wi = rng.choice(missing)
                if rng.random() < 0.5:
                    sol.greedy_place(wi)
                else:
                    sol.eject(wi)
            expected_owners = [0] * (n * n)
            for wi, assignment in enumerate(sol.placed):
                if assignment is not None:
                    cells, word = assignment
                    check(all(sol.board[p] == ch for p, ch in zip(cells, word)),
                          {'lost_placement': trial, 'step': step, 'word': wi})
                    for p in cells:
                        expected_owners[p] |= 1 << wi
            check(expected_owners == sol.owners, {'owner_mismatch': trial, 'step': step})
            check(all(bool(owner) == (ch >= 0) for owner, ch in zip(sol.owners, sol.board)),
                  {'ownership_board_mismatch': trial, 'step': step})
            grid = sol.grid()
            check(not any(w in observed(grid, len(w)) for w in forbidden),
                  {'forbidden_after_transition': trial, 'step': step, 'grid': grid})
            transitions += 1
        if all(p is not None for p in sol.placed):
            grid = sol.fill()
            if grid is not None:
                check(independent_valid(grid, required, forbidden), {'invalid_fill': trial, 'grid': grid})
                fills += 1
        searcher = v2._Solver(n, required, forbidden, rng)
        grid = searcher.search(time.perf_counter() + 0.01, 20)
        searches += 1
        if grid is not None:
            check(independent_valid(grid, required, forbidden), {'invalid_search_result': trial, 'grid': grid})
            returned_grids += 1
    RESULTS['checks']['solver_transitions'] = dict(transitions=transitions,
        valid_fills=fills, real_searches=searches, independently_valid_search_grids=returned_grids,
        note='Search success count is wall-clock dependent; every observed return was independently checked.')


def test_fallback_branches():
    clock_calls = 0
    def expired_clock():
        nonlocal clock_calls
        clock_calls += 1
        return 0.0 if clock_calls == 1 else 1000000.0
    required, forbidden = ['AB', 'CD', 'EF', 'GH', 'IJ', 'KL'], ['AA']
    with patch.object(v2.time, 'perf_counter', side_effect=expired_clock):
        grid = v2.generate_grid(required, forbidden)
    check(independent_valid(grid, required, forbidden), {'forced_fallback_invalid': grid})
    check(len(grid) == 12, {'unexpected_legacy_side': len(grid)})
    compact = shelf(required, 6)
    check(independent_valid(compact, required, forbidden), {'compact_invalid': compact})
    clock_calls = 0
    forbidden_no_safe = [c + c for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ']
    witness = ['AB', 'CD']
    check(independent_valid(witness, ['A'], forbidden_no_safe), 'no-safe witness invalid')
    with patch.object(v2.time, 'perf_counter', side_effect=expired_clock):
        try:
            v2.generate_grid(['A'], forbidden_no_safe)
        except RuntimeError as exc:
            error = str(exc)
        else:
            check(False, 'expected skipped-search no-safe RuntimeError')
    clock = {'expired': False}
    def now():
        return 1000000.0 if clock['expired'] else 0.0
    def invalid_search(*args):
        clock['expired'] = True
        return ['B']
    with patch.object(v2.time, 'perf_counter', side_effect=now), patch.object(v2._Solver, 'search', side_effect=invalid_search):
        rejected = v2.generate_grid(['A'], ['BB'])
    check(independent_valid(rejected, ['A'], ['BB']), {'invalid_candidate_accepted': rejected})
    RESULTS['checks']['forced_branch_tests'] = dict(legacy_fallback_grid=grid,
        no_safe_feasible_witness=witness, no_safe_forced_expiry_error=error,
        compact_example_grid=compact,
        invalid_search_candidate_rejected=True)


def test_missing_guard_counterexamples():
    examples = {
        'missing_horizontal_interword_separator': (['ABCDZ', 'ZZZZZ', 'ZZZZZ', 'ZZZZZ', 'ZZZZZ'], ['AB', 'CD'], ['BC']),
        'missing_trailing_wrap_separator': (['ABC', 'ZZZ', 'ZZZ'], ['ABC'], ['CAB']),
        'odd_side_too_many_content_rows_wrap': (['AZZ', 'ZZZ', 'BZZ'], ['A', 'B'], ['BA']),
        'long_periodic_forbidden_must_not_be_dropped': (['AB', 'ZZ'], ['AB'], ['ABABA']),
    }
    for name, (grid, required, forbidden) in examples.items():
        check(independent_valid(grid, required, []), {'counterexample_required_missing': name})
        check(not independent_valid(grid, required, forbidden), {'counterexample_not_invalid': name})
        RESULTS['counterexamples'][name] = dict(grid=grid, required=required, forbidden=forbidden)


def main():
    started = time.perf_counter()
    test_shelves()
    test_validator()
    test_solver_internals()
    test_solver_transitions()
    test_fallback_branches()
    test_missing_guard_counterexamples()
    RESULTS['elapsed_seconds'] = time.perf_counter() - started
    RESULTS['passed'] = not RESULTS['failures']
    out = ROOT / 'audit_v3_results.json'
    out.write_text(json.dumps(RESULTS, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(RESULTS, indent=2))


if __name__ == '__main__':
    main()
