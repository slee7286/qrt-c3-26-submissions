"""Experimental fixed-size, forbidden-free consistent-word packing.

This module deliberately leaves generate_grid.py unchanged.  The public entry
point is solve(words, n, seconds, seed), returning a grid or None.
"""
import heapq
import random
import time

from generate_grid import _Solver, _extreme, _pick


class RepairSolver(_Solver):
    chain_depth = 1

    def conflict_candidates(self, wi, limit=8, protected=0):
        """Rank every start by distinct victim owners, not cell mismatches.

        One word can own several wrong letters; conversely a single crossing
        can require removing several words.  The baseline's four minimum-cell-
        mismatch starts per orientation therefore need not contain the best
        owner-conflict move at all.
        """
        if limit <= 0:
            return []
        word = self.words[wi]
        reverse = word[::-1]
        n = self.geo.n
        heap = []
        board, owners = self.board, self.owners
        cutoff = len(self.words)
        serial = 0
        for family in range(4):
            inverse = self.geo.inverse[family]
            for base in range(0, self.geo.size, n):
                line = inverse[base:base+n] * 2
                for w in (word, reverse):
                    for offset in range(n):
                        cells = line[offset:offset+len(w)]
                        victims = fresh = 0
                        for p, ch in zip(cells, w):
                            if board[p] != ch:
                                fresh += 1
                                if board[p] >= 0:
                                    victims |= owners[p]
                                    if victims & protected or victims.bit_count() > cutoff:
                                        break
                        else:
                            # Keep the integer part an exact owner count, even
                            # for unusually long words.
                            cost = victims.bit_count() + min(
                                0.99, 0.025 * fresh + self.rng.random() * 0.15)
                            serial += 1
                            item = (-cost, serial, tuple(cells), w, victims)
                            if len(heap) < limit:
                                heapq.heappush(heap, item)
                            elif cost < -heap[0][0]:
                                heapq.heapreplace(heap, item)
                            if len(heap) == limit:
                                cutoff = int(-heap[0][0])
        return sorted((-cost, cells, w, victims)
                      for cost, _, cells, w, victims in heap)

    def placement_choices(self, wi, domains, width=4):
        """A small beam of distinct legal starts, with overlap-first ordering."""
        domains = domains[:]
        word = self.words[wi]
        result = []
        for _ in range(width):
            choices = []
            best = -1
            for direction, domain in enumerate(domains):
                if not domain:
                    continue
                family = direction // 2
                occupied = self.geo.all ^ self.blank[family]
                score, starts = _extreme(
                    domain,
                    (self.geo.rotate(occupied, i) for i in range(len(word))),
                    True)
                if score > best:
                    best, choices = score, [(direction, starts)]
                elif score == best:
                    choices.append((direction, starts))
            if not choices:
                break
            direction, starts = self.rng.choice(choices)
            start = _pick(starts, self.rng)
            domains[direction] &= ~(1 << start)
            w = word if direction % 2 == 0 else word[::-1]
            result.append((self.geo.cells(direction // 2, start, len(w)), w))
        return result

    def reinsert(self, pending, deadline, width=3, nodes=30,
                 chain_depth=0, protected=0):
        """MRV backtracking plus optional protected-owner ejection chains.

        Each ejection consumes depth. Inserted pending words become protected,
        preventing undo cycles. Every failed branch restores its exact state.
        """
        budget = [nodes]

        def visit(todo, depth, locked):
            if not todo:
                return True
            if budget[0] <= 0 or time.perf_counter() >= deadline:
                return False
            budget[0] -= 1
            options = []
            for wi in todo:
                domains = self.domains(self.words[wi])
                count = sum(domain.bit_count() for domain in domains)
                options.append((count, wi, domains))
            count, wi, domains = min(options, key=lambda option: option[0])
            remaining = [j for j in todo if j != wi]
            if count:
                for cells, word in self.placement_choices(wi, domains, width):
                    if self.add(wi, cells, word):
                        if visit(remaining, depth, locked | (1 << wi)):
                            return True
                        self.remove(wi)
            elif depth:
                for _, cells, word, victims in self.conflict_candidates(wi, width, locked):
                    if time.perf_counter() >= deadline:
                        break
                    if victims.bit_count() > 2:
                        continue
                    saved = []
                    while victims:
                        bit = victims & -victims
                        j = bit.bit_length() - 1
                        saved.append((j, self.placed[j]))
                        self.remove(j)
                        victims ^= bit
                    if self.add(wi, cells, word):
                        todo_next = remaining + [j for j, _ in saved]
                        if visit(todo_next, depth - 1, locked | (1 << wi)):
                            return True
                        self.remove(wi)
                    for j, assignment in saved:
                        self.add(j, *assignment)
            return False

        return visit(list(pending), chain_depth, protected)

    def repair(self, wi, deadline, candidates=None):
        """Try replacing the target and jointly relocating all victim words.

        A failed transaction restores cell masks, owners and all assignments;
        unlike unconstrained ejection it never sacrifices the incumbent count.
        """
        initial_missing = sum(assignment is None for assignment in self.placed)
        depth = self.chain_depth if initial_missing <= 2 else 0
        if candidates is None:
            candidates = self.conflict_candidates(wi)
        for _, cells, word, victims in candidates:
            if time.perf_counter() >= deadline:
                break
            saved = []
            while victims:
                bit = victims & -victims
                j = bit.bit_length() - 1
                saved.append((j, self.placed[j]))
                self.remove(j)
                victims ^= bit
            if self.add(wi, cells, word):
                if self.reinsert([j for j, _ in saved], deadline,
                                 chain_depth=depth, protected=1 << wi):
                    return True
                self.remove(wi)
            for j, assignment in saved:
                self.add(j, *assignment)
        return False

    def restore(self, snapshot):
        """Restore assignments through ownership-aware operations."""
        for wi, assignment in enumerate(self.placed):
            if assignment != snapshot[wi]:
                self.remove(wi)
        for wi, assignment in enumerate(snapshot):
            if assignment is not None and self.placed[wi] is None:
                self.add(wi, *assignment)

    def search(self, deadline, steps):
        self.stats = dict(repairs=0, repaired=0, moves=0, shakes=0, restarts=0)
        self.greedy(deadline)
        best = sum(assignment is not None for assignment in self.placed)
        snapshot = self.placed[:]
        self.stats['best'] = best
        stale = 0
        shakes = 0
        for _ in range(steps):
            missing = [wi for wi, assignment in enumerate(self.placed) if assignment is None]
            if not missing:
                self.stats['best'] = len(self.words)
                return self.fill()
            if time.perf_counter() >= deadline:
                break
            wi = max(missing, key=lambda j: self.weights[j] + self.rng.random() * 0.8)
            self.weights[wi] = min(8.0, self.weights[wi] + 0.2)
            if not self.greedy_place(wi):
                candidates = self.conflict_candidates(wi, 12)
                self.stats['repairs'] += 1
                repair_deadline = min(deadline, time.perf_counter() + 0.012)
                if self.repair(wi, repair_deadline, candidates[:4]):
                    self.stats['repaired'] += 1
                elif time.perf_counter() < deadline and candidates:
                    _, cells, word, victims = self.rng.choice(candidates[:3])
                    while victims:
                        bit = victims & -victims
                        self.remove(bit.bit_length() - 1)
                        victims ^= bit
                    self.add(wi, cells, word)
                    self.stats['moves'] += 1
            count = sum(assignment is not None for assignment in self.placed)
            if count > best:
                best, snapshot, stale, shakes = count, self.placed[:], 0, 0
                self.stats['best'] = best
            else:
                stale += 1
            if stale >= max(10, len(self.words) // 3) or count < best - 2:
                self.restore(snapshot)
                shakes += 1
                self.stats['shakes'] += 1
                if shakes % 4 == 0:
                    for j in range(len(self.words)):
                        self.remove(j)
                    self.greedy(deadline)
                    self.stats['restarts'] += 1
                else:
                    occupied = [j for j, assignment in enumerate(self.placed) if assignment is not None]
                    self.rng.shuffle(occupied)
                    for j in occupied[:min(len(occupied), 2 + shakes)]:
                        self.remove(j)
                    # Repair the destroyed neighbourhood greedily; the best
                    # snapshot remains available if this perturbation drifts.
                    pending = [j for j, assignment in enumerate(self.placed) if assignment is None]
                    self.rng.shuffle(pending)
                    for j in pending:
                        self.greedy_place(j)
                count = sum(assignment is not None for assignment in self.placed)
                if count > best:
                    best, snapshot, shakes = count, self.placed[:], 0
                    self.stats['best'] = best
                stale = 0
        self.restore(snapshot)
        return self.fill() if best == len(self.words) else None


def solve(words, n, seconds, seed):
    """Attempt a fixed size within a soft wall-clock budget."""
    if n < 1 or any(len(word) > n for word in words):
        return None
    deadline = time.perf_counter() + max(0.0, seconds)
    solver = RepairSolver(n, words, [], random.Random(seed))
    return solver.search(deadline, 10**9)


def benchmark(cases, sizes, seconds, seeds):
    """Paired fixed-N runs; preprocessing/initialization counts in both budgets.

    Words are supplied verbatim to both solvers (no production canonicalization).
    Independent brute validation is outside the timed search. The solver order
    alternates by seed index to reduce systematic first-run scheduling bias.
    """
    from test_generate_grid import valid

    records = []
    for name, words, forbidden in cases:
        if name not in sizes or forbidden:
            continue
        for index, seed in enumerate(seeds):
            classes = (_Solver, RepairSolver) if index % 2 == 0 else (RepairSolver, _Solver)
            for cls in classes:
                started = time.perf_counter()
                solver = cls(sizes[name], words, [], random.Random(seed))
                grid = solver.search(started + seconds, 10**9)
                elapsed = time.perf_counter() - started
                ok = grid is not None and valid(grid, words, [])
                if grid is not None and not ok:
                    raise AssertionError(('invalid experimental output', name, cls.__name__, seed))
                records.append(dict(case=name, N=sizes[name], seed=seed,
                                    solver=cls.__name__, budget=seconds,
                                    seconds=elapsed, valid=ok,
                                    placed_at_exit=sum(p is not None for p in solver.placed),
                                    stats=getattr(solver, 'stats', None)))
    return records


if __name__ == '__main__':
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=float, default=1.0)
    parser.add_argument('--seeds', default='0,1,2,3,4')
    parser.add_argument('--chain-depth', type=int, default=RepairSolver.chain_depth)
    parser.add_argument('--cases', default=str(Path(__file__).resolve().parents[1] / 'ws_cases.json'))
    args = parser.parse_args()
    RepairSolver.chain_depth = args.chain_depth
    cases = json.loads(Path(args.cases).read_text())
    sizes = {'random26-40': 15, 'random26-100': 22, 'random26-200': 31,
             'dense5-40': 12, 'dense5-100': 18, 'dense5-200': 24}
    records = benchmark(cases, sizes, args.seconds, [int(s) for s in args.seeds.split(',')])
    for record in records:
        print(json.dumps(record), flush=True)
    for name in sizes:
        summary = dict(case=name, N=sizes[name], budget=args.seconds)
        for cls in (_Solver, RepairSolver):
            runs = [r for r in records if r['case'] == name and r['solver'] == cls.__name__]
            summary[cls.__name__] = dict(solved=sum(r['valid'] for r in runs),
                                        runs=len(runs),
                                        mean_seconds=sum(r['seconds'] for r in runs) / len(runs)
                                        if runs else None)
        print('SUMMARY ' + json.dumps(summary), flush=True)
