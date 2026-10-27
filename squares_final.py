#!/bin/python3
import os, sys, time, random, math
from bisect import bisect_right

TIME_LIMIT = 8.0  # seconds per test
SEED = 2026
REPCAP = 4000
NW = 20
SLOT = 0.25
TF = 0.3

# ---------- greedy skyline best-fit (from v3) ----------
def _pack(W, cnt, policy, rng=None, p_skip=0.0, look=False):
    vals = sorted(cnt)
    c = dict(cnt)
    remaining = sum(c.values())
    segs = [[0, W, 0]]
    pos = {s: [] for s in cnt}
    INF = float('inf')
    while remaining:
        i = 0
        for k in range(1, len(segs)):
            if segs[k][2] < segs[i][2]:
                i = k
        x, w, h = segs[i]
        lh = segs[i-1][2] if i > 0 else INF
        rh = segs[i+1][2] if i + 1 < len(segs) else INF
        j = bisect_right(vals, w) - 1
        if j < 0:
            segs[i][2] = min(lh, rh)
        else:
            if look and j > 0:
                jj = j
                while jj >= 0:
                    rest = w - vals[jj]
                    small = vals[0] if (vals[0] != vals[jj] or c[vals[jj]] > 1) else (vals[1] if len(vals) > 1 else 10**9)
                    if rest == 0 or rest >= small:
                        break
                    jj -= 1
                if jj >= 0:
                    j = jj
            if rng is not None and j > 0 and rng.random() < p_skip:
                j -= rng.randint(1, min(j, 2))
            s = vals[j]
            c[s] -= 1
            if c[s] == 0:
                vals.pop(j)
            remaining -= 1
            pol = policy if rng is None else rng.randint(0, 3)
            if pol == 0:   left = True
            elif pol == 1: left = False
            elif pol == 2: left = lh >= rh
            else:          left = lh <= rh
            if left or w == s:
                pos[s].append((h, x))
                new = [[x, s, h + s]]
                if w > s:
                    new.append([x + s, w - s, h])
            else:
                px = x + w - s
                pos[s].append((h, px))
                new = [[x, w - s, h], [px, s, h + s]]
            segs[i:i+1] = new
        merged = [segs[0]]
        for sg in segs[1:]:
            if sg[2] == merged[-1][2]:
                merged[-1][1] += sg[1]
            else:
                merged.append(sg)
        segs = merged
    H = Wu = 0
    for s, lst in pos.items():
        for (r, q) in lst:
            H = max(H, r + s); Wu = max(Wu, q + s)
    return H * Wu, pos


# ---------- priority-driven best-fit: perm decides which fitting square fills each gap ----------
def _pack_perm(W, perm, pol, Ht):
    """Fitness-number best-fit: at the lowest gap pick the square with highest fitness,
    ties broken by priority order perm. Returns (overflow, H, Wu, placements)."""
    rem = list(perm)
    segs = [[0, W, 0]]
    place = {}
    INF = 1 << 60
    overflow = 0
    H = Wu = 0
    while rem:
        i = 0
        for k in range(1, len(segs)):
            if segs[k][2] < segs[i][2]:
                i = k
        x, w, h = segs[i]
        lh = segs[i-1][2] if i > 0 else INF
        rh = segs[i+1][2] if i + 1 < len(segs) else INF
        bestf = -100; pick = -1
        for t in range(len(rem)):
            s = SIDE[rem[t]]
            if s > w:
                continue
            top = h + s
            if s == w:
                f = 2 + (top == lh) + (top == rh)
            else:
                f = 1 if (top == lh or top == rh) else 0
            if top > Ht and pol == 1:
                f -= 3
            if f > bestf:
                bestf = f; pick = t
                if f == 4:
                    break
        if pick < 0:
            segs[i][2] = min(lh, rh)
        else:
            idx = rem.pop(pick)
            s = SIDE[idx]
            top = h + s
            if w == s:
                left = True
            elif top == lh:
                left = True
            elif top == rh:
                left = False
            else:
                left = lh >= rh
            px = x if left else x + w - s
            place[idx] = (h, px)
            if top > Ht:
                overflow += s * (top - Ht)
            if top > H: H = top
            if px + s > Wu: Wu = px + s
            if left:
                new = [[x, s, top]]
                if w > s:
                    new.append([x + s, w - s, h])
            else:
                new = [[x, w - s, h], [px, s, top]]
            segs[i:i+1] = new
        merged = [segs[0]]
        for sg in segs[1:]:
            if sg[2] == merged[-1][2]:
                merged[-1][1] += sg[1]
            else:
                merged.append(sg)
        segs = merged
    return overflow, H, Wu, place

SIDE = []


class _Stop(Exception):
    pass


def _finish(W, Ht, segs, c, budget, node_cap):
    """Complete DFS: pack remaining squares (counts c) on skyline segs under height Ht, waste <= budget."""
    sizes = sorted(c, reverse=True)
    c = dict(c)
    placed = []
    nodes = [0]
    INF = 1 << 60
    rem0 = sum(c.values())
    if rem0 == 0:
        return placed
    if max(s for s in sizes) > Ht:
        return None

    def merge(ns):
        out = [ns[0]]
        for sg in ns[1:]:
            if sg[2] == out[-1][2]:
                out[-1] = [out[-1][0], out[-1][1] + sg[1], out[-1][2]]
            else:
                out.append(sg)
        return out

    def dfs(segs, rem, waste):
        if rem == 0:
            return True
        nodes[0] += 1
        if nodes[0] > node_cap:
            raise _Stop
        i = 0
        for k in range(1, len(segs)):
            if segs[k][2] < segs[i][2]:
                i = k
        x, w, h = segs[i]
        if h >= Ht:
            return False
        lh = segs[i-1][2] if i > 0 else INF
        rh = segs[i+1][2] if i + 1 < len(segs) else INF
        room = Ht - h
        tried = False
        for s in sizes:
            if c[s] == 0 or s > w or s > room:
                continue
            tried = True
            c[s] -= 1
            for left in ((True, False) if (w > s and lh != rh) else (True,)):
                if left:
                    placed.append((s, h, x))
                    new = [[x, s, h + s]] + ([[x + s, w - s, h]] if w > s else [])
                else:
                    placed.append((s, h, x + w - s))
                    new = [[x, w - s, h], [x + w - s, s, h + s]]
                if dfs(merge(segs[:i] + new + segs[i+1:]), rem - 1, waste):
                    return True
                placed.pop()
            c[s] += 1
        nh = min(lh, rh, Ht)
        cost = (nh - h) * w
        if nh > h and cost <= waste:
            ns = segs[:i] + [[x, w, nh]] + segs[i+1:]
            if dfs(merge(ns), rem, waste - cost):
                return True
        return False

    try:
        ok = dfs([list(sg) for sg in segs], rem0, budget)
    except _Stop:
        return None
    return placed if ok else None



def _repair_from(W, Ht, squares, place, S, cap, rng):
    """Remove the squares poking above a cut row and re-pack them exactly under Ht."""
    n = len(squares)
    tops = sorted(set(place[i][0] + squares[i] for i in range(n)), reverse=True)
    for cut in tops[1:8]:
        keep = [i for i in range(n) if place[i][0] + squares[i] <= cut]
        rem = [i for i in range(n) if place[i][0] + squares[i] > cut]
        if len(rem) > 22 or not keep:
            continue
        col = [0] * W
        for i in keep:
            r, q = place[i]; s = squares[i]
            for x in range(q, q + s):
                if r + s > col[x]: col[x] = r + s
        segs = []
        for x in range(W):
            if segs and segs[-1][2] == col[x]:
                segs[-1][1] += 1
            else:
                segs.append([x, 1, col[x]])
        if max(col) > Ht:
            continue
        kept_area = sum(squares[i] ** 2 for i in keep)
        holes = sum(col) - kept_area
        budget = W * Ht - S - holes
        if budget < 0:
            continue
        c = {}
        for i in rem:
            c[squares[i]] = c.get(squares[i], 0) + 1
        res = _finish(W, Ht, segs, c, budget, cap)
        if res is not None:
            newp = dict((i, place[i]) for i in keep)
            pools = {}
            for s, r, q in res:
                pools.setdefault(s, []).append((r, q))
            for i in rem:
                newp[i] = pools[squares[i]].pop()
            return newp
    return None


def pack_squares(squares):
    global SIDE
    n = len(squares)
    if n == 0:
        return []
    t0 = time.time()
    deadline = t0 + TIME_LIMIT
    cnt = {}
    for s in squares:
        cnt[s] = cnt.get(s, 0) + 1
    m = max(squares)
    S = sum(s * s for s in squares)
    T = sum(squares)

    def LB(W):
        return W * max(m, -(-S // W))

    Wmax = max(m, min(T, -(-S // m) + m))
    lbs = [(LB(W), W) for W in range(m, Wmax + 1)]
    L = min(l for l, _ in lbs)
    cands = sorted(lb for lb in lbs if lb[0] <= 1.3 * L)

    best_area, best_out = None, None

    def out_from_pos(pos):
        pools = {s: list(lst) for s, lst in pos.items()}
        return [list(pools[s].pop()) for s in squares]

    results = []
    # Phase 1: deterministic best-fit over promising widths
    for lb, W in cands:
        if best_area is not None and lb >= best_area:
            continue
        if best_area is not None and time.time() - t0 > TIME_LIMIT * 0.15:
            break
        wbest = None
        for pol in range(8):
            a, p = _pack(W, cnt, pol % 4, look=pol >= 4)
            if wbest is None or a < wbest:
                wbest = a
            if best_area is None or a < best_area:
                best_area, best_out = a, out_from_pos(p)
        results.append((wbest, W))
        if best_area == L:
            break
    if best_area == L:
        return best_out

    # Phase 2: simulated annealing on the priority permutation, per width
    SIDE = list(squares)
    rng = random.Random(SEED)
    results.sort()
    widths = []
    for _, W in results:
        if W not in widths:
            widths.append(W)
    widths = widths[:NW]
    base = sorted(range(n), key=lambda k: -squares[k])
    state = {}
    for W in widths:
        state[W] = [list(base), None, rng.randint(0, 1)]
    avg_area = S / n
    k = 0
    while time.time() < deadline and best_area != L:
        live = [W for W in widths if LB(W) < best_area]
        if not live:
            break
        W = live[k % len(live)]
        k += 1
        Ht = (best_area - 1) // W  # height that would beat the incumbent at this width
        if Ht < m or W * Ht < S:
            continue
        perm, cur, pol = state[W]
        ov, H, Wu, pl = _pack_perm(W, perm, pol, Ht)
        cur = ov
        slot_end = min(deadline, time.time() + SLOT)
        T0 = avg_area * TF
        it = 0
        while time.time() < slot_end:
            it += 1
            cand = perm[:]
            r = rng.random()
            a = rng.randrange(n)
            if r < 0.45:
                b = min(n - 1, max(0, a + rng.randint(-3, 3)))
                cand[a], cand[b] = cand[b], cand[a]
            elif r < 0.8:
                b = rng.randrange(n)
                cand[a], cand[b] = cand[b], cand[a]
            else:
                v = cand.pop(a)
                cand.insert(rng.randrange(n), v)
            npol = pol if rng.random() < 0.95 else rng.randint(0, 1)
            ov2, H2, Wu2, pl2 = _pack_perm(W, cand, npol, Ht)
            frac = (time.time() - t0) / TIME_LIMIT
            temp = T0 * max(0.02, 1.0 - frac)
            d = ov2 - cur
            if d <= 0 or rng.random() < math.exp(-d / temp):
                perm, cur, pol = cand, ov2, npol
                if H2 * Wu2 < best_area:
                    best_area = H2 * Wu2
                    best_out = [list(pl2[idx]) for idx in range(n)]
                    Ht = (best_area - 1) // W
                    ov2b, _, _, _ = _pack_perm(W, perm, pol, Ht)
                    cur = ov2b
                    if best_area == L:
                        break
        # try exact repair of the top band of this width's current packing
        if time.time() < deadline and best_area != L:
            Ht2 = (best_area - 1) // W
            if Ht2 >= m and W * Ht2 >= S:
                _, H3, Wu3, pl3 = _pack_perm(W, perm, pol, Ht2)
                rp = _repair_from(W, Ht2, squares, pl3, S, REPCAP, rng)
                if rp is not None:
                    Hh = max(rp[i][0] + squares[i] for i in range(n))
                    Ww = max(rp[i][1] + squares[i] for i in range(n))
                    if Hh * Ww < best_area:
                        best_area = Hh * Ww
                        best_out = [list(rp[i]) for i in range(n)]
        state[W] = [perm, cur, pol]
    return best_out


if __name__ == '__main__':
    data = sys.stdin.read().split()
    n = int(data[0])
    squares = [int(v) for v in data[1:1 + n]]
    result = pack_squares(squares)
    text = '\n'.join(f"{r} {c}" for r, c in result) + '\n'
    path = os.environ.get('OUTPUT_PATH')
    if path:
        with open(path, 'w') as f:
            f.write(text)
    else:
        sys.stdout.write(text)
