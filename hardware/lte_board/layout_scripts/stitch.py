"""Add GND stitching vias wherever they clear all other-net copper; then refill.  usage: stitch.py board"""
import sys, math, pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
b = pcbnew.LoadBoard(sys.argv[1])
OX, OY, W, H = 100.0, 100.0, 63.5, 46.0
gnd = b.FindNet("GND")
VD, CLR = 0.5, 0.2          # via pad dia, clearance
obst = []                   # (shape_poly_set, ) other-net copper on any layer
items = []
for fp in b.GetFootprints():
    for p in fp.Pads():
        if p.GetNetname() != "GND" or p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
            items.append(p)
for t in b.GetTracks():
    if t.GetNetname() != "GND": items.append(t)
existing = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == "GND"]
# keep vias out of the RF shunt area and the module's centre (thermal pads)
rules = [z for z in b.Zones() if z.GetIsRuleArea()] + [z for fp in b.GetFootprints() for z in fp.Zones()]
HOLES = [(2.5, 2.5), (W - 2.5, 2.5), (2.5, H - 2.5), (W - 2.5, H - 2.5)]
def blocked(x, y):
    pt = VECTOR2I(FromMM(OX + x), FromMM(OY + y))
    if any((x - hx) ** 2 + (y - hy) ** 2 < 2.6 ** 2 for hx, hy in HOLES):   # keep out from under screw heads
        return True
    for z in rules:
        if z.GetDoNotAllowVias() and z.Outline().Collide(pt, FromMM(VD / 2 + 0.05)):
            return True
    for it in items:
        bb = it.GetBoundingBox()
        if not bb.Inflate(FromMM(VD / 2 + CLR + 0.05)).Contains(pt):
            continue
        if it.Type() == pcbnew.PCB_PAD_T:
            sh = it.GetEffectivePolygon(pcbnew.F_Cu if it.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu, pcbnew.ERROR_INSIDE)
        else:
            sh = pcbnew.SHAPE_POLY_SET(); it.TransformShapeToPolygon(sh, it.GetLayer(), 0, FromMM(0.005), pcbnew.ERROR_INSIDE)
        if sh.Collide(pt, FromMM(VD / 2 + CLR)):
            return True
    for v in existing:
        if (v.GetPosition() - pt).EuclideanNorm() < FromMM(1.0):
            return True
    return False
n = 0
step = 1.3
y = 0.9
while y < H - 0.8:
    x = 0.9
    while x < W - 0.8:
        if not blocked(x, y):
            v = pcbnew.PCB_VIA(b); v.SetPosition(VECTOR2I(FromMM(OX + x), FromMM(OY + y)))
            v.SetWidth(FromMM(VD)); v.SetDrill(FromMM(0.3)); v.SetNet(gnd); b.Add(v); existing.append(v); n += 1
        x += step
    y += step
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(sys.argv[1], b)
print("stitching vias", n)
