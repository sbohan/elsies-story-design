"""Step 3: turn the skeleton into a graph of strokes (nodes = stroke ends and crossings,
edges = pixel chains), prune thinning spurs and merge crossings. Prints a summary and writes a
debug PNG with node positions so the stroke order can be reasoned about."""
import math, os, pickle, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pngio import write_png

N8 = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]


def build_graph(w, h, skel):
    S = set(p for p in range(w * h) if skel[p])
    def nbrs(p):
        x, y = p % w, p // w
        return [(y + dy) * w + x + dx for dx, dy in N8 if 0 <= x + dx < w and 0 <= y + dy < h and (y + dy) * w + x + dx in S]
    deg = {p: len(nbrs(p)) for p in S}
    special = set(p for p in S if deg[p] != 2)
    # cluster adjacent special pixels into nodes
    node_of, nodes = {}, []
    for p in special:
        if p in node_of: continue
        nid = len(nodes); st = [p]; node_of[p] = nid; mem = []
        while st:
            q = st.pop(); mem.append(q)
            for r in nbrs(q):
                if r in special and r not in node_of: node_of[r] = nid; st.append(r)
        nodes.append(mem)
    # trace edges between nodes
    edges, seen = [], set()
    for nid, mem in enumerate(nodes):
        for p in mem:
            for q in nbrs(p):
                if q in node_of: 
                    if node_of[q] != nid and (min(p, q), max(p, q)) not in seen:
                        seen.add((min(p, q), max(p, q))); edges.append([nid, node_of[q], [p, q]])
                    continue
                if (p, q) in seen: continue
                path = [p, q]; prev, cur = p, q
                while cur not in node_of:
                    nxt = [r for r in nbrs(cur) if r != prev and r not in path[-3:]]
                    if not nxt: break
                    prev, cur = cur, nxt[0]; path.append(cur)
                if cur in node_of:
                    seen.add((path[-1], path[-2])); seen.add((p, q))
                    edges.append([nid, node_of[cur], path])
    # pure loops (no special pixels): add a node at the leftmost pixel
    covered = set(q for e in edges for q in e[2])
    for p in sorted(S - covered - set(node_of), key=lambda p: p % w):
        if p in covered: continue
        nid = len(nodes); nodes.append([p]); node_of[p] = nid
        path = [p]; prev, cur = None, p
        while True:
            nxt = [r for r in nbrs(cur) if r != prev and r not in path]
            if not nxt: break
            prev, cur = cur, nxt[0]; path.append(cur)
        path.append(p); edges.append([nid, nid, path]); covered.update(path)
    pos = [(sum(q % w for q in m) / len(m), sum(q // w for q in m) / len(m)) for m in nodes]
    return nodes, pos, edges


def simplify(w, pos, edges, spur=12, merge=9):
    """Remove short spurs ending in a free end, then merge nodes joined by a short edge (crossings)."""
    changed = True
    while changed:
        changed = False
        deg = {}
        for a, b, path in edges:
            deg[a] = deg.get(a, 0) + 1; deg[b] = deg.get(b, 0) + 1
        for e in list(edges):
            if e[0] == e[1] and len(e[2]) < spur:           # tiny loops left by thinning
                edges.remove(e); changed = True; break
        if changed: continue
        for e in list(edges):
            a, b, path = e
            if a != b and len(path) < spur and ((deg[a] == 1 and deg[b] >= 3) or (deg[b] == 1 and deg[a] >= 3)):
                edges.remove(e); changed = True; break
        if changed: continue
        for e in list(edges):
            a, b, path = e
            if a != b and len(path) <= merge and deg[a] >= 3 and deg[b] >= 3:
                edges.remove(e)
                for f in edges:
                    if f[0] == b: f[0] = a
                    if f[1] == b: f[1] = a
                pos[a] = ((pos[a][0] + pos[b][0]) / 2, (pos[a][1] + pos[b][1]) / 2)
                changed = True; break
        if changed: continue
        # join chains through degree-2 nodes
        for n, d in deg.items():
            if d != 2: continue
            es = [e for e in edges if e[0] == n or e[1] == n]
            if len(es) != 2 or es[0] is es[1]: continue
            e1, e2 = es
            p1 = e1[2] if e1[1] == n else e1[2][::-1]; s1 = e1[0] if e1[1] == n else e1[1]
            p2 = e2[2] if e2[0] == n else e2[2][::-1]; s2 = e2[1] if e2[0] == n else e2[0]
            edges.remove(e1); edges.remove(e2); edges.append([s1, s2, p1 + p2[1:]])
            changed = True; break
    return edges


if __name__ == '__main__':
    d = pickle.load(open(sys.argv[1], 'rb'))
    w, h = d['w'], d['h']
    nodes, pos, edges = build_graph(w, h, d['skel'])
    edges = simplify(w, pos, edges)
    used = sorted(set([e[0] for e in edges] + [e[1] for e in edges]))
    deg = {}
    for a, b, _ in edges: deg[a] = deg.get(a, 0) + 1; deg[b] = deg.get(b, 0) + 1
    print('edges', len(edges), 'nodes', len(used))
    for n in sorted(used, key=lambda n: pos[n][0]):
        print('node %3d (%5.1f,%5.1f) deg %d' % (n, pos[n][0], pos[n][1], deg[n]))
    pickle.dump({'w': w, 'h': h, 'pos': pos, 'edges': edges}, open(sys.argv[2], 'wb'))
    # debug: each edge a different colour, nodes as dots
    img = bytearray(b'\xff' * (w * h * 4))
    for p in range(w * h):
        if d['solid'][p]: img[p * 4:p * 4 + 4] = bytes((225, 222, 220, 255))
    pal = [(220, 40, 60), (30, 120, 200), (40, 160, 70), (230, 140, 20), (140, 60, 180), (0, 160, 160), (180, 100, 40)]
    for i, (a, b, path) in enumerate(edges):
        c = pal[i % len(pal)]
        for q in path: img[q * 4:q * 4 + 4] = bytes(c + (255,))
    for n in used:
        x, y = pos[n]
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                if dx * dx + dy * dy <= 9:
                    q = int(y + dy) * w + int(x + dx); img[q * 4:q * 4 + 4] = bytes((0, 0, 0, 255)) if deg[n] != 1 else bytes((0, 200, 0, 255))
    write_png(sys.argv[2].replace('.pkl', '-graph.png'), w, h, img)
