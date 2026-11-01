"""One-off hand fix for the committed rev 0.4 route ONLY (pipeline output varies run to run, so re-check before reuse).
Finishes /SIM_RST at U7 pad 4, boxed in by SIM_CLK above, the J8 shell pad to the right and the +5V highway on B.Cu.
usage: hand_fix_sim_rst.py board.kicad_pcb   (then run mkpro.py)"""
import sys, pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
b = pcbnew.LoadBoard(sys.argv[1]); net = b.FindNet("/SIM_RST")
P = lambda x, y: VECTOR2I(FromMM(100 + x), FromMM(100 + y))
f = lambda v: (round(ToMM(v.x) - 100, 2), round(ToMM(v.y) - 100, 2))
# 1. the GND F.Cu run under pad 4 (36.87,32.43)->(39.56,32.43)->(39.97,32.85)->(40.7,32.85)->(40.7,31.57); the pour replaces it
gone = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T and t.GetNetname() == "GND" and t.GetLayer() == pcbnew.F_Cu
        and {f(t.GetStart()), f(t.GetEnd())} & {(36.87, 32.43), (39.56, 32.43), (39.97, 32.85), (40.7, 32.85)}
        and all(36.8 <= p[0] <= 40.8 and 31.5 <= p[1] <= 32.9 for p in (f(t.GetStart()), f(t.GetEnd())))]
for t in gone: b.Remove(t)
print("removed GND segments:", len(gone))
def trk(a, c, layer):
    t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*c)); t.SetWidth(FromMM(0.15)); t.SetLayer(layer); t.SetNet(net); b.Add(t)
def via(x, y):
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetWidth(FromMM(0.5)); v.SetDrill(FromMM(0.3)); v.SetNet(net); b.Add(v)
trk((38.6, 31.65), (38.6, 32.25), pcbnew.F_Cu); via(38.6, 32.25)
trk((38.6, 32.25), (38.6, 29.1), pcbnew.In2_Cu); via(38.6, 29.1)          # joins the B.Cu SIM_RST run at y 29.1
b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(sys.argv[1], b); print("patched")
