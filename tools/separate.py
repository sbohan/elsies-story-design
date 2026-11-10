"""Step 2b: split the dark ink into handwriting and butterfly, stroke by stroke.

The butterfly's branch crosses the top of the E, so the two cannot be told apart by position.
Instead every stroke of the skeleton graph is classified (branch line, wing outline, antennae =
butterfly; everything else = handwriting) and each ink pixel goes to the stroke it belongs to.
Where a butterfly stroke crosses a handwriting stroke the pixels go to both layers, so each layer
is whole on its own.

Writes a layer map (bit 1 handwriting, bit 2 butterfly, bit 4 strapline) and the handwriting
graph for the stroke-order step.
"""
import collections, math, os, pickle, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pngio import read_png, write_png

BRANCH = ((58, 208), (176, 100))      # the butterfly's branch, lower-left tip to body, in logo px


def seg_dist(x, y, a=BRANCH[0], b=BRANCH[1]):
    ax, ay = a; bx, by = b; dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - ax - t * dx, y - ay - t * dy)


def main(logo, skel_pkl, graph_pkl, out_pkl, dbg):
    w, h, px = read_png(logo)
    S = pickle.load(open(skel_pkl, 'rb')); G = pickle.load(open(graph_pkl, 'rb'))
    pos, edges = G['pos'], G['edges']
    pink = bytearray(1 if px[p * 4 + 3] and px[p * 4] - px[p * 4 + 1] > 22 and px[p * 4] > 140 else 0 for p in range(w * h))
    # pixels near the pink wings (but not the strapline)
    near_wing = bytearray(w * h)
    for p in range(w * h):
        if pink[p] and p // w < 285:
            x0, y0 = p % w, p // w
            for yy in range(max(0, y0 - 6), min(h, y0 + 7)):
                for xx in range(max(0, x0 - 6), min(w, x0 + 7)): near_wing[yy * w + xx] = 1
    kinds = []
    for a, b, path in edges:
        pts = [(q % w, q // w) for q in path]; n = len(pts)
        on_branch = sum(1 for x, y in pts if seg_dist(x, y) < 6) / n
        by_wing = sum(1 for x, y in pts if near_wing[y * w + x]) / n
        high = sum(1 for x, y in pts if y < 126) / n
        kinds.append('fly' if (on_branch > .75 or by_wing > .6 or high > .85) else 'word')
    # nearest-stroke label for every dark pixel (multi-source BFS through the ink)
    owner = [-1] * (w * h); q = collections.deque()
    for i, (a, b, path) in enumerate(edges):
        for p in path:
            if owner[p] < 0: owner[p] = i; q.append(p)
    dark = bytearray(1 if px[p * 4 + 3] and not pink[p] else 0 for p in range(w * h))
    while q:
        p = q.popleft(); x, y = p % w, p // w
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h:
                    r = ny * w + nx
                    if dark[r] and owner[r] < 0: owner[r] = owner[p]; q.append(r)
    def near_solid_word(p):
        x, y = p % w, p // w
        return any(S['solid'][(y + dy) * w + x + dx] and owner[(y + dy) * w + x + dx] < 0
                   for dx in (-2, -1, 0, 1, 2) for dy in (-2, -1, 0, 1, 2) if 0 <= x + dx < w and 0 <= y + dy < h)
    layer = bytearray(w * h)
    for p in range(w * h):
        if not px[p * 4 + 3]: continue
        if pink[p]: layer[p] = 4 if p // w >= 285 else 2
        elif owner[p] >= 0: layer[p] = 1 if kinds[owner[p]] == 'word' else 2
        elif S['solid'][p] or near_solid_word(p): layer[p] = 1      # solid ink with no stroke through it: the i's dot
        else: layer[p] = 4 if p // w >= 285 else 2               # faint stray edge pixels not joined to any stroke
    # half-width of strokes, then give crossing pixels to both layers
    INF = 10 ** 9; dt = [INF] * (w * h); dq = collections.deque()
    for r in range(w * h):
        if not S['solid'][r]: dt[r] = 0; dq.append(r)
    while dq:
        r = dq.popleft(); x, y = r % w, r // w
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and dt[ny * w + nx] > dt[r] + 1: dt[ny * w + nx] = dt[r] + 1; dq.append(ny * w + nx)
    sk = sorted(dt[p] for a, b, path in edges for p in path)
    cap = sk[len(sk) // 2] + 1          # normal stroke half-width: crossings are wider and must not widen the nib
    for i, (a, b, path) in enumerate(edges):
        bit = 1 if kinds[i] == 'word' else 2
        for p in path:
            x0, y0 = p % w, p // w; R = min(dt[p], cap) + 1.5; Ri = int(R) + 1
            for yy in range(y0 - Ri, y0 + Ri + 1):
                for xx in range(x0 - Ri, x0 + Ri + 1):
                    if 0 <= xx < w and 0 <= yy < h:
                        r = yy * w + xx
                        if dark[r] and math.hypot(xx - x0, yy - y0) <= R: layer[r] |= bit
    word_edges = [e for e, k in zip(edges, kinds) if k == 'word']
    # where the butterfly crosses the handwriting, keep the handwriting's own centre line so the
    # page can redraw that bit of the stroke cleanly (without the branch) at full resolution
    both = [p for p in range(w * h) if layer[p] & 3 == 3]
    clean = []
    if both:
        bx0 = min(p % w for p in both) - 12; bx1 = max(p % w for p in both) + 12
        by0 = min(p // w for p in both) - 12; by1 = max(p // w for p in both) + 12
        clean = [[p % w, p // w] for e in word_edges for p in e[2] if bx0 <= p % w <= bx1 and by0 <= p // w <= by1]
    word_solid = bytearray(1 if S['solid'][p] and layer[p] & 1 else 0 for p in range(w * h))
    pickle.dump({'w': w, 'h': h, 'layer': layer, 'solid': word_solid, 'pos': pos, 'edges': word_edges,
                 'clean': clean, 'half': cap - .4}, open(out_pkl, 'wb'))
    print('strokes: %d handwriting, %d butterfly' % (kinds.count('word'), kinds.count('fly')))
    img = bytearray(b'\xff' * (w * h * 4))
    for p in range(w * h):
        L = layer[p]
        c = {1: (90, 75, 72), 2: (230, 120, 150), 3: (30, 140, 230), 4: (190, 215, 240)}.get(L & 3 if L & 3 else L, None)
        if c: img[p * 4:p * 4 + 3] = bytes(c)
    write_png(dbg, w, h, img)


if __name__ == '__main__':
    main(*sys.argv[1:6])
