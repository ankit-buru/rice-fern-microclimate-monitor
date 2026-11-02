"""Fab silkscreen: keep only the labels a user needs (connectors, solder jumpers, test points, status LEDs), hide
every other reference designator and any visible value, and mark the MCU / modem side of the bottom-side USB
jumpers JP3/JP4.  usage: silk_cleanup.py board.kicad_pcb   (run mkpro.py afterwards)"""
import sys, re, pcbnew
from pcbnew import FromMM, VECTOR2I
b = pcbnew.LoadBoard(sys.argv[1])
KEEP = re.compile(r"^(J\d+|JP\d+|TP\d+|D[123])$")    # D1-D3 = USB power / user / network LEDs (README)
DROP = {"J1"}                                           # USB-C needs no label (and it would sit on U1)
SILK = (pcbnew.F_SilkS, pcbnew.B_SilkS)
hidden = []
for f in b.GetFootprints():
    for fld in f.GetFields():
        if not fld.IsVisible() or fld.GetLayer() not in SILK: continue
        if fld.GetName() == "Reference" and KEEP.match(f.GetReference()) and f.GetReference() not in DROP: continue
        fld.SetVisible(False); hidden.append(f.GetReference() + ("" if fld.GetName() == "Reference" else "." + fld.GetName()))
print("hidden:", len(hidden))
# labels that collide after the cleanup: TP4 to the right of its pad, JP4 above its pads (bottom side)
def move(ref, dx, dy):
    f = b.FindFootprintByReference(ref)
    pad = f.Pads()[0].GetPosition() if f.GetReference().startswith("TP") else f.GetPosition()
    f.Reference().SetTextAngleDegrees(0); f.Reference().SetPosition(VECTOR2I(pad.x + FromMM(dx), pad.y + FromMM(dy)))
move("TP4", 2.2, 0.0)
move("JP4", 0.0, -1.45)
# bottom: which side of the USB select jumpers goes where (pad 1 = MCU, pad 3 = modem; pre-bridged 1-2)
if not any(isinstance(d, pcbnew.PCB_TEXT) and d.GetText() in ("MCU", "MDM") for d in b.GetDrawings()):
    j4, j3 = b.FindFootprintByReference("JP4"), b.FindFootprintByReference("JP3")
    pads = {p.GetNumber(): p.GetPosition() for p in j4.Pads()}
    ymid = (j4.GetPosition().y + j3.GetPosition().y) // 2
    for txt, n, dx in (("MCU", "1", -1.25), ("MDM", "3", 1.25)):
        t = pcbnew.PCB_TEXT(b); t.SetText(txt); t.SetLayer(pcbnew.B_SilkS); t.SetMirrored(True)
        t.SetTextSize(VECTOR2I(FromMM(0.7), FromMM(0.7))); t.SetTextThickness(FromMM(0.12))
        t.SetPosition(VECTOR2I(pads[n].x + FromMM(dx), ymid)); b.Add(t)
    print("added MCU / MDM marks beside JP3/JP4")
pcbnew.SaveBoard(sys.argv[1], b)
