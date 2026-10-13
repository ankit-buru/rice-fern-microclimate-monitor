import sys, pcbnew
from pcbnew import FromMM
b = pcbnew.LoadBoard(sys.argv[1])
b.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_SIGNAL)
if not any(z.GetIsRuleArea() and z.GetZoneName() == "In1_RF_keepout" for z in b.Zones()):
    z = pcbnew.ZONE(b); z.SetIsRuleArea(True); z.SetZoneName("In1_RF_keepout")
    ls = pcbnew.LSET(); ls.AddLayer(pcbnew.In1_Cu); z.SetLayerSet(ls)
    z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(False); z.SetDoNotAllowPads(False)
    z.SetDoNotAllowCopperPour(False); z.SetDoNotAllowFootprints(False)
    ol = z.Outline(); ol.NewOutline()
    for x, y in [(38.5, 0), (63.5, 0), (63.5, 46), (38.5, 46)]:
        ol.Append(FromMM(100 + x), FromMM(100 + y))
    b.Add(z)
pcbnew.SaveBoard(sys.argv[1], b)
print("dsn", pcbnew.ExportSpecctraDSN(b, sys.argv[2]))
