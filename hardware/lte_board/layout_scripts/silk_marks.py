"""Silkscreen marks: battery connector J9 polarity (pin 1 = +) and the RESET / BOOT0 button labels."""
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
    print("silk marks added")
else:
    print("silk marks already present")
# button labels, in free silk next to each button (SW1 top edge, SW2 above the button, left of the SIM holder)
OX, OY = 100.0, 100.0
if not any(isinstance(d, pcbnew.PCB_TEXT) and d.GetText() == "RESET" for d in b.GetDrawings()):
    for txt, x, y in (("RESET", 15.5, 2.8), ("BOOT0", 33.3, 38.3)):
        t = pcbnew.PCB_TEXT(b); t.SetText(txt); t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(VECTOR2I(FromMM(1.0), FromMM(1.0))); t.SetTextThickness(FromMM(0.18))
        t.SetPosition(VECTOR2I(FromMM(OX + x), FromMM(OY + y))); b.Add(t)
    b.FindFootprintByReference("SW1").Reference().SetPosition(VECTOR2I(FromMM(OX + 20.6), FromMM(OY + 6.4)))   # was off the board edge
    print("button labels added")
pcbnew.SaveBoard(sys.argv[1], b)
