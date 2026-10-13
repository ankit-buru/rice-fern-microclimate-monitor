"""Hand-route RF, add planes, export DSN.  usage: preroute.py board.kicad_pcb out.dsn"""
import sys, pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM
BRD, DSN = sys.argv[1:3]
b = pcbnew.LoadBoard(BRD)
OX, OY, W, H = 100.0, 100.0, 63.5, 46.0
DX = 11.0   # modem block offset (see gen_board.py)
def P(x, y): return VECTOR2I(FromMM(OX + x), FromMM(OY + y))
def pad(ref, num): 
    for p in b.FindFootprintByReference(ref).Pads():
        if p.GetNumber() == num: return p
    raise KeyError((ref, num))
def pos(ref, num):
    q = pad(ref, num).GetPosition(); return (ToMM(q.x) - OX, ToMM(q.y) - OY)
def track(pts, net, w=0.35, layer=pcbnew.F_Cu):
    n = b.FindNet(net)
    for a, c in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*c)); t.SetWidth(FromMM(w))
        t.SetLayer(layer); t.SetNet(n); t.SetLocked(True); b.Add(t)
def via(x, y, net="GND"):
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetWidth(FromMM(0.5)); v.SetDrill(FromMM(0.3))
    v.SetNet(b.FindNet(net)); v.SetLocked(True); b.Add(v)
def zone(pts, net, layer, prio=0, clearance=0.2):
    z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(b.FindNet(net)); z.SetAssignedPriority(prio)
    ol = z.Outline(); ol.NewOutline()
    for x, y in pts: ol.Append(FromMM(OX + x), FromMM(OY + y))
    z.SetLocalClearance(FromMM(clearance)); z.SetMinThickness(FromMM(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if net != "GND" else pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(FromMM(0.2)); z.SetThermalReliefSpokeWidth(FromMM(0.3))
    b.Add(z); return z

# ---- LTE: U6.32 -> R19 -> J6.1, shunts C40 (modem side) / C41 (antenna side)
m = pos("U6", "32"); r1 = pos("R19", "1"); r2 = pos("R19", "2"); j = pos("J6", "1")
c40 = pos("C40", "1"); c41 = pos("C41", "1")
track([m, r1], "/MDM_RF"); track([c40, (c40[0], m[1])], "/MDM_RF")
track([r2, (j[0], r2[1]), j], "/LTE_ANT"); track([c41, (c41[0], r2[1])], "/LTE_ANT")
# ---- GNSS: U6.68 (inner pad) -> escape through top-left module corner -> R20 -> J7.1
g = pos("U6", "68"); ra = pos("R20", "1"); rb = pos("R20", "2"); j7 = pos("J7", "1")
track([g, (g[0] - 1.2, g[1] - 1.1), (ra[0] + 1.1, ra[1]), ra], "/MDM_GNSS")
track([rb, j7], "/GNSS_ANT")
# ---- RF ground stitching (In1 is solid GND)
for x, y in [(45.0, 8.6), (46.4, 8.5), (49.6, 6.6), (44.6, 4.7), (47.0, 4.4), (25.4, 3.9), (25.6, 1.0)]:
    via(x + DX, y)

# ---- +3V8: buck output (L1.2) down to the In2 strip, VBAT pour down to the In2 strip
l = pos("L1", "2")
for dx in (-0.8, 0.0, 0.8):
    via(l[0] + dx, 24.15, "+3V8"); track([(l[0] + dx, 24.15), (l[0] + dx, l[1])], "+3V8", w=0.6)
c3 = pos("C3", "1"); r7 = pos("R7", "1")
track([c3, (c3[0], 24.15), (l[0] - 0.8, 24.15)], "+3V8", w=0.6)          # C3 -> L1 output vias
via(r7[0], r7[1] + 0.9, "+3V8"); track([r7, (r7[0], r7[1] + 0.9)], "+3V8", w=0.3)   # FB divider top -> In2 +3V8
# explicit 0.6 mm VBAT bus along the top edge: pins 34/35 -> C34, C33, C32, C30, C31 -> vias to In2
p34 = pos("U6", "34"); p35 = pos("U6", "35"); YB = 2.5
xend = pos("C31", "1")[0]
track([p35, (p35[0], YB), (xend, YB)], "+3V8", w=0.6)
c30 = pos("C30", "1"); track([c30, (p35[0], c30[1] + 0.4), (p35[0], YB)], "+3V8", w=0.6)   # bulk cap sits left of pin 35
track([p34, (p34[0], YB)], "+3V8", w=0.6)
for c in ("C34", "C33", "C32"):
    q = pos(c, "1"); track([q, (q[0], YB)], "+3V8", w=0.4)
q = pos("C31", "1"); track([q, (q[0], YB)], "+3V8", w=0.4)
for x in (42.2, 43.3):
    via(x + DX, 3.4, "+3V8"); track([(x + DX, 3.4), (x + DX, YB)], "+3V8", w=0.4)

# ---- USB D+/D-: coupled pair on B.Cu (In2 kept free of tracks underneath as its reference)
def offset(pts, d):
    """offset a polyline by d (positive = left of travel direction, i.e. up for +x travel), mitred corners"""
    import math
    def nrm(a, c):
        dx, dy = c[0] - a[0], c[1] - a[1]; L = math.hypot(dx, dy); return (dy / L, -dx / L)
    out = []
    for i, p in enumerate(pts):
        if i == 0:   n = nrm(pts[0], pts[1]); out.append((p[0] + d * n[0], p[1] + d * n[1])); continue
        if i == len(pts) - 1: n = nrm(pts[-2], pts[-1]); out.append((p[0] + d * n[0], p[1] + d * n[1])); continue
        n1 = nrm(pts[i - 1], p); n2 = nrm(p, pts[i + 1])
        m = (n1[0] + n2[0], n1[1] + n2[1]); k = d / (1 + n1[0] * n2[0] + n1[1] * n2[1])
        out.append((p[0] + k * m[0], p[1] + k * m[1]))
    return out
WP, GP = 0.3, 0.15                     # ~90 ohm coupled microstrip on JLC04161H-7628 (verify!)
a6, b6, a7, b7 = (pos("J1", n) for n in ("A6", "B6", "A7", "B7"))
padl = ToMM(pad("J1", "A6").GetBoundingBox().GetLeft()) - OX
xdn, xdp = padl - 0.45, padl - 1.25     # via columns under the receptacle body
def via_n(x, y, net): 
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetWidth(FromMM(0.5)); v.SetDrill(FromMM(0.3))
    v.SetNet(b.FindNet(net)); v.SetLocked(True); b.Add(v)
# B-row pins jump to the A-row nets through vias + short B.Cu links
for (pa, pb, x, net) in ((b7, a7, xdn, "/USB_DN"), (a6, b6, xdp, "/USB_DP")):
    via_n(x, pa[1], net); via_n(x, pb[1], net)
    track([pa, (x, pa[1])], net, w=0.15); track([pb, (x, pb[1])], net, w=0.15)
    track([(x, pa[1]), (x, pb[1])], net, w=0.2, layer=pcbnew.B_Cu)
# B-row pins -> USBLC6 (U1 turned 180 deg: pins 4/3 = DN on top, 6/1 = DP below), flow-through on F.Cu
u1, u3, u4, u6 = (pos("U1", n) for n in ("1", "3", "4", "6"))
track([b7, (b7[0] + 0.96, b7[1]), (u4[0] - 0.86, u4[1]), u4, u3], "/USB_DN", w=0.2)
track([b6, (b6[0] + 0.96, b6[1]), (u6[0] - 0.86, u6[1]), u6, u1], "/USB_DP", w=0.2)
# USBLC6 -> common pad of the USB select jumpers (JP4 = DN above, JP3 = DP below; pad 1 = MCU, pad 3 = modem)
j4c, j3c = pos("JP4", "2"), pos("JP3", "2")
track([u3, (j4c[0], u3[1]), j4c], "/USB_DN", w=0.2)
track([u1, (j3c[0], u1[1]), j3c], "/USB_DP", w=0.2)
# modem side: jumper pad 3 -> via -> coupled pair on B.Cu (DN on top, matching modem pins 26 above 25) -> R4/R3
j4m, j3m = pos("JP4", "3"), pos("JP3", "3")
xv = j4m[0] + 1.2
r4a, r4b, r3a, r3b = pos("R4", "1"), pos("R4", "2"), pos("R3", "1"), pos("R3", "2")
vx = r4a[0] + 0.92
yN, yP = 14.25, 14.25 + WP + GP
for q, net in ((j4m, "/MDM_USBJ_DN"), (j3m, "/MDM_USBJ_DP")):
    via_n(xv, q[1], net); track([q, (xv, q[1])], net, w=0.25)
track([(xv, j4m[1]), (xv + yN - j4m[1], yN), (57.5, yN), (57.95, r4a[1]), (vx, r4a[1])], "/MDM_USBJ_DN", w=WP, layer=pcbnew.B_Cu)
track([(xv, j3m[1]), (xv + yP - j3m[1], yP), (57.5, yP), (57.8, r3a[1]), (vx, r3a[1])], "/MDM_USBJ_DP", w=WP, layer=pcbnew.B_Cu)
via_n(vx, r4a[1], "/MDM_USBJ_DN"); via_n(vx, r3a[1], "/MDM_USBJ_DP")
track([(vx, r4a[1]), r4a], "/MDM_USBJ_DN", w=0.25); track([(vx, r3a[1]), r3a], "/MDM_USBJ_DP", w=0.25)
track([r4b, pos("U6", "26")], "/MDM_USB_DN", w=0.2); track([r3b, pos("U6", "25")], "/MDM_USB_DP", w=0.2)
# keep In2 free of tracks under the pair so it stays a clean reference (pours still allowed)
ka = pcbnew.ZONE(b); ka.SetIsRuleArea(True); ka.SetZoneName("In2_USB_ref"); ls = pcbnew.LSET(); ls.AddLayer(pcbnew.In2_Cu); ka.SetLayerSet(ls)
ka.SetDoNotAllowTracks(True); ka.SetDoNotAllowVias(False); ka.SetDoNotAllowPads(False); ka.SetDoNotAllowCopperPour(False); ka.SetDoNotAllowFootprints(False)
ol = ka.Outline(); ol.NewOutline()
for x, y in [(xv - 0.4, j4m[1] - 0.4), (xv + 0.4, j4m[1] - 0.4), (xv + yN - j4m[1] + 0.35, yN - 0.95), (57.5, yN - 0.95), (57.5, yP + 0.95), (xv + yP - j3m[1] - 0.2, yP + 0.95), (xv - 0.4, j3m[1] + 0.75)]:
    ol.Append(FromMM(OX + x), FromMM(OY + y))
b.Add(ka)

# ---- +5V highway: J1 VBUS -> B.Cu down the left side and along y=30.6 -> buck input (U2.4, C1)
vb = pos("J1", "A9"); u2 = pos("U2", "4")
yv = vb[1] + 1.35
track([vb, (8.9, vb[1]), (8.9, yv)], "+5V", w=0.5)
via_n(8.9, yv, "+5V")
# rev 0.3: the highway now ends at the Schottky D4 (USB -> VSYS); VSYS feeds the buck and the LDO
d4a = pos("D4", "2")
track([(8.9, yv), (8.9, 30.6), (43.4, 30.6), (43.4, 42.8)], "+5V", w=0.5, layer=pcbnew.B_Cu)
via_n(43.4, 42.8, "+5V")
track([(43.4, 42.8), (d4a[0], 42.8), d4a], "+5V", w=0.5)
track([u2, (u2[0], 33.6), pos("C1", "1")], "/VSYS", w=0.5)

# ---- modem control pins 39-42 (top edge): escape vias straight above each pad
for n, net in (("39", "/MDM_PWRKEY"), ("40", "/VDD_EXT"), ("41", "/MDM_NETLIGHT"), ("42", "/MDM_STATUS")):
    q = pos("U6", n); via_n(q[0], 1.85, net); track([q, (q[0], 1.85)], net, w=0.2)

# ---- U1 GND pin is boxed in by the USB flow-through traces: give it its own via
g2 = pos("U1", "2"); via(g2[0] + 1.14, g2[1]); track([g2, (g2[0] + 1.14, g2[1])], "GND", w=0.3)

E = 0.3
# In1: solid GND
zone([(E, E), (W - E, E), (W - E, H - E), (E, H - E)], "GND", pcbnew.In1_Cu)
# F.Cu: +3V8 pour joining VBAT pins 34/35 and C30-C34
zone([(38.75 + DX, E), (W - E, E), (W - E, 4.3), (38.75 + DX, 4.3)], "+3V8", pcbnew.F_Cu, prio=10)
# In2: +3V8 strip from buck (bottom right) up to the VBAT pins
zone([(38.75 + DX, E), (W - E, E), (W - E, 36.5), (59.7, 36.5), (59.7, 29.6), (42.9 + DX, 29.6), (42.9 + DX, 23.8), (46.5 + DX, 23.8), (46.5 + DX, 4.6), (38.75 + DX, 4.6)],
     "+3V8", pcbnew.In2_Cu, prio=10)
pcbnew.SaveBoard(BRD, b)
ok = pcbnew.ExportSpecctraDSN(b, DSN)
print("dsn export", ok)
