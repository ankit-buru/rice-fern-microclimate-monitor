"""Deterministic finishing touches after maze routing.

1. GND via beside C31 (VBAT cap strip has no room for stitching).
2. Replace 'dangling' vias that only bridge two same-layer track ends with a real segment.
3. Give every F.Cu GND pour island that has no via a via, placed only where it clears
   all other-net copper on every layer, every drill hole, keepouts and the board edge.
usage: final_fixes.py board.kicad_pcb drc_report.rpt
"""
import sys, re, math, pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
BRD, RPT = sys.argv[1:3]
OX, OY, W, H = 100.0, 100.0, 63.5, 46.0
VR, DRILL, CLR, HOLE_CLR, EDGE = 0.25, 0.3, 0.17, 0.27, 0.35
b = pcbnew.LoadBoard(BRD)
P = lambda x, y: VECTOR2I(FromMM(OX + x), FromMM(OY + y))
mm = lambda v: (ToMM(v.x) - OX, ToMM(v.y) - OY)
LAYERS = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
gnd = b.FindNet("GND")
tracks = list(b.GetTracks())
pads = [p for fp in b.GetFootprints() for p in fp.Pads()]
rules = [z for z in b.Zones() if z.GetIsRuleArea()] + [z for fp in b.GetFootprints() for z in fp.Zones()]

def seg_d(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay; L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(ax + t * dx - px, ay + t * dy - py)

def via_ok(x, y, net):
    if x < EDGE + VR or y < EDGE + VR or x > W - EDGE - VR or y > H - EDGE - VR: return False
    pt = P(x, y)
    for t in tracks:
        if t.GetNetname() == net: continue
        if t.Type() == pcbnew.PCB_VIA_T:
            (vx, vy) = mm(t.GetPosition())
            if math.hypot(vx - x, vy - y) < VR + ToMM(t.GetWidth()) / 2 + CLR: return False
            if math.hypot(vx - x, vy - y) < DRILL / 2 + ToMM(t.GetDrillValue()) / 2 + HOLE_CLR: return False
        else:
            (ax, ay), (bx, by) = mm(t.GetStart()), mm(t.GetEnd())
            if seg_d(x, y, ax, ay, bx, by) < VR + ToMM(t.GetWidth()) / 2 + CLR: return False
    for p in pads:
        if p.GetDrillSize().x > 0:
            (hx, hy) = mm(p.GetPosition())
            if math.hypot(hx - x, hy - y) < DRILL / 2 + ToMM(max(p.GetDrillSize().x, p.GetDrillSize().y)) / 2 + HOLE_CLR: return False
        if p.GetNetname() == net and net != "": continue
        for L in LAYERS:
            if p.IsOnLayer(L) and p.GetEffectivePolygon(L, pcbnew.ERROR_INSIDE).Collide(pt, FromMM(VR + CLR)): return False
    for z in rules:
        if z.GetDoNotAllowVias() and z.Outline().Collide(pt, FromMM(VR + 0.05)): return False
    return True

def add_via(x, y, net):
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetWidth(FromMM(2 * VR)); v.SetDrill(FromMM(DRILL))
    v.SetNet(b.FindNet(net)); b.Add(v); tracks.append(v)
def add_track(a, c, net, w=0.15, layer=pcbnew.F_Cu):
    t = pcbnew.PCB_TRACK(b); t.SetStart(a); t.SetEnd(c); t.SetWidth(FromMM(w)); t.SetLayer(layer); t.SetNet(b.FindNet(net)); b.Add(t); tracks.append(t)

# 1. C31 GND via
c31 = [p for p in b.FindFootprintByReference("C31").Pads() if p.GetNumber() == "2"][0]
near = [t for t in tracks if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == "GND" and math.hypot(mm(t.GetPosition())[0] - 57.6, mm(t.GetPosition())[1] - 1.12) < 1.2]
if near:
    print("C31 GND pad already has a via next to it")
elif via_ok(58.6, 1.0, "GND"):
    add_via(58.6, 1.0, "GND"); add_track(c31.GetPosition(), P(58.6, 1.0), "GND", 0.25); print("C31 GND via added")
else:
    print("C31 GND via spot blocked")

# 2. dangling vias that bridge two same-layer track ends
rpt = open(RPT).read()
for x, y in re.findall(r'\[via_dangling\][^@]*@\(([\d.]+) mm, ([\d.]+) mm\): Via', rpt):
    x, y = float(x) - OX, float(y) - OY
    v = [t for t in tracks if t.Type() == pcbnew.PCB_VIA_T and math.hypot(mm(t.GetPosition())[0] - x, mm(t.GetPosition())[1] - y) < 0.01]
    if not v: continue
    v = v[0]; net = v.GetNetname(); r = ToMM(v.GetWidth()) / 2
    ends = []
    for t in tracks:
        if t.Type() == pcbnew.PCB_VIA_T or t.GetNetname() != net: continue
        for e in (t.GetStart(), t.GetEnd()):
            ex, ey = mm(e)
            if 0.001 < math.hypot(ex - x, ey - y) <= r + 0.15: ends.append((t.GetLayer(), e))
    for L, e in ends:
        add_track(e, v.GetPosition(), net, 0.15, L)
    b.Remove(v); tracks.remove(v); print(f"bridged {len(ends)} track end(s) and removed dangling via on {net}")

# 3. F.Cu GND pour islands with no via
b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones())
z = [z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname() == "GND" and z.GetFirstLayer() == pcbnew.F_Cu][0]
fill = z.GetFilledPolysList(pcbnew.F_Cu)
gv = [t.GetPosition() for t in tracks if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == "GND"]
gth = [p.GetPosition() for p in pads if p.GetNetname() == "GND" and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
for i in range(fill.OutlineCount()):
    o = fill.Outline(i)
    if any(o.PointInside(v) for v in gv + gth): continue
    bb = o.BBox(); x0, y0 = mm(bb.GetOrigin()); x1, y1 = mm(bb.GetEnd())
    spot = None
    for k in range(60):
        for m in range(60):
            x = x0 + (x1 - x0) * (k + 0.5) / 60; y = y0 + (y1 - y0) * (m + 0.5) / 60
            pt = P(x, y)
            if not o.PointInside(pt): continue
            # whole via pad must sit on this island's copper
            if not all(o.PointInside(P(x + VR * math.cos(a), y + VR * math.sin(a))) for a in (0, 1.57, 3.14, 4.71)): continue
            if via_ok(x, y, "GND"): spot = (x, y); break
        if spot: break
    print(f"GND island at x {x0:.1f}..{x1:.1f} y {y0:.1f}..{y1:.1f} ({abs(o.Area()) / 1e12:.1f} mm2): via at", spot and f"({spot[0]:.2f},{spot[1]:.2f})")
    if spot: add_via(*spot, "GND")
b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(BRD, b)
