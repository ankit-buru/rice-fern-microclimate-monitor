"""Report every via that touches an SMD pad (any net). JLC doesn't fill vias by default, so solder wicks into them.
usage: check_via_in_pad.py board.kicad_pcb    (exit status 1 if any are found)"""
import sys, pcbnew
from pcbnew import ToMM, FromMM
b = pcbnew.LoadBoard(sys.argv[1])
vias = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
bad = []
for fp in b.GetFootprints():
    for p in fp.Pads():
        if p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD: continue
        layer = pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
        poly, bb = p.GetEffectivePolygon(layer, pcbnew.ERROR_INSIDE), p.GetBoundingBox()
        bb.Inflate(FromMM(0.4))
        for v in vias:
            if bb.Contains(v.GetPosition()) and poly.Collide(v.GetPosition(), v.GetWidth(pcbnew.F_Cu) // 2):
                bad.append(f"{fp.GetReference()} pad {p.GetNumber()} ({v.GetNetname()}) via at "
                           f"({ToMM(v.GetPosition().x) - 100:.2f}, {ToMM(v.GetPosition().y) - 100:.2f})")
print(f"vias touching SMD pads: {len(bad)}")
for line in bad: print("  " + line)
sys.exit(1 if bad else 0)
