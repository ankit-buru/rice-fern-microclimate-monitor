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
# forbid vias inside SMD pads (solder wicks into an unfilled via-in-pad)
d = open(sys.argv[2]).read()
if "via_at_smd" not in d:
    d = d.replace("  (structure\n", "  (structure\n    (control (via_at_smd off))\n", 1)
    assert "via_at_smd" in d, "DSN has no (structure section"
    open(sys.argv[2], "w").write(d)

# layer budget: In1 is a solid GND plane (no tracks at all); In2 takes power nets only; signals use F.Cu and B.Cu
import re
POWER_CLASSES = {"Power", "Batt", "VBAT"}
d = open(sys.argv[2]).read()
out, i, n = [], 0, 0
while True:                                   # each "(class NAME nets..." block: add the rule to its "(circuit"
    k = d.find("\n    (class ", i)
    if k < 0: break
    name = d[k + 12:].split(None, 1)[0]
    c = d.index("(circuit\n", k) + len("(circuit\n")
    layers = "F.Cu In2.Cu B.Cu" if name in POWER_CLASSES else "F.Cu B.Cu"
    out.append(d[i:c] + f"        (use_layer {layers})\n"); i = c; n += 1
d = "".join(out) + d[i:]
assert n >= 5, f"only {n} net classes got a layer rule"
open(sys.argv[2], "w").write(d)
