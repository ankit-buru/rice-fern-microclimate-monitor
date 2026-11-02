"""Post-route cleanup on the finished board: widen <0.1 mm necks, small-island removal, refill."""
import sys, pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
b = pcbnew.LoadBoard(sys.argv[1])
P = lambda x, y: VECTOR2I(FromMM(100 + x), FromMM(100 + y))
# (U1's boxed-in GND pin gets its via in preroute.py)
n = 0
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_TRACE_T and t.GetWidth() < FromMM(0.1):
        t.SetWidth(FromMM(0.1)); n += 1
for z in b.Zones():
    if not z.GetIsRuleArea() and z.GetNetname() == "GND":
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(sys.argv[1], b); print("widened", n)
