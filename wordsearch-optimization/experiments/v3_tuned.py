#!/bin/python3
import math
import os
import random
import re
import sys
import time
_popcount = getattr(int, 'bit_count', lambda x: bin(x).count('1'))

def _patterns(words, n):
    out = set()
    for w in words:
        if len(w) > n:
            if any((w[i] != w[i % n] for i in range(n, len(w)))):
                continue
            w = w[:n]
        out.add(w)
        out.add(w[::-1])
    return out

def _valid(grid, required, forbidden):
    n = len(grid)
    if n < max((len(w) for w in required), default=1):
        return False
    if not n or any((len(row) != n or any((not 'A' <= c <= 'Z' for c in row)) for row in grid)):
        return False
    lines = []
    for d in range(4):
        for a in range(n):
            if d == 0:
                s = grid[a]
            elif d == 1:
                s = ''.join((grid[k][a] for k in range(n)))
            elif d == 2:
                s = ''.join((grid[k][(a + k) % n] for k in range(n)))
            else:
                s = ''.join((grid[k][(a - k) % n] for k in range(n)))
            lines.append(s + s[:-1])
    for w in required:
        if not any((w in s or w[::-1] in s for s in lines)):
            return False
    patterns = _patterns(forbidden, n)
    if patterns:
        matcher = re.compile('|'.join(sorted(patterns, key=len)))
        if any((matcher.search(s) for s in lines)):
            return False
    return True

class _Geometry:

    def __init__(self, n):
        self.n = n
        self.size = n * n
        self.all = (1 << self.size) - 1
        rep = self.all // ((1 << n) - 1)
        self.low = [((1 << k) - 1) * rep for k in range(n)]
        self.maps = [[], [], [], []]
        self.inverse = [[0] * self.size for _ in range(4)]
        for r in range(n):
            for c in range(n):
                p = r * n + c
                indices = (p, c * n + r, (c - r) % n * n + r, (c + r) % n * n + r)
                for d, q in enumerate(indices):
                    self.maps[d].append(q)
                    self.inverse[d][q] = p

    def rotate(self, bits, k):
        if not k:
            return bits
        low = self.low[self.n - k]
        return bits >> k & low | bits << self.n - k & (self.all ^ low)

    def cells(self, family, start, length):
        a, b = divmod(start, self.n)
        inv = self.inverse[family]
        base = a * self.n
        return tuple((inv[base + (b + i) % self.n] for i in range(length)))

def _pick(mask, rng):
    rank = rng.randrange(_popcount(mask))
    offset = 0
    while mask.bit_length() > 1:
        half = mask.bit_length() // 2
        low = mask & (1 << half) - 1
        count = _popcount(low)
        if rank < count:
            mask = low
        else:
            rank -= count
            mask >>= half
            offset += half
    return offset

def _extreme(domain, masks, maximum):
    planes = []
    for bits in masks:
        carry = bits & domain
        j = 0
        while carry:
            if j == len(planes):
                planes.append(carry)
                break
            planes[j], carry = (planes[j] ^ carry, planes[j] & carry)
            j += 1
    score = 0
    for j in range(len(planes) - 1, -1, -1):
        ones = domain & planes[j]
        zeros = domain ^ ones
        chosen = ones if maximum else zeros
        if chosen:
            domain = chosen
            if maximum:
                score |= 1 << j
        elif not maximum:
            score |= 1 << j
    return (score, domain)

class _Solver:

    def __init__(self, n, words, forbidden, rng):
        self.geo = _Geometry(n)
        self.words = [tuple((ord(c) - 65 for c in w)) for w in words]
        self.forbidden = forbidden
        patterns = _patterns(forbidden, n)
        self.matcher = re.compile(b'|'.join((w.encode() for w in sorted(patterns, key=len)))) if patterns else None
        self.max_forbidden = max(map(len, patterns), default=0)
        self.rng = rng
        self.board = [-1] * self.geo.size
        self.masks = [[0] * 26 for _ in range(4)]
        self.blank = [self.geo.all] * 4
        self.lines = [bytearray(b'[' * n) for _ in range(4 * n)] if self.matcher else None
        self.owners = [0] * self.geo.size
        self.placed = [None] * len(words)
        self.weights = [1.0] * len(words)
        self.safe = next((ord(c) - 65 for c in 'ZXQJKVBPYGFWMUCDLHR SNIATOE'.replace(' ', '') if not any((c in w for w in forbidden))), None)
        banned = {ord(w) - 65 for w in forbidden if len(w) == 1}
        self.alphabet = [i for i in range(26) if i not in banned]

    def set_cell(self, p, ch):
        old = self.board[p]
        if old == ch:
            return
        self.board[p] = ch
        n = self.geo.n
        for d in range(4):
            q = self.geo.maps[d][p]
            bit = 1 << q
            if old >= 0:
                self.masks[d][old] ^= bit
            else:
                self.blank[d] ^= bit
            if ch >= 0:
                self.masks[d][ch] |= bit
            else:
                self.blank[d] |= bit
            if self.lines is not None:
                a, b = divmod(q, n)
                self.lines[d * n + a][b] = ch + 65 if ch >= 0 else 91

    def legal(self, cells):
        if not self.matcher:
            return True
        n = self.geo.n
        affected = {d * n + self.geo.maps[d][p] // n for p in cells for d in range(4)}
        k = self.max_forbidden - 1
        for a in affected:
            s = self.lines[a]
            if self.matcher.search(s + s[:k]):
                return False
        return True

    def domains(self, word):
        result = []
        # The four geometries permute the same cells, so global letter counts
        # (and therefore the best offset order) are identical in every family.
        counts = {ch: _popcount(self.masks[0][ch]) for ch in word}
        order = sorted(range(len(word)), key=lambda i: counts[word[i]])
        backwards = [len(word) - 1 - i for i in order]
        reverse = word[::-1]
        for d in range(4):
            blank = self.blank[d]
            masks = self.masks[d]
            for w, offsets in ((word, order), (reverse, backwards)):
                domain = self.geo.all
                for i in offsets:
                    domain &= self.geo.rotate(blank | masks[w[i]], i)
                    if not domain:
                        break
                result.append(domain)
        return result

    def add(self, wi, cells, word):
        changed = []
        for p, ch in zip(cells, word):
            if self.board[p] < 0:
                self.set_cell(p, ch)
                changed.append(p)
        if not self.legal(changed):
            for p in changed:
                self.set_cell(p, -1)
            return False
        bit = 1 << wi
        for p in cells:
            self.owners[p] |= bit
        self.placed[wi] = (cells, word)
        return True

    def remove(self, wi):
        assignment = self.placed[wi]
        if assignment is None:
            return
        keep = ~(1 << wi)
        for p in assignment[0]:
            self.owners[p] &= keep
            if not self.owners[p]:
                self.set_cell(p, -1)
        self.placed[wi] = None

    def greedy_place(self, wi, domains=None):
        word = self.words[wi]
        domains = self.domains(word) if domains is None else domains[:]
        for attempt in range(18):
            choices = []
            best = -1
            for d, domain in enumerate(domains):
                if not domain:
                    continue
                family = d // 2
                occupied = self.geo.all ^ self.blank[family]
                score, starts = _extreme(domain, (self.geo.rotate(occupied, i) for i in range(len(word))), True)
                if score > best:
                    best, choices = (score, [(d, starts)])
                elif score == best:
                    choices.append((d, starts))
            if not choices:
                return False
            d, starts = self.rng.choice(choices)
            start = _pick(starts, self.rng)
            domains[d] &= ~(1 << start)
            w = word if d % 2 == 0 else word[::-1]
            cells = self.geo.cells(d // 2, start, len(w))
            if self.add(wi, cells, w):
                return True
        return False

    def fill(self):
        holes = [p for p, ch in enumerate(self.board) if ch < 0]
        if self.safe is not None:
            for p in holes:
                self.set_cell(p, self.safe)
            return self.grid()
        for restart in range(5):
            self.rng.shuffle(holes)
            used = []
            for p in holes:
                letters = self.alphabet[:]
                self.rng.shuffle(letters)
                for ch in letters:
                    self.set_cell(p, ch)
                    if self.legal((p,)):
                        used.append(p)
                        break
                else:
                    self.set_cell(p, -1)
                    break
            else:
                return self.grid()
            for p in used:
                self.set_cell(p, -1)
        return None

    def grid(self):
        n = self.geo.n
        return [''.join((chr(ch + 65) for ch in self.board[r * n:(r + 1) * n])) for r in range(n)]

    def greedy(self, deadline):
        remaining = list(range(len(self.words)))
        self.rng.shuffle(remaining)
        remaining.sort(key=lambda wi: -len(self.words[wi]) * (0.86 + 0.28 * self.rng.random()))
        while remaining:
            if time.perf_counter() > deadline:
                return False
            options = []
            for wi in remaining[:4]:
                domains = self.domains(self.words[wi])
                count = sum((_popcount(x) for x in domains))
                options.append((count, wi, domains))
            _, wi, domains = min(options, key=lambda x: x[0])
            self.greedy_place(wi, domains)
            remaining.remove(wi)
        return all((p is not None for p in self.placed))

    def eject(self, wi):
        word = self.words[wi]
        candidates = []
        for d in range(8):
            family = d // 2
            w = word if d % 2 == 0 else word[::-1]
            masks = [self.geo.rotate(self.geo.all ^ (self.blank[family] | self.masks[family][ch]), i) for i, ch in enumerate(w)]
            domain = self.geo.all
            for _ in range(4):
                _, starts = _extreme(domain, masks, False)
                if not starts:
                    break
                start = _pick(starts, self.rng)
                domain &= ~(1 << start)
                cells = self.geo.cells(family, start, len(w))
                victims = 0
                fresh = 0
                for p, ch in zip(cells, w):
                    if self.board[p] >= 0 and self.board[p] != ch:
                        victims |= self.owners[p]
                    if self.board[p] != ch:
                        fresh += 1
                bits = victims
                cost = 0.0
                while bits:
                    bit = bits & -bits
                    cost += self.weights[bit.bit_length() - 1]
                    bits ^= bit
                cost = _popcount(victims) + 0.035 * cost + 0.018 * fresh + self.rng.random() * 0.45
                candidates.append((cost, cells, w, victims))
        candidates.sort(key=lambda x: x[0])
        for _, cells, w, victims in candidates[:8]:
            saved = []
            bits = victims
            while bits:
                bit = bits & -bits
                j = bit.bit_length() - 1
                saved.append((j, self.placed[j]))
                self.remove(j)
                bits ^= bit
            if self.add(wi, cells, w):
                return True
            for j, (old_cells, old_word) in saved:
                self.add(j, old_cells, old_word)
        return False

    def search(self, deadline, steps):
        self.greedy(deadline)
        best = sum((p is not None for p in self.placed))
        snapshot = self.placed[:]
        stale = 0
        shakes = 0
        for step in range(max(steps, 100000)):
            missing = [i for i, p in enumerate(self.placed) if p is None]
            if not missing:
                return self.fill()
            if time.perf_counter() >= deadline:
                return None
            wi = max(missing, key=lambda i: self.weights[i] + self.rng.random() * 0.8)
            self.weights[wi] = min(6.0, self.weights[wi] + 0.15)
            if not self.greedy_place(wi):
                self.eject(wi)
            count = sum((p is not None for p in self.placed))
            if count > best:
                best = count
                snapshot = self.placed[:]
                stale = 0
                shakes = 0
            else:
                stale += 1
            if stale >= max(20, len(self.words) // 2) or count < best - max(2, len(self.words) // 40):
                for j in range(len(self.words)):
                    self.remove(j)
                shakes += 1
                if shakes % 4:
                    for j, assignment in enumerate(snapshot):
                        if assignment is not None:
                            self.add(j, *assignment)
                    occupied = [j for j, p in enumerate(self.placed) if p is not None]
                    self.rng.shuffle(occupied)
                    for j in occupied[:min(len(occupied), 2 + shakes)]:
                        self.remove(j)
                    pending = [j for j, p in enumerate(self.placed) if p is None]
                    self.rng.shuffle(pending)
                    pending.sort(key=lambda j: -len(self.words[j]) * (0.7 + 0.6 * self.rng.random()))
                    for j in pending:
                        self.greedy_place(j)
                else:
                    self.greedy(deadline)
                count = sum((p is not None for p in self.placed))
                if count > best:
                    best = count
                    snapshot = self.placed[:]
                    shakes = 0
                stale = 0
        return None

# Tuning and optional local diagnostics; submission output stays silent.
_TIME_LIMIT = 3.5
_DIAGNOSTICS = False
LAST_DIAGNOSTICS = {}


def _pack_rows(words, n, gap):
    rows = []
    loads = []
    for word in words:
        need = len(word) + gap
        if need > n:
            return None
        choices = [i for i, used in enumerate(loads) if used + need <= n]
        if choices:
            i = max(choices, key=loads.__getitem__)
            rows[i].append(word)
            loads[i] += need
        else:
            rows.append([word])
            loads.append(need)
    return rows


def _compact_fallback(words, required, forbidden, lower, safe):
    """Separator-isolated multiword rows, not one row per word."""
    if safe is None:
        return None
    gap = int(bool(forbidden))
    step = 1 + gap
    ordered = sorted(words, key=lambda w: (-len(w), w))
    area = step * sum(len(w) + gap for w in ordered)
    n = max(lower, max(map(len, ordered), default=0) + gap,
            math.isqrt(max(0, area - 1)) + 1, step)
    while True:
        packed = _pack_rows(ordered, n, gap)
        if packed is not None and len(packed) <= n // step:
            rows = [safe * n for _ in range(n)]
            for i, group in enumerate(packed):
                text = safe.join(group) + safe if gap else ''.join(group)
                rows[step * i] = text + safe * (n - len(text))
            if _valid(rows, required, forbidden):
                protected = rows
                break
            # Internal required/forbidden conflicts should already have been
            # rejected. Never return an unchecked grid, even on this path.
            return None
        n += 1
    if not forbidden:
        return protected
    # Dense shelves need no isolation if they happen to pass the full torus
    # validator. This usually helps rare forbidden patterns. Isolation remains
    # the unconditional safety net whenever a globally safe letter exists.
    for sep in (0, 1):
        area = sum(len(w) + sep for w in ordered)
        first = max(lower, max(map(len, ordered), default=0) + sep,
                    math.isqrt(max(0, area - 1)) + 1, 1)
        for side in range(first, min(len(protected), first + 5)):
            packed = _pack_rows(ordered, side, sep)
            if len(packed) > side:
                continue
            candidate = [safe * side for _ in range(side)]
            for i, group in enumerate(packed):
                text = safe.join(group) + safe if sep else ''.join(group)
                candidate[i] = text + safe * (side - len(text))
            if _valid(candidate, required, forbidden):
                protected = candidate
                break
    return protected


def _score_info(required):
    total = sum(map(len, required))
    lower = max(1, max(map(len, required), default=1))
    bound = min(100.0, 100.0 * total / (1.7 * lower * lower))
    goal = max(lower, math.isqrt(10 * total // 17))
    return total, lower, bound, goal


def generate_grid(required_words, forbidden_words):
    global LAST_DIAGNOSTICS
    started = time.perf_counter()
    required = list(required_words)
    forbidden = sorted(set(forbidden_words))
    if any(any(not 'A' <= c <= 'Z' for c in w) for w in required + forbidden):
        raise ValueError('Words must use uppercase A-Z.')
    if '' in forbidden or len({w for w in forbidden if len(w) == 1}) == 26:
        raise ValueError('Impossible forbidden constraints.')
    forbidden_regex = re.compile('|'.join(_patterns(forbidden, max(map(len, forbidden), default=1)))) if forbidden else None
    if forbidden_regex and any(forbidden_regex.search(w) for w in required):
        raise ValueError('A required word contains a forbidden word or its reverse.')
    canonical = sorted({min(w, w[::-1]) for w in required if w}, key=lambda w: (-len(w), w))
    words = []
    for w in canonical:
        if not any(w in v or w[::-1] in v for v in words):
            words.append(w)
    total, raw_lower, upper_score, score_goal = _score_info(required)
    letter_counts = [0] * 26
    for w in words:
        counts = [w.count(chr(c + 65)) for c in range(26)]
        letter_counts = [max(a, b) for a, b in zip(letter_counts, counts)]
    lower = max(raw_lower, math.isqrt(max(0, sum(letter_counts) - 1)) + 1)
    if forbidden:
        pats = _patterns(forbidden, lower)
        matcher = re.compile('|'.join(sorted(pats))) if pats else None
        if matcher and any(len(w) == lower and matcher.search(w + w[:-1]) for w in words):
            lower += 1
    goal = max(lower, score_goal)
    reduced_sum = sum(map(len, words))
    safe = next((c for c in 'ZXQJKVBPYGFWMUCDLHRSNIATOE' if not any(c in w for w in forbidden)), None)
    stats = {'required_words': len(required), 'reduced_words': len(words),
             'total_letters': total, 'longest_word': raw_lower,
             'forbidden_words': len(forbidden), 'initial_grid_size': None,
             'construction_attempts': 0, 'successful_constructions': 0,
             'failed_constructions': 0, 'attempts': [],
             'fallback_used': False, 'fallback_reason': '',
             'safe_filler': safe, 'score_bound': upper_score}
    LAST_DIAGNOSTICS = stats
    best = _compact_fallback(words, required, forbidden, lower, safe)
    best_source = 'separator_shelves' if forbidden else 'multiword_rows'
    stats['initial_incumbent_size'] = len(best) if best else None
    # Establish the compact certified incumbent BEFORE the timed optimizer.
    # Time spent preprocessing/validating counts toward the search budget.
    budget = min(_TIME_LIMIT, 0.25 + 0.014 * len(words) + 0.001 * reduced_sum)
    deadline = started + budget
    rng = random.Random(61789)

    def finish():
        if best is None:
            raise RuntimeError('No valid grid found within the search budget; no safe separator exists.')
        if not _valid(best, required, forbidden):
            raise RuntimeError('Internal final validation failed.')
        stats['final_grid_size'] = len(best)
        stats['search_runtime'] = time.perf_counter() - started
        stats['fallback_used'] = best_source != 'search'
        stats['fallback_reason'] = ('compact incumbent retained after search exhaustion' if stats['fallback_used'] else '')
        stats['final_score'] = min(100.0, 100.0 * total / (1.7 * len(best) ** 2))
        stats['solution_source'] = best_source
        if _DIAGNOSTICS:
            for key, value in stats.items():
                if key != 'attempts':
                    print(str(key) + ': ' + str(value), file=sys.stderr)
        return best

    def attempt(n, seconds, phase):
        nonlocal best, best_source
        now = time.perf_counter()
        if now >= deadline or (best is not None and n >= len(best)):
            return False
        if stats['initial_grid_size'] is None:
            stats['initial_grid_size'] = n
        stats['construction_attempts'] += 1
        solver = _Solver(n, words, forbidden, rng)
        grid = solver.search(min(deadline, now + seconds), max(80, 8 * len(words)))
        placed = sum(p is not None for p in solver.placed)
        good = grid is not None and _valid(grid, required, forbidden)
        stats['attempts'].append({'n': n, 'phase': phase, 'placed': placed,
                                  'words': len(words), 'valid': good,
                                  'seconds': time.perf_counter() - now})
        if good:
            stats['successful_constructions'] += 1
            best, best_source = grid, 'search'
        else:
            stats['failed_constructions'] += 1
        return good

    if best is not None and len(best) <= goal:
        return finish()
    # Necessary small-size probes: forbidden feasibility is not monotone in N.
    if reduced_sum <= lower * lower or forbidden:
        probe_end = min(deadline, time.perf_counter() + budget * .10)
        for n in range(lower, min(goal, lower + (4 if forbidden else 0)) + 1):
            if time.perf_counter() >= probe_end:
                break
            if attempt(n, max(.001, probe_end - time.perf_counter()), 'lower_probe'):
                if len(best) <= goal:
                    return finish()
                break
    # Secure a reasonably sized eight-direction construction first. Growth
    # attempts receive a bounded slice, rather than exhausting all time at N.
    freq = [0] * 26
    for w in words:
        for c in w:
            freq[ord(c) - 65] += 1
    concentration = sum(v * v for v in freq) / max(1, reduced_sum * reduced_sum)
    effective = 1 / max(concentration, 1 / 26)
    packing = 1.05 + 5.0 / effective
    target = max(lower, goal, math.ceil(math.sqrt(reduced_sum / packing)))
    # Leave a substantial improvement phase, but never lose the incumbent.
    grow_end = min(deadline, started + budget * .68)
    n = target
    found = False
    while time.perf_counter() < grow_end:
        if best is not None and n >= len(best):
            break
        if attempt(n, min(budget * .16, max(.001, grow_end - time.perf_counter())), 'grow'):
            found = True
            break
        n += 1
    if best is not None and len(best) <= goal:
        return finish()
    # If dense attempts failed, try an easy intermediate square instead of
    # returning the isolated-row construction immediately.
    if not found and best is not None and time.perf_counter() < deadline:
        easy = max(n, math.ceil(math.sqrt(max(1, reduced_sum) / .75)))
        if easy < len(best):
            attempt(easy, budget * .12, 'recovery')
    # Reduce one cell at a time, retaining every verified improvement.
    while time.perf_counter() < deadline:
        if best is not None and len(best) <= goal:
            break
        if best is None:
            side = n
            n += 1
        else:
            side = len(best) - 1
        if side < lower:
            break
        attempt(side, max(.015, budget * .20), 'shrink' if best else 'grow_unseparated')
    return finish()

if __name__ == '__main__':
    fptr = open(os.environ['OUTPUT_PATH'], 'w')

    required_words_count = int(input().strip())

    required_words = []

    for _ in range(required_words_count):
        required_words_item = input()
        required_words.append(required_words_item)

    forbidden_words_count = int(input().strip())

    forbidden_words = []

    for _ in range(forbidden_words_count):
        forbidden_words_item = input()
        forbidden_words.append(forbidden_words_item)

    result = generate_grid(required_words, forbidden_words)

    fptr.write('\n'.join([' '.join(x) for x in result]))
    fptr.write('\n')

    fptr.close()