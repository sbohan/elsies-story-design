"""Step 1-2: isolate the handwriting in the logo and thin it to one-pixel centre lines.

Outputs a pickle used by the stroke builder, plus a debug PNG.
"""
import os, pickle, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pngio import read_png, write_png

FLY = [(0, 0), (262, 0), (262, 126), (150, 134), (116, 152), (102, 196), (58, 220), (0, 214)]


def inpoly(x, y, P=FLY):
    c = False; j = len(P) - 1
    for i in range(len(P)):
        xi, yi = P[i]; xj, yj = P[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi: c = not c
        j = i
    return c


def classify(w, h, px):
    """0 nothing, 1 handwriting, 2 butterfly, 3 strapline. Uses any alpha so edges are kept."""
    cls = bytearray(w * h)
    for p in range(w * h):
        r, g, b, a = px[p * 4:p * 4 + 4]
        if a == 0: continue
        x, y = p % w, p // w
        pink = r - g > 22 and r > 140
        if pink and y > 285: cls[p] = 3
        elif pink or inpoly(x, y): cls[p] = 2
        else: cls[p] = 1
    return cls


def components(w, h, mask):
    lab = [0] * (w * h); comps = []
    for p in range(w * h):
        if mask[p] and not lab[p]:
            n = len(comps) + 1; st = [p]; lab[p] = n; pts = []
            while st:
                q = st.pop(); pts.append(q); qx, qy = q % w, q // w
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        nx, ny = qx + dx, qy + dy
                        if 0 <= nx < w and 0 <= ny < h:
                            r = ny * w + nx
                            if mask[r] and not lab[r]: lab[r] = n; st.append(r)
            comps.append(pts)
    return lab, comps


def zhang_suen(w, h, img):
    img = bytearray(img)
    pts = [p for p in range(w * h) if img[p]]
    def nb(p):
        x, y = p % w, p // w
        g = lambda dx, dy: img[(y + dy) * w + x + dx] if 0 <= x + dx < w and 0 <= y + dy < h else 0
        return [g(0, -1), g(1, -1), g(1, 0), g(1, 1), g(0, 1), g(-1, 1), g(-1, 0), g(-1, -1)]
    changed = True
    while changed:
        changed = False
        for step in (0, 1):
            kill = []
            for p in pts:
                if not img[p]: continue
                n = nb(p); B = sum(n)
                if B < 2 or B > 6: continue
                A = sum(1 for i in range(8) if n[i] == 0 and n[(i + 1) % 8] == 1)
                if A != 1: continue
                if step == 0:
                    if n[0] * n[2] * n[4] or n[2] * n[4] * n[6]: continue
                else:
                    if n[0] * n[2] * n[6] or n[0] * n[4] * n[6]: continue
                kill.append(p)
            for p in kill: img[p] = 0
            if kill: changed = True
            pts = [p for p in pts if img[p]]
    return img


if __name__ == '__main__':
    src, out = sys.argv[1], sys.argv[2]
    w, h, px = read_png(src)
    cls = classify(w, h, px)
    pinkish = lambda p: px[p * 4] - px[p * 4 + 1] > 22 and px[p * 4] > 140
    solid = bytearray(1 if px[p * 4 + 3] >= 110 and not pinkish(p) else 0 for p in range(w * h))
    lab, comps = components(w, h, solid)
    keep = bytearray(w * h)
    for pts in comps:
        if len(pts) >= 40:
            for q in pts: keep[q] = 1
    skel = zhang_suen(w, h, keep)
    pickle.dump({'w': w, 'h': h, 'cls': cls, 'solid': keep, 'skel': skel}, open(out, 'wb'))
    dbg = bytearray(w * h * 4)
    for p in range(w * h):
        c = (255, 255, 255, 255)
        if keep[p]: c = (205, 200, 198, 255)
        elif cls[p] == 2: c = (250, 215, 225, 255)
        elif cls[p] == 3: c = (215, 235, 250, 255)
        if skel[p]: c = (200, 20, 60, 255)
        dbg[p * 4:p * 4 + 4] = bytes(c)
    write_png(out.replace('.pkl', '-skeleton.png'), w, h, dbg)
    print('kept', sum(keep), 'skeleton px', sum(skel))
