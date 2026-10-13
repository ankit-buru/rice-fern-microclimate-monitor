"""Silkscreen polarity marks for the battery connector J9 (pin 1 = +)."""
import sys, pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
b = pcbnew.LoadBoard(sys.argv[1])
if not any(isinstance(d, pcbnew.PCB_TEXT) and d.GetText().startswith("BAT") for d in b.GetDrawings()):
    j9 = b.FindFootprintByReference("J9")
    p1 = [p for p in j9.Pads() if p.GetNumber() == "1"][0].GetPosition()
    p2 = [p for p in j9.Pads() if p.GetNumber() == "2"][0].GetPosition()
    for txt, at in (("+", p1), ("-", p2)):
        t = pcbnew.PCB_TEXT(b); t.SetText(txt); t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(VECTOR2I(FromMM(1.2), FromMM(1.2))); t.SetTextThickness(FromMM(0.2))
        t.SetPosition(VECTOR2I(at.x, at.y - FromMM(3.0))); b.Add(t)
    t = pcbnew.PCB_TEXT(b); t.SetText("BAT 3.0-4.2V"); t.SetLayer(pcbnew.F_SilkS)
    t.SetTextSize(VECTOR2I(FromMM(0.8), FromMM(0.8))); t.SetTextThickness(FromMM(0.15))
    t.SetPosition(VECTOR2I((p1.x + p2.x) // 2, p1.y + FromMM(4.1))); b.Add(t)
    pcbnew.SaveBoard(sys.argv[1], b); print("silk marks added")
else:
    print("silk marks already present")
