"""Grid maze router for a few leftover connections on a mostly-routed KiCad board.

usage: maze_route.py board.kicad_pcb NET [NET ...]
Zone fills are ignored (they refill afterwards); free-standing GND stitching vias are removed first
(run stitch.py again afterwards). Rule-area keepouts, other-net copper, holes and the edge are respected.
"""
import sys, math, heapq, pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

BRD, NETS = sys.argv[1], sys.argv[2:]
OX, OY, W, H = 100.0, 100.0, 63.5, 46.0
G = 0.1                                   # grid pitch, mm
TW, CLR, VR = 0.15, 0.16, 0.25            # track width, clearance (+margin), via pad radius
EDGE = 0.3
LAYERS = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
NX, NY = int(W / G) + 1, int(H / G) + 1
VIA_COST, DIAG = 25.0, math.sqrt(2)

b = pcbnew.LoadBoard(BRD)
mm = lambda v: (ToMM(v.x) - OX, ToMM(v.y) - OY)

# ---- drop free-standing stitching vias (GND, unlocked, no track ending on them)
tl = list(b.GetTracks())
ends = set()
for t in tl:
    if t.Type() == pcbnew.PCB_TRACE_T and t.GetNetname() == "GND":
        ends.add((t.GetStart().x, t.GetStart().y)); ends.add((t.GetEnd().x, t.GetEnd().y))
stitch = [t for t in tl if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == "GND" and not t.IsLocked()
          and (t.GetPosition().x, t.GetPosition().y) not in ends]
tl = [t for t in tl if t not in stitch]
for t in stitch: b.Remove(t)
print("removed stitching vias:", len(stitch))
pads = [p for fp in b.GetFootprints() for p in fp.Pads()]
rules = [z for z in b.Zones() if z.GetIsRuleArea()] + [z for fp in b.GetFootprints() for z in fp.Zones()]

def rasterize(grid, cx0, cy0, cx1, cy1, test):
    i0, i1 = max(0, int(cx0 / G) - 1), min(NX - 1, int(cx1 / G) + 2)
    j0, j1 = max(0, int(cy0 / G) - 1), min(NY - 1, int(cy1 / G) + 2)
    for i in range(i0, i1 + 1):
        x = i * G
        for j in range(j0, j1 + 1):
            if test(x, j * G): grid[j * NX + i] = 1

def seg_d2(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay; L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
    qx, qy = ax + t * dx - px, ay + t * dy - py
    return qx * qx + qy * qy

def build(net, infl_track, infl_via):
    """blocked[layer] for track centrelines, vblock for via centres; other-net copper only"""
    blk = [bytearray(NX * NY) for _ in LAYERS]
    vblk = bytearray(NX * NY)
    def mark(layers, shape, extra_t, extra_v):
        for li in layers: shape(blk[li], extra_t)
        shape(vblk, extra_v)
    for t in tl:
        if t.GetNetname() == net: continue
        if t.Type() == pcbnew.PCB_VIA_T:
            (x, y), r = mm(t.GetPosition()), ToMM(t.GetWidth()) / 2
            f = lambda g, e, x=x, y=y, r=r: rasterize(g, x - r - e, y - r - e, x + r + e, y + r + e, lambda px, py: (px - x) ** 2 + (py - y) ** 2 <= (r + e) ** 2)
            mark(range(4), f, infl_track, infl_via)
        else:
            (ax, ay), (bx, by), r = mm(t.GetStart()), mm(t.GetEnd()), ToMM(t.GetWidth()) / 2
            li = LAYERS.index(t.GetLayer())
            f = lambda g, e, ax=ax, ay=ay, bx=bx, by=by, r=r: rasterize(g, min(ax, bx) - r - e, min(ay, by) - r - e, max(ax, bx) + r + e, max(ay, by) + r + e, lambda px, py: seg_d2(px, py, ax, ay, bx, by) <= (r + e) ** 2)
            f(blk[li], infl_track); f(vblk, infl_via)
    for p in pads:
        if p.GetNetname() == net and p.GetNetname() != "": continue
        bb = p.GetBoundingBox(); x0, y0 = mm(bb.GetOrigin()); x1, y1 = mm(bb.GetEnd())
        th = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
        lays = range(4) if th else [LAYERS.index(l) for l in (pcbnew.F_Cu, pcbnew.B_Cu) if p.IsOnLayer(l)]
        f = lambda g, e, x0=x0, y0=y0, x1=x1, y1=y1: rasterize(g, x0 - e, y0 - e, x1 + e, y1 + e, lambda px, py: x0 - e <= px <= x1 + e and y0 - e <= py <= y1 + e)
        for li in lays: f(blk[li], infl_track)
        f(vblk, infl_via)
    for z in rules:
        bb = z.GetBoundingBox(); x0, y0 = mm(bb.GetOrigin()); x1, y1 = mm(bb.GetEnd())
        ol = z.Outline()
        inside = lambda px, py, ol=ol, e=0.0: ol.Collide(VECTOR2I(FromMM(OX + px), FromMM(OY + py)), FromMM(e))
        for li, L in enumerate(LAYERS):
            if z.IsOnLayer(L) and z.GetDoNotAllowTracks():
                rasterize(blk[li], x0 - infl_track, y0 - infl_track, x1 + infl_track, y1 + infl_track, lambda px, py: inside(px, py, e=infl_track))
        if z.GetDoNotAllowVias():
            rasterize(vblk, x0 - infl_via, y0 - infl_via, x1 + infl_via, y1 + infl_via, lambda px, py: inside(px, py, e=infl_via))
    for g, e in [(x, infl_track) for x in blk] + [(vblk, infl_via)]:
        m = EDGE + e
        for j in range(NY):
            for i in range(NX):
                if i * G < m or i * G > W - m or j * G < m or j * G > H - m: g[j * NX + i] = 1
    return blk, vblk

def islands(net):
    """group this net's copper into connected islands (geometric contact)"""
    items = [("pad", p) for p in pads if p.GetNetname() == net] + [("trk", t) for t in tl if t.GetNetname() == net]
    par = list(range(len(items)))
    def find(a):
        while par[a] != a: par[a] = par[par[a]]; a = par[a]
        return a
    def pts(kind, it):
        if kind == "pad" or it.Type() == pcbnew.PCB_VIA_T: return [it.GetPosition()]
        return [it.GetStart(), it.GetEnd()]
    def layers(kind, it):
        if kind == "pad": return {l for l in LAYERS if it.IsOnLayer(l)}
        if it.Type() == pcbnew.PCB_VIA_T: return set(LAYERS)
        return {it.GetLayer()}
    def hit(kind, it, pt, L):
        if L not in layers(kind, it): return False
        if kind == "pad": return it.HitTest(pt, FromMM(0.01))
        return it.HitTest(pt, FromMM(0.01))
    for a, (ka, ia) in enumerate(items):
        for c, (kb, ib) in enumerate(items):
            if a >= c: continue
            common = layers(ka, ia) & layers(kb, ib)
            if not common: continue
            if any(hit(kb, ib, p, L) for p in pts(ka, ia) for L in common if L in layers(ka, ia)) or \
               any(hit(ka, ia, p, L) for p in pts(kb, ib) for L in common if L in layers(kb, ib)):
                par[find(a)] = find(c)
    groups = {}
    for a, it in enumerate(items): groups.setdefault(find(a), []).append(it)
    return list(groups.values())

def cells_of(group):
    out = set()
    for kind, it in group:
        if kind == "pad" or it.Type() == pcbnew.PCB_VIA_T:
            x, y = mm(it.GetPosition())
            lays = [i for i, L in enumerate(LAYERS) if it.IsOnLayer(L)] if kind == "pad" else range(4)
            for li in lays: out.add((li, int(round(x / G)), int(round(y / G))))
        else:
            (ax, ay), (bx, by) = mm(it.GetStart()), mm(it.GetEnd()); li = LAYERS.index(it.GetLayer())
            n = max(1, int(math.hypot(bx - ax, by - ay) / G))
            for k in range(n + 1):
                out.add((li, int(round((ax + (bx - ax) * k / n) / G)), int(round((ay + (by - ay) * k / n) / G))))
    return out

def route(net):
    isl = islands(net)
    if len(isl) < 2: print(net, "already connected"); return True
    isl.sort(key=len, reverse=True)
    src, dst = cells_of(isl[0]), set().union(*[cells_of(g) for g in isl[1:]])
    blk, vblk = build(net, CLR + TW / 2, CLR + VR)
    tx = [c[1] for c in dst]; ty = [c[2] for c in dst]
    dist = {}; prev = {}; pq = []
    for c in src:
        dist[c] = 0.0; heapq.heappush(pq, (0.0, c))
    goal = None
    steps = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, DIAG), (1, -1, DIAG), (-1, 1, DIAG), (-1, -1, DIAG)]
    while pq:
        d, c = heapq.heappop(pq)
        if d > dist.get(c, 1e18): continue
        if c in dst: goal = c; break
        li, i, j = c
        for di, dj, w in steps:
            ni, nj = i + di, j + dj
            if not (0 <= ni < NX and 0 <= nj < NY): continue
            n = (li, ni, nj)
            free = not blk[li][nj * NX + ni] or n in dst or n in src
            if di and dj:   # no corner cutting
                free = free and not blk[li][j * NX + ni] and not blk[li][nj * NX + i]
            if not free: continue
            nd = d + w
            if nd < dist.get(n, 1e18): dist[n] = nd; prev[n] = c; heapq.heappush(pq, (nd, n))
        if not vblk[j * NX + i]:
            for lj in range(4):
                if lj == li: continue
                n = (lj, i, j)
                if blk[lj][j * NX + i] and n not in dst and n not in src: continue
                nd = d + VIA_COST
                if nd < dist.get(n, 1e18): dist[n] = nd; prev[n] = c; heapq.heappush(pq, (nd, n))
    if goal is None: print(net, "NO PATH"); return False
    path = [goal]
    while path[-1] in prev: path.append(prev[path[-1]])
    path.reverse()
    # emit tracks/vias, merging collinear runs
    nobj = b.FindNet(net); nt = nv = 0
    def P(i, j): return VECTOR2I(FromMM(OX + i * G), FromMM(OY + j * G))
    k = 0
    while k < len(path) - 1:
        a, c = path[k], path[k + 1]
        if a[0] != c[0]:
            v = pcbnew.PCB_VIA(b); v.SetPosition(P(a[1], a[2])); v.SetWidth(FromMM(2 * VR)); v.SetDrill(FromMM(0.3)); v.SetNet(nobj); b.Add(v); tl.append(v); nv += 1
            k += 1; continue
        d = (c[1] - a[1], c[2] - a[2]); m = k + 1
        while m + 1 < len(path) and path[m + 1][0] == a[0] and (path[m + 1][1] - path[m][1], path[m + 1][2] - path[m][2]) == d: m += 1
        t = pcbnew.PCB_TRACK(b); t.SetStart(P(a[1], a[2])); t.SetEnd(P(path[m][1], path[m][2])); t.SetWidth(FromMM(TW))
        t.SetLayer(LAYERS[a[0]]); t.SetNet(nobj); b.Add(t); tl.append(t); nt += 1
        k = m
    print(f"{net}: routed, {len(path)} cells, {nt} segments, {nv} vias, cost {dist[goal]:.1f}")
    return True

def route_all(net, tries=12):
    """join islands one at a time until the net is a single piece"""
    for _ in range(tries):
        if len(islands(net)) < 2: return True
        if not route(net): return False
    return len(islands(net)) < 2
ok = all([route_all(n) for n in NETS])
pcbnew.SaveBoard(BRD, b)
print("done", "OK" if ok else "INCOMPLETE")
