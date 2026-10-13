"""Delete vias listed as dangling in a DRC report, keeping any whose removal would add unconnected items."""
import sys, re, pcbnew
from pcbnew import FromMM
b = pcbnew.LoadBoard(sys.argv[1]); rpt = open(sys.argv[2]).read()
pts = [(float(x), float(y)) for x, y in re.findall(r'\[(?:via|track)_dangling\][^@]*@\(([\d.]+) mm, ([\d.]+) mm\): (?:Via|Track)', rpt)]
b.BuildConnectivity(); base = b.GetConnectivity().GetUnconnectedCount(True); n = 0
near = lambda p: any(abs(p.x - FromMM(x)) < 2000 and abs(p.y - FromMM(y)) < 2000 for x, y in pts)
vias = [t for t in b.GetTracks() if (t.Type() == pcbnew.PCB_VIA_T and near(t.GetPosition())) or (t.Type() == pcbnew.PCB_TRACE_T and (near(t.GetStart()) or near(t.GetEnd()) or near((t.GetStart() + t.GetEnd()) / 2)))]
for t in vias:
    b.Remove(t); b.BuildConnectivity()
    if b.GetConnectivity().GetUnconnectedCount(True) > base: b.Add(t); b.BuildConnectivity()
    else: n += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); pcbnew.SaveBoard(sys.argv[1], b); print("removed", n, "of", len(pts))
