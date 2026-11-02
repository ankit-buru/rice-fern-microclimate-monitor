"""Swap one footprint in place on a hand-edited board (position, rotation, side, fields and attributes kept), assign
pad nets from the netlist, and delete the tracks/vias that now collide with the new pads (re-route them afterwards
with maze_route.py).  usage: swap_footprint.py board.kicad_pcb netlist.net REF LIB:FOOTPRINT
rev 0.9: swap_footprint.py lte_board.kicad_pcb net.net J4 Connector_PinHeader_2.54mm:PinHeader_2x05_P2.54mm_Vertical"""
import sys, re, pcbnew
BRD, NET, REF, FPID = sys.argv[1:5]
STDLIB = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
b = pcbnew.LoadBoard(BRD)
old = b.FindFootprintByReference(REF)
lib, name = FPID.split(":")
fp = pcbnew.FootprintLoad(f"{STDLIB}/{lib}.pretty", name)
fp.SetFPID(pcbnew.LIB_ID(lib, name))
fp.SetReference(REF); fp.SetValue(old.GetValue())
fp.SetPath(old.GetPath()); fp.SetSheetname(old.GetSheetname()); fp.SetSheetfile(old.GetSheetfile())
fp.SetDNP(old.IsDNP()); fp.SetExcludedFromBOM(old.IsExcludedFromBOM()); fp.SetExcludedFromPosFiles(old.IsExcludedFromPosFiles())
for src, dst in ((old.Reference(), fp.Reference()), (old.Value(), fp.Value())):
    dst.SetTextSize(src.GetTextSize()); dst.SetTextThickness(src.GetTextThickness()); dst.SetVisible(src.IsVisible())
b.Add(fp)
fp.SetPosition(old.GetPosition())
if old.IsFlipped():
    try: fp.Flip(old.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    except (AttributeError, TypeError): fp.Flip(old.GetPosition(), True)
fp.SetOrientationDegrees(old.GetOrientationDegrees())
fp.Reference().SetPosition(old.Reference().GetPosition()); fp.Value().SetPosition(old.Value().GetPosition())
b.Remove(old)

txt = open(NET).read(); nets = txt[txt.index("(nets"):]
m = re.search(r'\(comp \(ref "%s"\)(.*?)\(tstamps' % re.escape(REF), txt, re.S)
fp.SetValue(re.search(r'\(value "([^"]*)"\)', m.group(1)).group(1))
pinnet = {}
for m in re.finditer(r'\(net \(code "\d+"\) \(name "([^"]*)"\)(.*?)(?=\(net \(code|\Z)', nets, re.S):
    for r, p in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', m.group(2)):
        pinnet[(r, p)] = m.group(1)
def net(name):                                 # nets the schematic added since the board was made
    n = b.FindNet(name)
    if n is None: n = pcbnew.NETINFO_ITEM(b, name); b.Add(n)
    return n
for f in b.GetFootprints():                    # every pad follows the netlist (also the MCU pins the new nets start from)
    for pad in f.Pads():
        k = (f.GetReference(), pad.GetNumber())
        if k in pinnet and pad.GetNetname() != pinnet[k]:
            if f.GetReference() != REF: print(f"  {k[0]}.{k[1]}: {pad.GetNetname()} -> {pinnet[k]}")
            pad.SetNet(net(pinnet[k]))
for pad in fp.Pads():
    print(f"  pad {pad.GetNumber():>2} {pad.GetNetname():12s} at {pcbnew.ToMM(pad.GetPosition().x) - 100:.2f}, {pcbnew.ToMM(pad.GetPosition().y) - 100:.2f}")

# other-net copper touching a new pad (+ clearance) goes; the router re-joins the pieces
gone = 0
for t in list(b.GetTracks()):
    for pad in fp.Pads():
        if t.GetNetname() == pad.GetNetname(): continue
        if t.Type() == pcbnew.PCB_VIA_T or pad.IsOnLayer(t.GetLayer()):
            if pad.GetEffectiveShape(t.GetLayer() if t.Type() != pcbnew.PCB_VIA_T else pcbnew.F_Cu).Collide(
                    t.GetEffectiveShape(t.GetLayer() if t.Type() != pcbnew.PCB_VIA_T else pcbnew.F_Cu), pcbnew.FromMM(0.2)):
                print("  removed", "via" if t.Type() == pcbnew.PCB_VIA_T else b.GetLayerName(t.GetLayer()), t.GetNetname())
                b.Remove(t); gone += 1; break
print(f"{REF} -> {FPID}; removed {gone} colliding tracks/vias")
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(BRD, b)
