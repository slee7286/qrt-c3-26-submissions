"""Independent all-words-placed soft-conflict experiment.

No production solver imports. solve(words, n, seconds, seed) returns rows or None.
Supports per-cell-majority and pairwise disagreement energy. A coordinate move
scores all 8*N*N placements in parallel using Python integer bit planes.
LAST_STATS describes the most recent run (including unsuccessful runs).
"""
import math
import random
import time

LAST_STATS = {}


def _pick_rank(mask, rank):
    offset = 0
    while mask.bit_length() > 1:
        half = mask.bit_length() // 2
        low = mask & ((1 << half) - 1)
        count = low.bit_count()
        if rank < count:
            mask = low
        else:
            offset += half
            mask >>= half
            rank -= count
    return offset


def _sum_planes(masks):
    planes = []
    for value in masks:
        i = 0
        while value:
            if i == len(planes):
                planes.append(value)
                break
            planes[i], value = planes[i] ^ value, planes[i] & value
            i += 1
    return planes


def _minimum(planes, domain):
    cost = 0
    for i in range(len(planes) - 1, -1, -1):
        zeros = domain & ~planes[i]
        if zeros:
            domain = zeros
        else:
            cost |= 1 << i
    return cost, domain


class _Soft:
    def __init__(self, words, n, rng, objective='majority'):
        self.n, self.rng = n, rng
        self.objective = objective
        self.size = n*n
        self.all = (1 << self.size) - 1
        repeat = self.all // ((1 << n) - 1)
        self.low = [((1 << k) - 1)*repeat for k in range(n)]
        self.words = [tuple(ord(c)-65 for c in w) for w in words]
        self.maps = [[], [], [], []]
        self.inverse = [[0]*self.size for _ in range(4)]
        for r in range(n):
            for c in range(n):
                p = r*n+c
                for d, q in enumerate((p, c*n+r, ((c-r) % n)*n+r,
                                       ((c+r) % n)*n+r)):
                    self.maps[d].append(q)
                    self.inverse[d][q] = p
        self.counts = [{} for _ in range(self.size)]
        self.owners = [0]*self.size
        self.majority = [(1 << 26)-1]*self.size
        self.free = [[self.all]*26 for _ in range(4)]
        self.blank = [self.all]*4
        self.assignments = [None]*len(words)
        self.conflicts = [0]*len(words)
        self.energy = 0
        self.pair_energy = 0
        self.guided_energy = 0
        self.penalty = [1]*self.size
        self.penalty_planes = [[self.all] for _ in range(4)]
        self.width = max(1, len(words).bit_length())
        self.totals = [[0]*self.width for _ in range(4)]
        self.letters = [[[0]*self.width for _ in range(26)] for _ in range(4)]

    def rotate(self, bits, k):
        if not k:
            return bits
        low = self.low[self.n-k]
        return ((bits >> k) & low) | ((bits << (self.n-k)) & (self.all ^ low))

    def cells(self, d, start, length):
        base, off = divmod(start, self.n)
        inv = self.inverse[d]
        base *= self.n
        return tuple(inv[base+(off+i) % self.n] for i in range(length))

    def _change(self, p, ch, wi, delta):
        counts = self.counts[p]
        total = sum(counts.values())
        same = counts.get(ch, 0)
        self.pair_energy += delta*(total-same)
        total_change = total ^ (total+delta)
        same_change = same ^ (same+delta)
        owners = self.owners[p]
        old_blank = not counts
        if len(counts) > 1:
            bits = owners
            while bits:
                bit = bits & -bits
                self.conflicts[bit.bit_length()-1] -= 1
                bits ^= bit
        old_cost = sum(counts.values()) - max(counts.values(), default=0)
        value = counts.get(ch, 0) + delta
        if value:
            counts[ch] = value
        else:
            del counts[ch]
        if delta > 0:
            owners |= 1 << wi
        else:
            owners &= ~(1 << wi)
        self.owners[p] = owners
        if len(counts) > 1:
            bits = owners
            while bits:
                bit = bits & -bits
                self.conflicts[bit.bit_length()-1] += 1
                bits ^= bit
        largest = max(counts.values(), default=0)
        change = sum(counts.values()) - largest - old_cost
        self.energy += change
        self.guided_energy += self.penalty[p]*change
        majority = (sum(1 << c for c, count in counts.items() if count == largest)
                    if counts else (1 << 26)-1)
        changed = majority ^ self.majority[p]
        self.majority[p] = majority
        blank_changed = old_blank != (not counts)
        for d in range(4):
            bit = 1 << self.maps[d][p]
            bits = total_change
            while bits:
                plane = bits & -bits
                self.totals[d][plane.bit_length()-1] ^= bit
                bits ^= plane
            bits = same_change
            while bits:
                plane = bits & -bits
                self.letters[d][ch][plane.bit_length()-1] ^= bit
                bits ^= plane
            if blank_changed:
                self.blank[d] ^= bit
            bits = changed
            while bits:
                letter = bits & -bits
                self.free[d][letter.bit_length()-1] ^= bit
                bits ^= letter

    def remove(self, wi):
        assignment = self.assignments[wi]
        if assignment is None:
            return
        d, start = assignment
        word = self.words[wi] if d % 2 == 0 else self.words[wi][::-1]
        for p, ch in zip(self.cells(d//2, start, len(word)), word):
            self._change(p, ch, wi, -1)
        self.assignments[wi] = None

    def add(self, wi, d, start):
        word = self.words[wi] if d % 2 == 0 else self.words[wi][::-1]
        for p, ch in zip(self.cells(d//2, start, len(word)), word):
            self._change(p, ch, wi, 1)
        self.assignments[wi] = (d, start)

    def penalize(self):
        """Break out of local minima by charging repeatedly disputed cells."""
        for p, counts in enumerate(self.counts):
            if len(counts) < 2:
                continue
            old = self.penalty[p]
            self.penalty[p] += 1
            self.guided_energy += sum(counts.values())-max(counts.values())
            for d in range(4):
                bit = 1 << self.maps[d][p]
                changed = old ^ (old+1)
                while changed:
                    value = changed & -changed
                    index = value.bit_length()-1
                    while index >= len(self.penalty_planes[d]):
                        self.penalty_planes[d].append(0)
                    self.penalty_planes[d][index] ^= bit
                    changed ^= value

    def cost_planes(self, word, family):
        if self.objective == 'majority':
            return _sum_planes(self.rotate(self.all ^ self.free[family][ch], k)
                               for k, ch in enumerate(word))
        if self.objective == 'guided':
            planes = []
            for k, ch in enumerate(word):
                bad = self.all ^ self.free[family][ch]
                for j, weight_mask in enumerate(self.penalty_planes[family]):
                    carry = self.rotate(bad & weight_mask, k)
                    index = j
                    while carry:
                        while index >= len(planes):
                            planes.append(0)
                        planes[index], carry = planes[index] ^ carry, planes[index] & carry
                        index += 1
            return planes
        # Sum occupant counts and matching-letter counts separately, then
        # subtract their bit-sliced values. Every start has nonnegative cost.
        sums = []
        for source in (None, True):
            planes = []
            for k, ch in enumerate(word):
                values = self.totals[family] if source is None else self.letters[family][ch]
                for j, mask in enumerate(values):
                    carry = self.rotate(mask, k)
                    index = j
                    while carry:
                        while index >= len(planes):
                            planes.append(0)
                        planes[index], carry = planes[index] ^ carry, planes[index] & carry
                        index += 1
            sums.append(planes)
        a, b = sums
        result, borrow = [], 0
        for j in range(max(len(a), len(b))):
            x = a[j] if j < len(a) else 0
            y = b[j] if j < len(b) else 0
            result.append(x ^ y ^ borrow)
            borrow = ((~x & (y | borrow)) | (y & borrow)) & self.all
        return result

    def candidate(self, wi, slack=0, compact=True):
        word = self.words[wi]
        options, best = [], float('inf')
        for d in range(8):
            w = word if d % 2 == 0 else word[::-1]
            planes = self.cost_planes(w, d//2)
            cost, domain = _minimum(planes, self.all)
            if cost < best:
                best = cost
            options.append((d, cost, domain, planes))
        # Slack occasionally admits one additional disagreement, providing
        # uphill moves rather than deterministic descent trapped at a plateau.
        target = best + slack
        candidates = []
        for d, cost, domain, planes in options:
            if cost > target:
                continue
            if target != cost:
                domain = self.all
                for i, plane in enumerate(planes):
                    domain &= plane if (target >> i) & 1 else self.all ^ plane
                if target >> len(planes):
                    domain = 0
            if domain:
                # Prefer reusing cells after minimizing new disagreements.
                holes = 0
                if compact:
                    blank_planes = _sum_planes(
                        self.rotate(self.blank[d//2], k) for k in range(len(word)))
                    holes, domain = _minimum(blank_planes, domain)
                candidates.append((holes, d, domain))
        if not candidates:
            return self.candidate(wi, 0, compact)
        holes = min(item[0] for item in candidates)
        _, d, domain = self.rng.choice([x for x in candidates if x[0] == holes])
        return d, _pick_rank(domain, self.rng.randrange(domain.bit_count()))

    def grid(self):
        if self.energy or any(a is None for a in self.assignments):
            return None
        chars = [chr(next(iter(c), 0)+65) for c in self.counts]
        return [''.join(chars[r*self.n:(r+1)*self.n]) for r in range(self.n)]


def validate_required(grid, words):
    """Deliberately slow, independent eight-direction required validation."""
    if not grid:
        return False
    n = len(grid)
    if any(len(row) != n or any(not 'A' <= ch <= 'Z' for ch in row)
           for row in grid):
        return False
    for word in words:
        if len(word) > n:
            return False
        found = False
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if not (dr or dc):
                    continue
                if any(all(grid[(r+i*dr) % n][(c+i*dc) % n] == ch
                           for i, ch in enumerate(word))
                       for r in range(n) for c in range(n)):
                    found = True
                    break
            if found:
                break
        if not found:
            return False
    return True


def solve(words, n, seconds=1.0, seed=0, objective='majority'):
    """Return an N-square required-word packing, or None on budget exhaustion.

    Required length must not exceed N. Forbidden patterns are intentionally
    unsupported. Words must be uppercase A-Z; empty required words are ignored.
    """
    global LAST_STATS
    started = time.perf_counter()
    required = list(words)
    if objective not in ('majority', 'pairwise', 'guided'):
        raise ValueError('objective must be majority, pairwise, or guided')
    if n < 1:
        raise ValueError('n must be positive')
    if any(any(not 'A' <= ch <= 'Z' for ch in w) for w in required):
        raise ValueError('words must be uppercase A-Z')
    if max(map(len, required), default=0) > n:
        LAST_STATS = {'reason': 'word_too_long', 'best_energy': None, 'moves': 0}
        return None
    canonical = sorted({min(w, w[::-1]) for w in required if w},
                       key=lambda w: (-len(w), w))
    texts = []
    for w in canonical:
        if not any(w in other or w[::-1] in other for other in texts):
            texts.append(w)
    rng = random.Random(seed)
    state = _Soft(texts, n, rng, objective)
    deadline = started + max(0.0, seconds)
    order = list(range(len(texts)))
    order.sort(key=lambda i: -len(texts[i])*(0.9+0.2*rng.random()))
    for wi in order:
        if time.perf_counter() >= deadline:
            LAST_STATS = {'reason': 'initialization_timeout', 'best_energy': None,
                          'moves': 0, 'seconds': time.perf_counter()-started}
            return None
        state.add(wi, *state.candidate(wi))
    objective_value = lambda: (state.pair_energy if objective == 'pairwise' else
                              state.guided_energy if objective == 'guided' else state.energy)
    quality_value = lambda: state.energy if objective == 'guided' else objective_value()
    initial = best = quality_value()
    best_assignments = state.assignments[:]
    moves, stale, restores = 0, 0, 0
    while state.energy and time.perf_counter() < deadline:
        troubled = [i for i, value in enumerate(state.conflicts) if value]
        # Moving only conflicting words freezes their otherwise-consistent
        # neighbors; occasional background moves open routes through plateaus.
        wi = rng.randrange(len(texts)) if rng.random() < 0.25 else rng.choice(troubled)
        old, energy = state.assignments[wi], objective_value()
        state.remove(wi)
        phase = (moves % 500)/500.0
        temperature = 0.45*(1.0-phase) + 0.03
        slack = int(rng.random() < 0.18*(1.0-phase))
        state.add(wi, *state.candidate(wi, slack, compact=False))
        delta = objective_value()-energy
        if delta > 0 and rng.random() >= math.exp(-delta/temperature):
            state.remove(wi)
            state.add(wi, *old)
        moves += 1
        if quality_value() < best:
            best = quality_value()
            best_assignments = state.assignments[:]
            stale = 0
        else:
            stale += 1
        if objective == 'guided' and stale and stale % 40 == 0:
            state.penalize()
        if stale >= max(600, 4*len(texts)):
            # Restore the best state, then relocate a small conflicting block.
            for j in range(len(texts)):
                state.remove(j)
            for j, assignment in enumerate(best_assignments):
                state.add(j, *assignment)
            trouble = [i for i, value in enumerate(state.conflicts) if value]
            rng.shuffle(trouble)
            block = list(set(trouble[:max(2, len(texts)//12)] +
                             rng.sample(range(len(texts)), max(1, len(texts)//16))))
            for j in block:
                state.remove(j)
            rng.shuffle(block)
            for j in block:
                state.add(j, *state.candidate(j, int(rng.random() < 0.3), compact=False))
            stale = 0
            restores += 1
    grid = state.grid()
    LAST_STATS = {'objective': objective, 'initial_energy': initial, 'best_energy': best,
                  'pair_energy': state.pair_energy,
                  'guided_energy': state.guided_energy,
                  'final_energy': state.energy, 'moves': moves,
                  'restores': restores, 'seconds': time.perf_counter()-started,
                  'words': len(texts), 'valid': grid is not None}
    return grid
