import math
import re
import random
import time
from generate_grid_v1 import _valid,_patterns
from experiments.portfolio_search import PortfolioSolver as _Solver

def generate_grid(required_words, forbidden_words):
    required = list(required_words)
    forbidden = list(set(forbidden_words))
    if any(any(not 'A' <= c <= 'Z' for c in w) for w in required+forbidden):
        raise ValueError('Words must use uppercase A-Z.')
    if '' in forbidden:
        raise ValueError('An empty forbidden word makes the instance impossible.')
    if len({w for w in forbidden if len(w) == 1}) == 26:
        raise ValueError('Every letter is forbidden.')
    forbidden_regex = re.compile('|'.join(_patterns(forbidden, max(map(len, forbidden), default=1)))) if forbidden else None
    if forbidden_regex and any(forbidden_regex.search(w) for w in required):
        raise ValueError('A required word contains a forbidden word or its reverse.')
    canonical = sorted({min(w, w[::-1]) for w in required if w}, key=lambda w: (-len(w), w))
    words = []
    for w in canonical:
        if not any(w in v or w[::-1] in v for v in words):
            words.append(w)
    lower = max(1, max(map(len, required), default=1))
    letter_counts = [0]*26
    for w in words:
        counts = [0]*26
        for c in w:
            counts[ord(c)-65] += 1
        letter_counts = [max(a, b) for a, b in zip(letter_counts, counts)]
    lower = max(lower, math.isqrt(max(0, sum(letter_counts)-1))+1)
    # A word occupying an entire cycle forces all of its cyclic rotations,
    # including periodic forbidden words longer than the cycle.
    if forbidden:
        pats = _patterns(forbidden, lower)
        matcher = re.compile('|'.join(sorted(pats))) if pats else None
        if matcher and any(len(w) == lower and matcher.search(w+w[:-1]) for w in words):
            lower += 1
    score_sum = sum(map(len, required))
    start = time.perf_counter()
    budget = min(3.5, 0.25+0.014*len(words)+0.001*sum(map(len, words)))
    deadline = start+budget
    rng = random.Random(61789)
    best = None
    # A guaranteed fallback exists when a letter occurs in no forbidden word.
    safe = next((c for c in 'ZXQJKVBPYGFWMUCDLHRSNIATOE' if not any(c in w for w in forbidden)), None)
    fallback_n = max(lower, len(words), 1) if not forbidden else max(lower+1, 2*len(words), 1)
    target = max(lower, math.isqrt(10*score_sum//17))
    if sum(map(len, words)) <= lower*lower:
        target = lower
    # Small sizes can be the only feasible sizes under forbidden constraints.
    # Probe them before jumping to the score target; feasibility is not monotone.
    if forbidden:
        probe_deadline = min(deadline, start+budget*0.15)
        for probe_n in range(lower, target):
            if time.perf_counter() >= probe_deadline:
                break
            solver = _Solver(probe_n, words, forbidden, rng)
            grid = solver.search(probe_deadline, max(4, len(words)//2))
            if grid is not None and _valid(grid, required, forbidden):
                best = grid
                break
    n = target
    while best is None:
        slice_deadline = min(deadline, time.perf_counter()+max(0.03, budget*0.20))
        solver = _Solver(n, words, forbidden, rng)
        grid = solver.search(slice_deadline, max(30, len(words)*8))
        if grid is not None and _valid(grid, required, forbidden):
            best = grid
            break
        if time.perf_counter() >= deadline:
            break
        n += 1 if forbidden else max(1, n//10)
    if best is not None:
        while len(best) > max(lower, math.isqrt(10*score_sum//17)) and time.perf_counter() < deadline:
            n = len(best)-1
            solver = _Solver(n, words, forbidden, rng)
            grid = solver.search(min(deadline, time.perf_counter()+max(0.04, budget*0.25)), max(50, len(words)*12))
            if grid is not None and _valid(grid, required, forbidden):
                best = grid
            elif time.perf_counter() < deadline:
                continue
            else:
                break
        return best
    if safe is not None:
        n = fallback_n
        rows = [safe*n for _ in range(n)]
        for i, w in enumerate(words):
            r = i if not forbidden else 2*i
            rows[r] = w+safe*(n-len(w))
        if _valid(rows, required, forbidden):
            return rows
    raise RuntimeError('No valid grid found within the search budget.')


