"""Step 4-5: order the strokes the way a hand writes them, time them, and give every ink pixel of
the logo the moment the pen reaches it.

Rules
- Words are written left to right; each word's connected pieces in order of their left edge.
- A piece starts at its left-most free end and follows the straightest way on at every join, so the
  pen carries through crossings (the loop of the l, the bowl of the y).
- When the pen runs out of road it retraces wet ink to the nearest unfinished join ahead (as a hand
  does on an i or t), or lifts and moves on. Anything left behind (the t's cross) is done after
  the word.
- Details come last: the dot on the i is dabbed and the apostrophe is flicked down, after the word.
- Speed follows curvature: slower on tight turns, quicker on straight runs, easing in and out.

Writes a deflated Uint16 time map (ms + 1 per logo pixel, 0 = not handwriting) and the pen path.
"""
import heapq, json, math, os, pickle, sys, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pngio import read_png, write_png
from skeleton import classify, components

V_MAX, V_RETRACE, V_AIR = 980.0, 1300.0, 1900.0       # px per second (logo is 1000 px wide)
LIFT_PAUSE, WORD_PAUSE, DETAIL_PAUSE, DAB = .06, .18, .14, .18


def main(sep_pkl, logo, out_dir, dbg_dir):
    S = pickle.load(open(sep_pkl, 'rb')); G = S
    w, h, px = read_png(logo)
    pos, edges = G['pos'], G['edges']
    xy = lambda p: (p % w, p // w)

    # which solid component each edge belongs to
    lab, comps = components(w, h, S['solid'])
    for e in edges: e.append(lab[e[2][len(e[2]) // 2]])
    big = {i + 1 for i, c in enumerate(comps) if len(c) >= 40}
    detail = {i for i in big if len(comps[i - 1]) < 1000}
    minx = {i: min(q % w for q in comps[i - 1]) for i in big}
    word_of = lambda c: 0 if minx[c] < 560 else 1

    def edir(e, at_start, n=10):
        path = e[2] if at_start else e[2][::-1]
        a, b = xy(path[0]), xy(path[min(n, len(path) - 1)])
        dx, dy = b[0] - a[0], b[1] - a[1]; l = math.hypot(dx, dy) or 1
        return dx / l, dy / l

    def traverse(eids, start, allow_defer=True):
        """Return a list of moves (kind, path) and the edges deferred for later."""
        todo = set(eids); moves = []; adj = {}
        for i in eids:
            a, b = edges[i][0], edges[i][1]
            adj.setdefault(a, []).append(i); adj.setdefault(b, []).append(i)
        node, d = start, None
        passed = {start}
        while todo:
            cand = [i for i in adj.get(node, []) if i in todo]
            if cand:
                def score(i):
                    e = edges[i]; o = edir(e, e[0] == node)
                    return (o[0] * d[0] + o[1] * d[1]) if d else (o[1] * .3 - abs(o[0]) * .1)
                i = max(cand, key=score); e = edges[i]; todo.discard(i)
                path = e[2] if e[0] == node else e[2][::-1]
                moves.append(('ink', path))
                nd = e[1] if e[0] == node else e[0]
                ex = edir(e, e[0] != node); d = (-ex[0], -ex[1])
                node = nd; passed.add(nd); continue
            # stuck: at the end of a stroke, a nearby free end is where the pen goes next (the t's cross)
            cx = pos[node][0]
            if len(adj.get(node, [])) == 1:
                def into_crossing(n):                          # its stroke runs into a crossing already passed through
                    e = edges[adj[n][0]]; m = e[1] if e[0] == n else e[0]
                    return len(adj.get(m, [])) >= 4 and m in passed
                free = [n for n in adj if len(adj[n]) == 1 and any(i in todo for i in adj[n]) and into_crossing(n)
                        and pos[n][0] >= cx - 60 and math.hypot(pos[n][0] - cx, pos[n][1] - pos[node][1]) < 115]
                if free:
                    tgt = min(free, key=lambda n: math.hypot(pos[n][0] - cx, pos[n][1] - pos[node][1]))
                    moves.append(('lift', (pos[node], pos[tgt]))); node, d = tgt, None; continue
            # otherwise retrace over wet ink to an unfinished join ahead, or lift the pen
            targets = {n for i in todo for n in edges[i][:2]}
            ahead = {n for n in targets if pos[n][0] >= cx - 15}
            dist, prev = {node: 0}, {}
            pq = [(0, node)]
            while pq:
                dd, n = heapq.heappop(pq)
                if dd > dist.get(n, 1e9) or dd > 140: continue
                for i in adj.get(n, []):
                    if i in todo: continue
                    e = edges[i]; m = e[1] if e[0] == n else e[0]
                    nd2 = dd + len(e[2])
                    if nd2 < dist.get(m, 1e9): dist[m] = nd2; prev[m] = (n, i); heapq.heappush(pq, (nd2, m))
            reach = [n for n in targets if n in dist and n != node and (n in ahead or dist[n] <= 90)]
            if reach:
                tgt = min(reach, key=lambda n: dist[n]); chain = []
                n = tgt
                while n != node:
                    pn, i = prev[n]; e = edges[i]
                    chain.append(e[2] if e[0] == pn else e[2][::-1]); n = pn
                for path in reversed(chain): moves.append(('retrace', path))
                node, d = tgt, None; continue
            pool = ahead if (ahead or not allow_defer) else set()
            if not pool and not allow_defer: pool = targets
            if not pool:
                return moves, sorted(todo)
            tgt = min(pool, key=lambda n: (pos[n][0] - cx) ** 2 + (pos[n][1] - pos[node][1]) ** 2)
            # prefer a free end as the place to put the pen down
            ends = [n for n in pool if sum(1 for i in adj[n] if i in todo) == 1 and len(adj[n]) == 1]
            if ends: tgt = min(ends, key=lambda n: (pos[n][0] - cx) ** 2 + (pos[n][1] - pos[node][1]) ** 2)
            moves.append(('lift', (pos[node], pos[tgt])))
            node, d = tgt, None
        return moves, []

    def start_node(eids, top=False):
        deg = {}
        for i in eids:
            for n in edges[i][:2]: deg[n] = deg.get(n, 0) + 1
        ends = [n for n, k in deg.items() if k == 1] or list(deg)
        if top: return min(ends, key=lambda n: pos[n][1])
        for n in sorted(ends, key=lambda n: pos[n][0]):          # a downstroke into a crossing goes first
            e = next(edges[i] for i in eids if n in edges[i][:2])
            m = e[1] if e[0] == n else e[0]
            dx, dy = pos[m][0] - pos[n][0], pos[m][1] - pos[n][1]
            if deg.get(m, 0) >= 4 and dy > 25 and abs(dx) < dy * .5: return n
        return min(ends, key=lambda n: pos[n][0])

    plan = []   # list of (kind, payload)
    for word in (0, 1):
        mains = sorted([c for c in big if word_of(c) == word and c not in detail], key=lambda c: minx[c])
        later = []
        for c in mains:
            eids = [i for i, e in enumerate(edges) if e[3] == c]
            moves, deferred = traverse(eids, start_node(eids))
            if plan and plan[-1][0] != 'pause': plan.append(('lift', None))
            plan.extend(moves); later.extend(deferred)
        if later:
            plan.append(('pause', DETAIL_PAUSE))
            groups = {}
            for i in later: groups.setdefault(edges[i][3], []).append(i)
            for c, eids in groups.items():
                plan.append(('lift', None))
                moves, _ = traverse(eids, start_node(eids), allow_defer=False); plan.extend(moves)
        for c in sorted([c for c in big if word_of(c) == word and c in detail], key=lambda c: minx[c]):
            plan.append(('pause', DETAIL_PAUSE)); plan.append(('lift', None))
            eids = [i for i, e in enumerate(edges) if e[3] == c]
            if eids:
                moves, _ = traverse(eids, start_node(eids, top=True), allow_defer=False); plan.extend(moves)
            else:
                pts = comps[c - 1]
                plan.append(('dab', (sum(q % w for q in pts) / len(pts), sum(q // w for q in pts) / len(pts), c)))
        plan.append(('pause', WORD_PAUSE))

    # ── timing: one continuous stroke = consecutive ink/retrace moves without a lift ──
    strokes, cur = [], None
    for kind, pl in plan:
        if kind in ('ink', 'retrace'):
            if cur is None: cur = []; strokes.append(('stroke', cur))
            cur.append((kind, pl))
        else:
            cur = None; strokes.append((kind, pl))
    t = 0.0; pen = []; t_skel = {}; dabs = []; last = None; runs = []
    def run(moves):
        nonlocal t, last
        seq = []; rec = []
        for kind, path in moves:
            for p in (path if not seq else path[1:]): seq.append((kind, p))
        pts = [xy(p) for _, p in seq]; n = len(pts)
        arc = [0.0]
        for k in range(1, n): arc.append(arc[-1] + math.hypot(pts[k][0] - pts[k - 1][0], pts[k][1] - pts[k - 1][1]))
        L = arc[-1] or 1
        for k in range(n):
            kind, p = seq[k]
            a = pts[max(0, k - 6)]; b = pts[k]; c = pts[min(n - 1, k + 6)]
            v1 = (b[0] - a[0], b[1] - a[1]); v2 = (c[0] - b[0], c[1] - b[1])
            l1, l2 = math.hypot(*v1) or 1, math.hypot(*v2) or 1
            ang = math.acos(max(-1, min(1, (v1[0] * v2[0] + v1[1] * v2[1]) / (l1 * l2))))
            v = (V_RETRACE if kind == 'retrace' else V_MAX) * (.5 + .5 * math.exp(-ang * 2.2))
            v *= min(1, .45 + arc[k] / 45) * min(1, .5 + (L - arc[k]) / 35)    # ease in and out of the stroke
            if k: t += (arc[k] - arc[k - 1]) / v
            if kind == 'ink' and p not in t_skel: t_skel[p] = t
            pen.append((t, b[0], b[1], 1)); rec.append((p, t))
        last = pts[-1]; runs.append(rec)
    for kind, pl in strokes:
        if kind == 'pause': t += pl
        elif kind == 'lift':
            if last: pen.append((t, last[0], last[1], 0))
        elif kind == 'stroke':
            if last:
                b = xy(pl[0][1][0]); dd = math.hypot(b[0] - last[0], b[1] - last[1])
                if dd > 2: t += dd / V_AIR + LIFT_PAUSE; pen.append((t, b[0], b[1], 0))
            run(pl)
        elif kind == 'dab':
            x, y, c = pl
            if last: t += math.hypot(x - last[0], y - last[1]) / V_AIR + LIFT_PAUSE
            pen.append((t, x, y, 1)); dabs.append((t, x, y, c)); t += DAB; last = (x, y)
    total = t

    # ── every handwriting pixel gets the time the pen reaches it ──
    cls = bytearray(1 if S['layer'][p] & 1 else 0 for p in range(w * h))
    solid = S['solid']
    # half-width of the stroke at each point: distance to the nearest non-ink pixel
    import collections
    INF = 10 ** 9; dt = [INF] * (w * h); q = collections.deque()
    for r in range(w * h):
        if not solid[r]: dt[r] = 0; q.append(r)
    while q:
        r = q.popleft(); x, y = r % w, r // w
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and dt[ny * w + nx] > dt[r] + 1:
                dt[ny * w + nx] = dt[r] + 1; q.append(ny * w + nx)
    tm = [None] * (w * h)
    sk = sorted(dt[p] for p in t_skel); cap = sk[len(sk) // 2] + 1
    for p, ts in sorted(t_skel.items(), key=lambda kv: kv[1]):
        x0, y0 = p % w, p // w; R = min(dt[p], cap) + .7; Ri = int(R) + 1
        for yy in range(y0 - Ri, y0 + Ri + 1):
            for xx in range(x0 - Ri, x0 + Ri + 1):
                if 0 <= xx < w and 0 <= yy < h:
                    r = yy * w + xx; dd = math.hypot(xx - x0, yy - y0)
                    if dd <= R and cls[r] == 1 and tm[r] is None: tm[r] = ts + dd * .0015
    # soft edges and pixels outside the capped nib: each belongs to the centre line it sits closest
    # to, measured against that stroke's own width, so crossings don't leak slivers of later strokes
    bestd = {}
    for p, ts in t_skel.items():
        x0, y0 = p % w, p // w; R = dt[p] + 2.5; Ri = int(R) + 1
        for yy in range(y0 - Ri, y0 + Ri + 1):
            for xx in range(x0 - Ri, x0 + Ri + 1):
                if 0 <= xx < w and 0 <= yy < h:
                    r = yy * w + xx
                    if cls[r] == 1 and tm[r] is None:
                        dd = math.hypot(xx - x0, yy - y0)
                        if dd <= R:
                            score = dd - dt[p]
                            if r not in bestd or score < bestd[r][0]: bestd[r] = (score, ts + dd * .0015)
    for r, (_, ts) in bestd.items(): tm[r] = ts
    near_dab = lambda x, y: any(abs(x - dx2) < 14 and abs(y - dy2) < 14 for _, dx2, dy2, _ in dabs)
    hp = [(tm[r], r) for r in range(w * h) if tm[r] is not None]
    heapq.heapify(hp)
    while hp:
        ts, r = heapq.heappop(hp)
        if ts > tm[r]: continue
        x, y = r % w, r // w
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h:
                    s = ny * w + nx
                    if cls[s] == 1 and tm[s] is None and not near_dab(nx, ny):
                        tm[s] = ts + .001; heapq.heappush(hp, (tm[s], s))
    # the dot's own pixels (and its soft edge) grow out from the centre
    for ts, x, y, c in dabs:
        for yy in range(int(y) - 16, int(y) + 17):
            for xx in range(int(x) - 16, int(x) + 17):
                r = yy * w + xx
                if 0 <= xx < w and 0 <= yy < h and cls[r] == 1 and tm[r] is None:
                    tm[r] = ts + math.hypot(xx - x, yy - y) / 10 * DAB * .8
    for r in range(w * h):
        if cls[r] == 1 and tm[r] is None: tm[r] = total
    clean, zone, half, in_zone = [], None, 6, set()
    both = [r for r in range(w * h) if S['layer'][r] & 3 == 3]
    if both and runs:
        zone = [min(r % w for r in both) - 12, min(r // w for r in both) - 12, max(r % w for r in both) + 12, max(r // w for r in both) + 12]
        E = runs[0]; n = len(E)
        inside = [i for i, (p, ts) in enumerate(E) if zone[0] <= p % w <= zone[2] and zone[1] <= p // w <= zone[3]]
        if inside:
            i0, i1 = max(0, inside[0] - 3), min(n - 1, inside[-1] + 3)
            P0, P1 = xy(E[i0][0]), xy(E[i1][0]); A, B = xy(E[max(0, i0 - 8)][0]), xy(E[min(n - 1, i1 + 8)][0])
            ch = math.hypot(P1[0] - P0[0], P1[1] - P0[1])
            def unit(v): l = math.hypot(*v) or 1; return (v[0] / l, v[1] / l)
            T0 = unit((P0[0] - A[0], P0[1] - A[1])); T1 = unit((B[0] - P1[0], B[1] - P1[1]))
            t0, t1 = E[i0][1], E[i1][1]
            def curve(s):
                h00, h10, h01, h11 = 2*s**3 - 3*s**2 + 1, s**3 - 2*s**2 + s, -2*s**3 + 3*s**2, s**3 - s**2
                return (h00 * P0[0] + h10 * T0[0] * ch + h01 * P1[0] + h11 * T1[0] * ch,
                        h00 * P0[1] + h10 * T0[1] * ch + h01 * P1[1] + h11 * T1[1] * ch)
            for k in range(0, 201):
                s = k / 200; x, y = curve(s); clean.append([round(x, 2), round(y, 2), round((t0 + (t1 - t0) * s) * 1000)])
            for i in list(range(max(0, i0 - 14), i0)) + list(range(i1 + 1, min(n, i1 + 15))):
                x, y = xy(E[i][0]); clean.append([x, y, round(E[i][1] * 1000)])
            def edist(p):                                   # true distance from the centre line to the stroke's edge
                x0, y0 = p % w, p // w; best = 99
                for yy in range(y0 - 14, y0 + 15):
                    for xx in range(x0 - 14, x0 + 15):
                        if 0 <= xx < w and 0 <= yy < h and px[(yy * w + xx) * 4 + 3] < 128:
                            best = min(best, math.hypot(xx - x0, yy - y0))
                return best
            ws = sorted(edist(E[i][0]) for i in list(range(max(0, i0 - 12), i0)) + list(range(i1 + 1, min(n, i1 + 13))))
            half = ws[len(ws) // 2] - .5
            pen = [(ts, *curve((ts - t0) / (t1 - t0)), dn) if t0 < ts < t1 else (ts, x, y, dn) for ts, x, y, dn in pen]
            # the zone, pixel by pixel: near the fitted curve, and closest to this stretch of the E
            # (not to another stroke such as the E's middle bar)
            seg = set(E[i][0] for i in range(max(0, i0 - 14), min(n, i1 + 15)))
            wsk = list(t_skel.keys()); R = half + 11
            cpts = [(c[0], c[1]) for c in clean[:201]]
            for yy in range(zone[1], zone[3] + 1):
                for xx in range(zone[0], zone[2] + 1):
                    r = yy * w + xx
                    if not S['layer'][r] & 3: continue
                    if min((xx - cx) ** 2 + (yy - cy) ** 2 for cx, cy in cpts) > R * R: continue
                    best, bq = 1e9, None
                    for q in wsk:
                        dq = (q % w - xx) ** 2 + (q // w - yy) ** 2
                        if dq < best: best, bq = dq, q
                    if bq in seg or best > 196 or not S['layer'][r] & 1: in_zone.add(r)
    arr = bytearray(w * h * 3)
    for r in range(w * h):
        if tm[r] is not None:
            v = min(65000, int(tm[r] * 1000) + 1); arr[r * 2] = v & 255; arr[r * 2 + 1] = v >> 8
    arr[w * h * 2:] = S['layer']   # bit 1 handwriting, 2 butterfly, 4 strapline, 8 where the E is redrawn clean
    for r in in_zone: arr[w * h * 2 + r] |= 8
    # stray handwriting specks near the E that sit on no handwriting stroke belong to the butterfly
    if zone:
        wsk = list(t_skel.keys())
        for yy in range(zone[1] - 6, zone[3] + 7):
            for xx in range(zone[0] - 6, zone[2] + 7):
                r = yy * w + xx
                if 0 <= xx < w and 0 <= yy < h and arr[w * h * 2 + r] & 1 and not arr[w * h * 2 + r] & 8:
                    if min((q % w - xx) ** 2 + (q // w - yy) ** 2 for q in wsk) > (half + 2.5) ** 2:
                        arr[w * h * 2 + r] = (arr[w * h * 2 + r] & ~1) | 2
    os.makedirs(out_dir, exist_ok=True)
    import base64
    packed = base64.b64encode(zlib.compress(bytes(arr), 9)).decode()
    # pen path, thinned to ~every 10 ms
    keep, lt = [], -1
    for i, (ts, x, y, down) in enumerate(pen):
        if ts - lt >= .01 or i == len(pen) - 1 or down != pen[i - 1][3]:
            keep.append([round(ts * 1000), round(x / w, 4), round(y / h, 4), down]); lt = ts
    json.dump({'w': w, 'h': h, 'total': round(total * 1000), 'pen': keep,
               'map': packed, 'clean': clean, 'half': round(half, 2), 'zone': zone},   # zlib: Uint16 ms+1 per pixel, then Uint8 layer bits (1 writing, 2 butterfly, 4 strapline)
              open(os.path.join(out_dir, 'logo-write.json'), 'w'), separators=(',', ':'))
    print('writing takes %.2fs, %d pen samples, %d dabs' % (total, len(keep), len(dabs)))
    print('plan:', ' '.join(k[0][0] for k in plan))

    # ── debug: frames at even steps, cropped to the handwriting ──
    if dbg_dir:
        y0, y1 = 120, 380; fh = y1 - y0; steps = 10
        img = bytearray(b'\xff' * (w * fh * steps * 4))
        for s in range(steps):
            T = total * (s + 1) / steps
            for yy in range(y0, y1):
                for xx in range(w):
                    r = yy * w + xx; o = ((s * fh + yy - y0) * w + xx) * 4
                    if cls[r] == 1 and tm[r] is not None and tm[r] <= T:
                        a = px[r * 4 + 3] / 255
                        for k in range(3): img[o + k] = int(255 * (1 - a) + px[r * 4 + k] * a)
            pt = max((p for p in pen if p[0] <= T), key=lambda p: p[0])
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    if dx * dx + dy * dy <= 16:
                        xx, yy = int(pt[1]) + dx, int(pt[2]) + dy
                        if 0 <= xx < w and y0 <= yy < y1:
                            o = ((s * fh + yy - y0) * w + xx) * 4; img[o:o + 3] = bytes((220, 30, 70) if pt[3] else (40, 120, 220))
            for xx in range(w):
                o = ((s * fh) * w + xx) * 4; img[o:o + 3] = bytes((200, 200, 200))
        write_png(os.path.join(dbg_dir, 'frames.png'), w, fh * steps, img)


if __name__ == '__main__':
    main(*sys.argv[1:5])
