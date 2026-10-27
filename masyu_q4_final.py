#!/bin/python3

import math
import os
import random
import re
import sys
import time
import threading

T0 = time.time()
DR = (-1, 0, 1, 0)
DC = (0, 1, 0, -1)
CH = {(0, 2): '|', (1, 3): '-', (0, 1): 'L', (0, 3): 'J', (1, 2): 'F', (2, 3): '7'}


CON = {'.': (), '-': (1, 3), '|': (0, 2), 'L': (0, 1), 'J': (0, 3), 'F': (2, 1), '7': (2, 3)}

def validate(grid, out):
    R = len(grid); C = len(grid[0])
    if len(out) != R or any(len(x) != C for x in out):
        return False
    con = CON
    cells = []
    for r in range(R):
        for c in range(C):
            ch = out[r][c]
            if ch not in con:
                return False
            for d in con[ch]:
                nr, nc = r + DR[d], c + DC[d]
                if not (0 <= nr < R and 0 <= nc < C):
                    return False
                if ((d + 2) % 4) not in con[out[nr][nc]]:
                    return False
            if ch != '.':
                cells.append((r, c))
    if not cells:
        return False
    sr, sc = cells[0]
    r, c = sr, sc
    pd = con[out[r][c]][0]
    r, c = r + DR[pd], c + DC[pd]
    cnt = 1
    while (r, c) != (sr, sc):
        ds = con[out[r][c]]
        nd = ds[0] if ds[0] != (pd + 2) % 4 else ds[1]
        pd = nd
        r, c = r + DR[pd], c + DC[pd]
        cnt += 1
    if cnt != len(cells):
        return False
    for r in range(R):
        for c in range(C):
            gch = grid[r][c]
            if gch == '.':
                continue
            ch = out[r][c]
            if gch == 'W':
                if ch not in '-|':
                    return False
                ok = False
                for d in con[ch]:
                    if out[r + DR[d]][c + DC[d]] in 'LJF7':
                        ok = True
                if not ok:
                    return False
            else:
                if ch not in 'LJF7':
                    return False
                for d in con[ch]:
                    if out[r + DR[d]][c + DC[d]] not in '-|':
                        return False
    return True



class Fail(Exception):
    pass


class Done(Exception):
    pass


def solve_core(grid, budget=7.0):
    R = len(grid); C = len(grid[0])
    N = R * C
    g = [grid[r][c] for r in range(R) for c in range(C)]
    isW = [x == 'W' for x in g]
    isB = [x == 'B' for x in g]
    isP = [x != '.' for x in g]
    pearls = [i for i in range(N) if isP[i]]
    NP = len(pearls)
    nb = [[-1] * 4 for _ in range(N)]
    for i in range(N):
        r, c = divmod(i, C)
        for d in range(4):
            nr, nc = r + DR[d], c + DC[d]
            if 0 <= nr < R and 0 <= nc < C:
                nb[i][d] = nr * C + nc
    # edge ids: cell i east edge = 2i, south edge = 2i+1
    ce = [[-1] * 4 for _ in range(N)]  # ce[i][d] edge id
    E = 2 * N
    ea = [0] * E; eb = [0] * E; ed = [0] * E  # endpoints, direction from ea
    for i in range(N):
        if nb[i][1] >= 0:
            ce[i][1] = 2 * i; ce[nb[i][1]][3] = 2 * i
            ea[2 * i] = i; eb[2 * i] = nb[i][1]; ed[2 * i] = 1
        if nb[i][2] >= 0:
            ce[i][2] = 2 * i + 1; ce[nb[i][2]][0] = 2 * i + 1
            ea[2 * i + 1] = i; eb[2 * i + 1] = nb[i][2]; ed[2 * i + 1] = 2
    es = [0] * E  # 0 unknown, 1 on, 2 off
    valid = [ce[i][1] >= 0 or True for i in range(N)]
    # mark non-existent edges as off permanently: handle via ce == -1 checks
    on_cnt = [0] * N
    unk_cnt = [sum(1 for d in range(4) if ce[i][d] >= 0) for i in range(N)]
    trail = []
    # union find with undo
    par = list(range(N)); sz = [1] * N
    uf_trail = []
    st = {'ends': 0, 'pdone': 0, 'sol': None, 'nodes': 0, 'deadline': T0 + budget, 'best': None, 'non': 0, 'closed': -1, 'bound': None, 'endlist': [], 'prev': [-1] * N, 'wander': 0, 'wlimit': 150}

    def find(x):
        while par[x] != x:
            x = par[x]
        return x

    queue = []

    def set_edge(e, s):
        cur = es[e]
        if cur == s:
            return
        if cur != 0:
            raise Fail
        a = ea[e]; b = eb[e]
        if s == 1:
            ra = find(a); rb = find(b)
            if ra == rb:
                # closing a cycle: valid only if it completes everything
                if st['ends'] == 2 and st['pdone'] + (1 if isP[a] and on_cnt[a] == 1 else 0) + (1 if isP[b] and on_cnt[b] == 1 else 0) == NP and on_cnt[a] == 1 and on_cnt[b] == 1:
                    es[e] = 1; trail.append(e)
                    on_cnt[a] += 1; on_cnt[b] += 1; unk_cnt[a] -= 1; unk_cnt[b] -= 1
                    st['non'] += 1
                    st['ends'] -= 2
                    if isP[a]: st['pdone'] += 1
                    if isP[b]: st['pdone'] += 1
                    st['closed'] = e
                    queue.append(a); queue.append(b)
                    return
                raise Fail
            if sz[ra] < sz[rb]:
                ra, rb = rb, ra
            par[rb] = ra; sz[ra] += sz[rb]; uf_trail.append(rb)
            st['non'] += 1
            # ends
            da = on_cnt[a]; db = on_cnt[b]
            st['ends'] += (1 if da == 0 else -1) + (1 if db == 0 else -1)
            on_cnt[a] += 1; on_cnt[b] += 1
            if isP[a] and on_cnt[a] == 2:
                st['pdone'] += 1
            if isP[b] and on_cnt[b] == 2:
                st['pdone'] += 1
        unk_cnt[a] -= 1; unk_cnt[b] -= 1
        es[e] = s
        trail.append(e)
        queue.append(a); queue.append(b)

    def undo_to(mark, ufmark):
        while len(trail) > mark:
            e = trail.pop()
            a = ea[e]; b = eb[e]
            if es[e] == 1:
                if st['closed'] == e:
                    st['closed'] = -1
                on_cnt[a] -= 1; on_cnt[b] -= 1
                st['non'] -= 1
                if isP[a] and on_cnt[a] == 1:
                    st['pdone'] -= 1
                if isP[b] and on_cnt[b] == 1:
                    st['pdone'] -= 1
                st['ends'] -= (1 if on_cnt[a] == 0 else -1) + (1 if on_cnt[b] == 0 else -1)
            es[e] = 0
            unk_cnt[a] += 1; unk_cnt[b] += 1
        while len(uf_trail) > ufmark:
            rb = uf_trail.pop()
            ra = par[rb]
            sz[ra] -= sz[rb]
            par[rb] = rb

    def propagate():
        while queue:
            i = queue.pop()
            on = on_cnt[i]; unk = unk_cnt[i]
            cei = ce[i]
            if on > 2:
                raise Fail
            if isP[i]:
                if on + unk < 2:
                    raise Fail
                if isW[i]:
                    for d in (0, 1):
                        e1 = cei[d]; e2 = cei[d + 2]
                        if e1 < 0 or e2 < 0:
                            if e1 >= 0 and es[e1] != 2:
                                set_edge(e1, 2)
                            if e2 >= 0 and es[e2] != 2:
                                set_edge(e2, 2)
                            continue
                        s1 = es[e1]; s2 = es[e2]
                        if s1 == 1 or s2 == 1:
                            if s1 != 1: set_edge(e1, 1)
                            if s2 != 1: set_edge(e2, 1)
                            p1 = cei[(d + 1) & 3]; p2 = cei[(d + 3) & 3]
                            if p1 >= 0 and es[p1] != 2: set_edge(p1, 2)
                            if p2 >= 0 and es[p2] != 2: set_edge(p2, 2)
                            # turn constraint
                            n1 = nb[i][d]; n2 = nb[i][d + 2]
                            c1 = ce[n1][d]; c2 = ce[n2][d + 2]
                            t1 = es[c1] if c1 >= 0 else 2
                            t2 = es[c2] if c2 >= 0 else 2
                            if t1 == 1 and t2 == 1:
                                raise Fail
                            if t1 == 1 and c2 >= 0 and t2 == 0:
                                set_edge(c2, 2)
                            elif t2 == 1 and c1 >= 0 and t1 == 0:
                                set_edge(c1, 2)
                        elif s1 == 2 or s2 == 2:
                            if s1 != 2: set_edge(e1, 2)
                            if s2 != 2: set_edge(e2, 2)
                            p1 = cei[(d + 1) & 3]; p2 = cei[(d + 3) & 3]
                            if p1 < 0 or p2 < 0:
                                raise Fail
                            if es[p1] != 1: set_edge(p1, 1)
                            if es[p2] != 1: set_edge(p2, 1)
                else:  # black
                    for d in range(4):
                        e1 = cei[d]
                        if e1 < 0:
                            continue
                        s1 = es[e1]
                        n1 = nb[i][d]
                        c1 = ce[n1][d]
                        if s1 == 0:
                            if c1 < 0 or es[c1] == 2:
                                set_edge(e1, 2)
                                continue
                            # neighbor n1 must be able to go straight: also if n1 is black -> impossible
                            if isB[n1]:
                                set_edge(e1, 2)
                                continue
                            q1 = ce[n1][(d + 1) & 3]; q2 = ce[n1][(d + 3) & 3]
                            if (q1 >= 0 and es[q1] == 1) or (q2 >= 0 and es[q2] == 1):
                                set_edge(e1, 2)
                                continue
                        if s1 == 1:
                            e2 = cei[(d + 2) & 3]
                            if e2 >= 0 and es[e2] != 2:
                                set_edge(e2, 2)
                            if c1 < 0:
                                raise Fail
                            if es[c1] != 1:
                                set_edge(c1, 1)
                        elif s1 == 2:
                            e2 = cei[(d + 2) & 3]
                            if e2 < 0:
                                raise Fail
                            if es[e2] != 1:
                                set_edge(e2, 1)
                on = on_cnt[i]; unk = unk_cnt[i]
            if on == 2:
                if unk:
                    for d in range(4):
                        e = cei[d]
                        if e >= 0 and es[e] == 0:
                            set_edge(e, 2)
            elif on == 1:
                if unk == 0:
                    raise Fail
                if unk > 1:
                    # premature closure prevention: unknown edge to the other end of the same path must be off
                    ri = find(i)
                    nbi = nb[i]
                    for d in range(4):
                        e = cei[d]
                        if e >= 0 and es[e] == 0:
                            y = nbi[d]
                            if on_cnt[y] == 1 and find(y) == ri:
                                if not (st['ends'] == 2 and st['pdone'] + (1 if isP[i] else 0) + (1 if isP[y] else 0) == NP):
                                    set_edge(e, 2)
                    unk = unk_cnt[i]
                if unk == 0:
                    raise Fail
                if unk == 1:
                    for d in range(4):
                        e = cei[d]
                        if e >= 0 and es[e] == 0:
                            set_edge(e, 1)
            else:
                if unk == 1:
                    for d in range(4):
                        e = cei[d]
                        if e >= 0 and es[e] == 0:
                            set_edge(e, 2)

    rows = [i // C for i in range(N)]
    stamp = [0] * N
    stamp2 = [0] * N
    stampv = [0]
    cols = [i % C for i in range(N)]
    sys.setrecursionlimit(100000)

    def pick():
        # pending pearl with fewest unknown edges first
        best = -1; bu = 9
        for p in pearls:
            if on_cnt[p] < 2:
                u = unk_cnt[p] - (2 - on_cnt[p])
                if u < bu:
                    bu = u; best = p
                    if u <= 0:
                        break
        if best >= 0:
            return best
        # most constrained path end (fewest unknown edges); ties -> most recently extended
        best = -1; bu = 9
        for k in range(len(trail) - 1, -1, -1):
            e = trail[k]
            if es[e] == 1:
                a = ea[e]; b = eb[e]
                if on_cnt[a] == 1 and unk_cnt[a] < bu:
                    bu = unk_cnt[a]; best = a
                if on_cnt[b] == 1 and unk_cnt[b] < bu:
                    bu = unk_cnt[b]; best = b
                if bu <= 1:
                    break
        if best >= 0:
            return best
        # no path end: pick a pearl not done
        for p in pearls:
            if on_cnt[p] < 2:
                return p
        return -1

    def other_end(u):
        prev = -1; cur = u
        while True:
            cec = ce[cur]; nbc = nb[cur]
            nxt = -1
            for d in range(4):
                e = cec[d]
                if e >= 0 and es[e] == 1 and nbc[d] != prev:
                    nxt = nbc[d]
                    break
            if nxt < 0:
                return cur
            prev, cur = cur, nxt
            if on_cnt[cur] == 1:
                return cur

    def check_closed():
        if st['closed'] >= 0:
            out = build()
            if out is not None and validate(grid, out):
                st['sol'] = out
                raise Done
            raise Fail

    def build():
        out = [['.'] * C for _ in range(R)]
        for i in range(N):
            ds = tuple(d for d in range(4) if ce[i][d] >= 0 and es[ce[i][d]] == 1)
            if ds:
                if len(ds) != 2:
                    return None
                out[i // C][i % C] = CH[ds]
        return [''.join(x) for x in out]

    def search():
        st['nodes'] += 1
        if (st['nodes'] & 63) == 0 and time.time() > st['deadline']:
            raise Done
        i = pick()
        if i < 0:
            raise Fail  # no ends, pearls done, but no closure -> inconsistent
        if st['pdone'] == NP:
            st['wander'] += 1
            if st['wander'] > st['wlimit']:
                raise Fail
        else:
            st['wander'] = 0
        # reachability: BFS from i over non-off edges; cells with 2 on-edges only via those edges.
        # must reach all other ends and all untouched pearls
        stampv[0] += 1
        sv = stampv[0]
        stamp[i] = sv
        need = 0
        for p in pearls:
            if on_cnt[p] == 0 and p != i:
                need += 1
        need += st['ends'] - (1 if on_cnt[i] == 1 else 0)
        stack = [i]
        while stack and need > 0:
            x = stack.pop()
            cex = ce[x]; nbx = nb[x]
            full = on_cnt[x] == 2
            for d in range(4):
                e = cex[d]
                if e >= 0:
                    s = es[e]
                    if s == 2 or (full and s == 0):
                        continue
                    y = nbx[d]
                    if stamp[y] != sv:
                        stamp[y] = sv
                        oy = on_cnt[y]
                        if oy == 1 or (oy == 0 and isP[y]):
                            need -= 1
                        stack.append(y)
        if need > 0:
            raise Fail
        B = st['bound']
        if B is not None:
            # lower bound on final loop length: on edges + half the sum of end-to-nearest-other-end distances
            lb = 0
            endsl = st['endlist']
            del endsl[:]
            for e2 in trail:
                if es[e2] == 1:
                    a = ea[e2]; b = eb[e2]
                    if on_cnt[a] == 1 and stamp2[a] != sv:
                        stamp2[a] = sv; endsl.append(a)
                    if on_cnt[b] == 1 and stamp2[b] != sv:
                        stamp2[b] = sv; endsl.append(b)
            if len(endsl) >= 2:
                tot = 0
                for u in endsl:
                    ur = rows[u]; uc = cols[u]
                    bd = 10 ** 9
                    for v in endsl:
                        if v != u:
                            w = abs(rows[v] - ur) + abs(cols[v] - uc)
                            if w < bd:
                                bd = w
                    tot += bd
                lb = (tot + 1) // 2
            if st['non'] + lb > B:
                raise Fail
        if on_cnt[i] == 1 and st['ends'] == 2 and st['pdone'] == NP:
            # terminal phase: connect the two ends by BFS shortest path over free cells
            oe = other_end(i)
            stampv[0] += 1
            sv2 = stampv[0]
            stamp[i] = sv2
            prev = st['prev']
            prev[i] = -1
            frontier = [i]
            found = False
            while frontier and not found:
                nf = []
                for x in frontier:
                    cex = ce[x]; nbx = nb[x]
                    for d in range(4):
                        e = cex[d]
                        if e >= 0 and es[e] == 0:
                            y = nbx[d]
                            if stamp[y] != sv2:
                                stamp[y] = sv2
                                if y == oe:
                                    prev[y] = x; found = True; break
                                if on_cnt[y] == 0:
                                    prev[y] = x
                                    nf.append(y)
                    if found:
                        break
                frontier = nf
            if not found:
                raise Fail
            pc = []
            y = oe
            while y != -1:
                pc.append(y)
                y = prev[y]
            mark = len(trail); ufmark = len(uf_trail)
            try:
                queue.clear()
                for k in range(len(pc) - 1):
                    a = pc[k]; b = pc[k + 1]
                    for d in range(4):
                        if nb[a][d] == b:
                            set_edge(ce[a][d], 1)
                            break
                propagate()
                check_closed()
            except Fail:
                pass
            undo_to(mark, ufmark)
        elif on_cnt[i] == 1 and st['pdone'] == NP:
            # all pearls done, >2 ends: end i must reach some other path's end via free cells
            oe = other_end(i)
            stampv[0] += 1
            sv2 = stampv[0]
            stamp[i] = sv2
            prev = st['prev']
            prev[i] = -1
            frontier = [i]
            tgt = -1
            while frontier and tgt < 0:
                nf = []
                for x in frontier:
                    cex = ce[x]; nbx = nb[x]
                    for d in range(4):
                        e = cex[d]
                        if e >= 0 and es[e] == 0:
                            y = nbx[d]
                            if stamp[y] != sv2:
                                stamp[y] = sv2
                                oy = on_cnt[y]
                                if oy == 1 and y != oe:
                                    prev[y] = x; tgt = y; break
                                if oy == 0:
                                    prev[y] = x
                                    nf.append(y)
                    if tgt >= 0:
                        break
                frontier = nf
            if tgt < 0:
                raise Fail
            pc = []
            y = tgt
            while y != -1:
                pc.append(y)
                y = prev[y]
            mark = len(trail); ufmark = len(uf_trail)
            try:
                queue.clear()
                for k in range(len(pc) - 1):
                    a = pc[k]; b = pc[k + 1]
                    for d in range(4):
                        if nb[a][d] == b:
                            set_edge(ce[a][d], 1)
                            break
                propagate()
                check_closed()
                search()
            except Fail:
                pass
            undo_to(mark, ufmark)
        cands = [ce[i][d] for d in range(4) if ce[i][d] >= 0 and es[ce[i][d]] == 0]
        if not cands:
            raise Fail
        # order: toward nearest pending pearl
        if len(cands) > 1:
            tgt = -1; bd = 10 ** 9
            ir = rows[i]; ic = cols[i]
            for p in pearls:
                if on_cnt[p] < 2 and p != i:
                    v = abs(rows[p] - ir) + abs(cols[p] - ic)
                    if v < bd:
                        bd = v; tgt = p
            if tgt < 0 and on_cnt[i] == 1:
                ir = rows[i]; ic = cols[i]
                for e2 in trail:
                    if es[e2] == 1:
                        for u in (ea[e2], eb[e2]):
                            if u != i and on_cnt[u] == 1:
                                v = abs(rows[u] - ir) + abs(cols[u] - ic)
                                if v < bd:
                                    bd = v; tgt = u
            if tgt >= 0:
                tr = rows[tgt]; tc = cols[tgt]
                def key(e):
                    o = eb[e] if ea[e] == i else ea[e]
                    return abs(rows[o] - tr) + abs(cols[o] - tc)
                cands.sort(key=key)
        for e in cands:
            mark = len(trail); ufmark = len(uf_trail)
            try:
                queue.clear()
                set_edge(e, 1)
                propagate()
                check_closed()
                search()
            except Fail:
                pass
            undo_to(mark, ufmark)
            # the edge e must now be off
            try:
                queue.clear()
                set_edge(e, 2)
                propagate()
                check_closed()
            except Fail:
                undo_to(mark, ufmark)
                raise Fail
        raise Fail

    # initial propagation: all cells
    try:
        for i in range(N):
            queue.append(i)
        propagate()
        check_closed()
    except Done:
        return st['sol']
    except Fail:
        return None
    base_mark = len(trail); base_uf = len(uf_trail)
    base_non = st['non']
    best = [None]

    def run_search(deadline):
        st['deadline'] = deadline
        st['nodes'] = 0
        try:
            search()
        except Done:
            pass
        except Fail:
            return 'exhausted'
        undo_to(base_mark, base_uf)
        if st['sol'] is not None:
            return 'found'
        return 'timeout'

    for wl in (30, 300, 3000, 10 ** 9):
        st['wlimit'] = wl
        # phase 1: unbounded quick search
        st['bound'] = None
        r = run_search(min(T0 + 0.8, T0 + budget))
        if r == 'found':
            best[0] = st['sol']
            bestL = sum(1 for row in best[0] for ch in row if ch != '.')
            st['sol'] = None
            B = max(base_non, 4)
            while B < bestL - 1 and time.time() < T0 + 1.2:
                st['bound'] = B
                r = run_search(T0 + 1.2)
                if r == 'found':
                    best[0] = st['sol']; st['sol'] = None
                    bestL = sum(1 for row in best[0] for ch in row if ch != '.')
                    break
                if r == 'timeout':
                    break
                B = int(B * 1.1) + 2
            return best[0]
        # phase 2: iterative bounded search
        B = max(base_non, 4)
        exhausted_all = True
        while time.time() < T0 + budget:
            st['bound'] = B
            r = run_search(T0 + budget)
            if r == 'found':
                return st['sol']
            if r == 'timeout':
                exhausted_all = False
                break
            B = int(B * 1.15) + 2
            if B > 2 * N + 10:
                break
        if time.time() >= T0 + budget:
            return None
    return None


def solve(grid):
    res = [None]
    def run():
        res[0] = solve_core(grid)
    threading.stack_size(512 * 1024 * 1024)
    t = threading.Thread(target=run)
    t.start()
    t.join()
    out = res[0]
    if out is None:
        out = ['.' * len(grid[0]) for _ in grid]
    return out

if __name__ == '__main__':
    fptr = open(os.environ['OUTPUT_PATH'], 'w')

    grid_count = int(input().strip())

    grid = []

    for _ in range(grid_count):
        grid_item = input()
        grid.append(grid_item)

    result = solve(grid)

    fptr.write('\n'.join(result))
    fptr.write('\n')

    fptr.close()
