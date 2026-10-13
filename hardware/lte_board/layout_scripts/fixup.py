"""Post-route cleanup on the finished board: U1 GND via, widen <0.1 mm necks, small-island removal, refill."""
import sys, pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
b = pcbnew.LoadBoard(sys.argv[1])
P = lambda x, y: VECTOR2I(FromMM(100 + x), FromMM(100 + y))
fp = b.FindFootprintByReference("U1"); g2 = [p for p in fp.Pads() if p.GetNumber() == "2"][0].GetPosition()
gx, gy = ToMM(g2.x) - 100, ToMM(g2.y) - 100
if not any(t.Type() == pcbnew.PCB_VIA_T and abs(ToMM(t.GetPosition().x) - 100 - gx - 1.14) < 0.05 for t in b.GetTracks()):
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(gx + 1.14, gy)); v.SetWidth(FromMM(0.5)); v.SetDrill(FromMM(0.3)); v.SetNet(b.FindNet("GND")); b.Add(v)
    t = pcbnew.PCB_TRACK(b); t.SetStart(g2); t.SetEnd(P(gx + 1.14, gy)); t.SetWidth(FromMM(0.3)); t.SetLayer(pcbnew.F_Cu); t.SetNet(b.FindNet("GND")); b.Add(t)
n = 0
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_TRACE_T and t.GetWidth() < FromMM(0.1):
        t.SetWidth(FromMM(0.1)); n += 1
for z in b.Zones():
    if not z.GetIsRuleArea() and z.GetNetname() == "GND":
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(sys.argv[1], b); print("widened", n)
