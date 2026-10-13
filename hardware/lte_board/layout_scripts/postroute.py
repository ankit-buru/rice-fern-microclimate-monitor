"""Import Freerouting session, add GND pours, fill.  usage: postroute.py board.kicad_pcb in.ses"""
import sys, pcbnew
from pcbnew import FromMM
BRD, SES = sys.argv[1:3]
b = pcbnew.LoadBoard(BRD)
print("ses import", pcbnew.ImportSpecctraSES(b, SES))
OX, OY, W, H, E = 100.0, 100.0, 63.5, 46.0, 0.3
for layer in (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
    z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(b.FindNet("GND")); z.SetAssignedPriority(0)
    ol = z.Outline(); ol.NewOutline()
    for x, y in [(E, E), (W - E, E), (W - E, H - E), (E, H - E)]:
        ol.Append(FromMM(OX + x), FromMM(OY + y))
    z.SetLocalClearance(FromMM(0.2)); z.SetMinThickness(FromMM(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(FromMM(0.2)); z.SetThermalReliefSpokeWidth(FromMM(0.3))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    b.Add(z)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(BRD, b)
print("tracks", len(b.GetTracks()))
