"""Copper/track/via keep-out circles (r = 2.45 mm, the M2 head courtyard) at the four corner holes, then refill."""
import sys, math, pcbnew
from pcbnew import FromMM
b = pcbnew.LoadBoard(sys.argv[1]); W, H = 63.5, 46.0
if not any(z.GetIsRuleArea() and z.GetZoneName().startswith("hole_keepout") for z in b.Zones()):
    for i, (hx, hy) in enumerate([(2.5, 2.5), (W - 2.5, 2.5), (2.5, H - 2.5), (W - 2.5, H - 2.5)], 1):
        z = pcbnew.ZONE(b); z.SetIsRuleArea(True); z.SetZoneName(f"hole_keepout_H{i}")
        ls = pcbnew.LSET()
        for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu): ls.AddLayer(l)
        z.SetLayerSet(ls)
        z.SetDoNotAllowCopperPour(True); z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True)
        z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
        ol = z.Outline(); ol.NewOutline()
        for k in range(32):
            a = 2 * math.pi * k / 32
            ol.Append(FromMM(100 + hx + 2.45 * math.cos(a)), FromMM(100 + hy + 2.45 * math.sin(a)))
        b.Add(z)
b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); pcbnew.SaveBoard(sys.argv[1], b); print("hole keep-outs added")
