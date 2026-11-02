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
def track(pts, net, w=0.30, layer=pcbnew.F_Cu):     # default = RF: 0.30 mm ~ 49 ohm CPWG on JLC04161H-7628
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

# ---- LTE: U6.32 -> R19 -> C61 (series 100 pF) -> node: J6 U.FL below, D6 TVS above, R40 (DNP 0R) east -> J10 SMA
m = pos("U6", "32"); r1 = pos("R19", "1"); r2 = pos("R19", "2")
c40 = pos("C40", "1"); c41 = pos("C41", "1")
track([m, r1], "/MDM_RF"); track([c40, (c40[0], m[1])], "/MDM_RF")
track([r2, pos("C61", "1")], "/LTE_MATCH"); track([c41, (c41[0], r2[1])], "/LTE_MATCH")
n2 = pos("C61", "2"); j = pos("J6", "1"); d6 = pos("D6", "1"); ra = pos("R40", "1"); rs = pos("R40", "2")
track([n2, (ra[0], n2[1]), ra], "/LTE_ANT"); track([(j[0], n2[1]), j], "/LTE_ANT"); track([d6, (d6[0], n2[1])], "/LTE_ANT")
d6g = pos("D6", "2"); via(d6g[0], 5.2); track([d6g, (d6g[0], 5.2)], "GND", w=0.3)
# SMA option: down the right edge, round J6 and into the J10 centre pad from its inboard end
s1 = pos("J10", "1"); sx = s1[0] - 2.125 + 0.35      # just inside the inboard end of the 4.25 mm centre pad
track([rs, (rs[0], 13.45), (58.2, 13.45), (58.2, s1[1]), (sx, s1[1])], "/LTE_SMA")
# ---- GNSS along y = 5.0: U6.68 -> corner escape -> R20 0R -> C56 100 pF DC block -> J7 SMA centre pad
#      shunts: C59 (module side) / C58 (DNP, above the line), D5 TVS and the L2 bias choke (below, antenna side)
YG = 5.0
g = pos("U6", "68"); ra = pos("R20", "1"); rb = pos("R20", "2"); ca = pos("C56", "1"); cb = pos("C56", "2")
j7 = pos("J7", "1"); j7in = (j7[0], j7[1] + 2.125 - 0.35)     # just inside the inboard end of the centre pad
track([g, (g[0] - 1.0, YG), ra], "/MDM_GNSS"); track([rb, ca], "/GNSS_MATCH")
track([cb, (j7[0], YG), j7in], "/GNSS_ANT")
for ref, net in (("C59", "/MDM_GNSS"), ("C58", "/GNSS_MATCH"), ("L2", "/GNSS_ANT"), ("D5", "/GNSS_ANT")):
    q = pos(ref, "1"); track([q, (q[0], YG)], net)
for ref, (dx, dy) in (("C59", (0, -0.7)), ("C58", (0, -0.7)), ("D5", (0.7, 0)),     # bias-switch GND pads get their own
                      ("R32", (0, 0.8)), ("R27", (0, -0.8)), ("C17", (0, -1.2))):                                            # vias: the pour here is too narrow
    q = pos(ref, "2"); via(q[0] + dx, q[1] + dy); track([q, (q[0] + dx, q[1] + dy)], "GND", w=0.3)
# GNSS antenna bias: R38 moved next to U10, so L2 drops GNSS_BIAS straight onto In2 (power layer)
q = pos("L2", "2"); via(q[0] - 0.75, q[1], "/GNSS_BIAS"); track([q, (q[0] - 0.75, q[1])], "/GNSS_BIAS", w=0.3)
# ---- RF ground stitching (In1 is solid GND); J7 grounds: one via outboard of each top ground pad
for x, y in [(45.0, 8.6), (46.4, 8.5), (44.6, 4.7), (25.6, 1.0)]:     # (47.0, 4.4) became D7's GND via
    via(x + DX, y)
for dx in (-3.52 - 0.55, 3.52 + 0.55):
    via(j7[0] + dx, 2.5)
# ---- edge-launch SMA centre pads: no In1/In2 copper underneath (a 1.5 mm pad 0.2 mm over In1 is ~20 ohm);
#      they reference the coplanar ground pads and B.Cu instead
for ref in ("J7", "J10"):
    pd = pad(ref, "1"); bb = pd.GetBoundingBox()
    x0, y0, x1, y1 = ToMM(bb.GetLeft()) - OX - 0.3, ToMM(bb.GetTop()) - OY - 0.3, ToMM(bb.GetRight()) - OX + 0.3, ToMM(bb.GetBottom()) - OY + 0.3
    kz = pcbnew.ZONE(b); kz.SetIsRuleArea(True); kz.SetZoneName(f"sma_ref_cutout_{ref}")
    ls = pcbnew.LSET(); ls.AddLayer(pcbnew.In1_Cu); ls.AddLayer(pcbnew.In2_Cu); kz.SetLayerSet(ls)
    kz.SetDoNotAllowCopperPour(True); kz.SetDoNotAllowTracks(True); kz.SetDoNotAllowVias(True)
    kz.SetDoNotAllowPads(False); kz.SetDoNotAllowFootprints(False)
    ol = kz.Outline(); ol.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)): ol.Append(FromMM(OX + x), FromMM(OY + y))
    b.Add(kz)

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
WP, GP = 0.25, 0.20                    # ~92 ohm coupled microstrip on JLC04161H-7628 (2D field solve, DESIGN.md H06)
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
# USBLC6 -> common pad of the USB select jumpers (JP4 = DN above, JP3 = DP below; pad 1 = MCU, pad 3 = modem).
# JP3/JP4 are bare copper on B.Cu, north-east of U1: each feed runs F.Cu over the jumpers and drops through a via
# onto the middle pad from the gap between the rows (DN) or from below (DP)
j4c, j3c = pos("JP4", "2"), pos("JP3", "2")
u1, u3 = pos("U1", "1"), pos("U1", "3")
gN, gP = (j4c[0], (j4c[1] + j3c[1]) / 2), (j3c[0], j3c[1] + 1.6)
track([u3, (u3[0] + 0.76, u3[1]), (u3[0] + 1.46, u3[1] - 0.7), (u3[0] + 1.46, gN[1] + 1.4), gN], "/USB_DN", w=0.2)
track([u1, (gP[0] - 1.0, u1[1]), (gP[0], u1[1] - 1.0), gP], "/USB_DP", w=0.2)
for g, j, net in ((gN, j4c, "/USB_DN"), (gP, j3c, "/USB_DP")):
    via_n(*g, net); track([g, j], net, w=0.2, layer=pcbnew.B_Cu)
# MCU side: jumper pad 1 -> B.Cu north, west of the jumpers -> vias beside PA11 / PA12 (pins 32/33, left side)
j4u, j3u = pos("JP4", "1"), pos("JP3", "1")
pa11, pa12 = pos("U4", "32"), pos("U4", "33")
mN, mP = (pa11[0] - 1.35, pa11[1]), (pa11[0] - 2.25, pa12[1] + 0.4)
via_n(*mN, "/MCU_USB_DN"); via_n(*mP, "/MCU_USB_DP")
track([j4u, (mN[0], j4u[1]), mN], "/MCU_USB_DN", w=0.2, layer=pcbnew.B_Cu)
track([j3u, (mP[0], j3u[1]), mP], "/MCU_USB_DP", w=0.2, layer=pcbnew.B_Cu)
track([mN, pa11], "/MCU_USB_DN", w=0.2); track([mP, (mP[0] + 0.4, pa12[1]), pa12], "/MCU_USB_DP", w=0.2)
# modem side: jumper pad 3 -> coupled pair on B.Cu (DN on top, matching modem pins 26 above 25) east below the MCU,
# 45 degrees up under the modem, then east between R4 and R3 -> vias above R4 / below R3
j4m, j3m = pos("JP4", "3"), pos("JP3", "3")
xv = j4m[0] + 1.2
r4a, r4b, r3a, r3b = pos("R4", "1"), pos("R4", "2"), pos("R3", "1"), pos("R3", "2")
vx = r4a[0]                            # rev 0.5: vias above R4 / below R3, keeping x > 58 free for the LTE SMA trace
vN, vP = 12.75, 16.05
yN, yE = j3m[1] + 0.95, 14.25          # pair height below the jumpers / at the modem end
xr = 47.0                              # end of the 45-degree rise under the modem
main = [(xv + yN - j4m[1], yN), (xr - (yN - yE), yN), (xr, yE), (56.8, yE)]
mainP = offset(main, -(WP + GP))
for q, net in ((j4m, "/MDM_USBJ_DN"), (j3m, "/MDM_USBJ_DP")):
    track([q, (xv, q[1])], net, w=0.25, layer=pcbnew.B_Cu)
track([(xv, j4m[1])] + main + [(vx, yE - 0.71), (vx, vN)], "/MDM_USBJ_DN", w=WP, layer=pcbnew.B_Cu)
track([(xv, j3m[1]), (xv + mainP[0][1] - j3m[1], mainP[0][1])] + mainP[1:] + [(vx, mainP[-1][1] + 0.71), (vx, vP)],
      "/MDM_USBJ_DP", w=WP, layer=pcbnew.B_Cu)
via_n(vx, vN, "/MDM_USBJ_DN"); via_n(vx, vP, "/MDM_USBJ_DP")
track([(vx, vN), r4a], "/MDM_USBJ_DN", w=0.25); track([(vx, vP), r3a], "/MDM_USBJ_DP", w=0.25)
track([r4b, pos("U6", "26")], "/MDM_USB_DN", w=0.2); track([r3b, pos("U6", "25")], "/MDM_USB_DP", w=0.2)
# keep In2 free of tracks under the pair so it stays a clean reference (pours still allowed)
def in2_ref(name, pts):
    ka = pcbnew.ZONE(b); ka.SetIsRuleArea(True); ka.SetZoneName(name); ls = pcbnew.LSET(); ls.AddLayer(pcbnew.In2_Cu); ka.SetLayerSet(ls)
    ka.SetDoNotAllowTracks(True); ka.SetDoNotAllowVias(False); ka.SetDoNotAllowPads(False); ka.SetDoNotAllowCopperPour(False); ka.SetDoNotAllowFootprints(False)
    ol = ka.Outline(); ol.NewOutline()
    for x, y in pts: ol.Append(FromMM(OX + x), FromMM(OY + y))
    b.Add(ka)
in2_ref("In2_USB_ref", offset(main, 0.6) + offset(mainP, -0.6)[::-1])
in2_ref("In2_USB_ref_start", [(j4m[0], j4m[1] - 0.5), (main[0][0] + 0.5, j4m[1] - 0.5), (main[0][0] + 0.5, mainP[0][1] + 0.6), (j4m[0], mainP[0][1] + 0.6)])
in2_ref("In2_USB_ref_end", [(56.6, vN - 0.45), (58.0, vN - 0.45), (58.0, vP + 0.45), (56.6, vP + 0.45)])

# ---- +5V highway: J1 VBUS -> B.Cu down the left side and along y=30.6 -> buck input (U2.4, C1)
vb = pos("J1", "A9"); u2 = pos("U2", "4")
yv = vb[1] + 1.35
track([vb, (8.9, vb[1]), (8.9, yv)], "+5V", w=0.5)
via_n(8.9, yv, "+5V")
# rev 0.3: the highway now ends at the Schottky D4 (USB -> VSYS); VSYS feeds the buck and the LDO
d4a = pos("D4", "2")
yd = d4a[1] - 1.75                                   # via just above D4's anode (D4 sits left of the SIM holder)
track([(8.9, yv), (8.9, 30.6), (d4a[0], 30.6), (d4a[0], yd)], "+5V", w=0.5, layer=pcbnew.In2_Cu)   # In2: power layer
via_n(d4a[0], yd, "+5V")
track([(d4a[0], yd), d4a], "+5V", w=0.5)
# JP1 (modem USB VBUS, right edge) taps the highway too: In2 east, 45 degrees up past the buck, via beside JP1
j1p = pos("JP1", "1"); jv = (j1p[0] - 0.25, j1p[1] + 1.25); via_n(*jv, "+5V")    # between JP1 and L1, east of the +3V8 vias
track([(d4a[0], 30.6), (46.8, 30.6), (54.0, 23.4), (jv[0] - 0.5, 23.4), jv], "+5V", w=0.5, layer=pcbnew.In2_Cu); track([jv, j1p], "+5V", w=0.3)
# D1's resistor R9 taps the highway from In2 just west of the LED (its pad is boxed in by the battery block)
r9 = pos("R9", "1"); tv = (r9[0] - 0.89, 30.9); via_n(*tv, "+5V")
track([(tv[0], 30.6), tv], "+5V", w=0.5, layer=pcbnew.In2_Cu); track([tv, r9], "+5V", w=0.3)

# ---- SIM holder J8 (XunPu SMN-303): manufacturer drawing marks "NO PATTERN AND VIA HOLE IN THIS AREA" under
# the contact springs. Six F.Cu keep-outs (no tracks, vias or pour), footprint coords, 0.1 mm margin.
j8 = b.FindFootprintByReference("J8"); jx, jy = ToMM(j8.GetPosition().x) - OX, ToMM(j8.GetPosition().y) - OY
assert abs(j8.GetOrientationDegrees()) < 0.01, "SIM keep-outs assume J8 at 0 deg"
for k, (cx, cy, w, h) in enumerate([(-3.71, -0.25, 1.30, 2.75), (-1.17, -0.25, 1.30, 2.75), (1.37, -0.25, 1.30, 2.75),
                                     (-3.72, 5.42, 1.85, 3.50), (-1.22, 5.42, 1.85, 3.50), (1.28, 5.42, 1.85, 3.50)]):
    kz = pcbnew.ZONE(b); kz.SetIsRuleArea(True); kz.SetZoneName(f"sim_spring_keepout_{k + 1}")
    ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); kz.SetLayerSet(ls)
    kz.SetDoNotAllowTracks(True); kz.SetDoNotAllowVias(True); kz.SetDoNotAllowCopperPour(True)
    kz.SetDoNotAllowPads(False); kz.SetDoNotAllowFootprints(False)
    ol = kz.Outline(); ol.NewOutline()
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        ol.Append(FromMM(OX + jx + cx + sx * (w / 2 + 0.1)), FromMM(OY + jy + cy + sy * (h / 2 + 0.1)))
    b.Add(kz)
track([u2, (u2[0], 33.6), pos("C1", "1")], "/VSYS", w=0.5)

# ---- modem control pins 39-42 (top edge): escape vias straight above each pad
for n, net in (("39", "/MDM_PWRKEY"), ("40", "/VDD_EXT"), ("41", "/MDM_NETLIGHT"), ("42", "/MDM_STATUS")):
    q = pos("U6", n); via_n(q[0], 1.85, net); track([q, (q[0], 1.85)], net, w=0.2)

# ---- U1 GND pin is boxed in by the USB flow-through traces: give it its own via
g2 = pos("U1", "2"); via(g2[0] + 0.95, g2[1]); track([g2, (g2[0] + 0.95, g2[1])], "GND", w=0.3)   # MCU pins 1 mm east

# ---- rev 0.6 audit fixes (DESIGN.md H10)
def keepout(name, x0, y0, x1, y1):
    """F.Cu rule area: no tracks, vias or pour (pads allowed)"""
    kz = pcbnew.ZONE(b); kz.SetIsRuleArea(True); kz.SetZoneName(name)
    ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); kz.SetLayerSet(ls)
    kz.SetDoNotAllowTracks(True); kz.SetDoNotAllowVias(True); kz.SetDoNotAllowCopperPour(True)
    kz.SetDoNotAllowPads(False); kz.SetDoNotAllowFootprints(False)
    ol = kz.Outline(); ol.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)): ol.Append(FromMM(OX + x), FromMM(OY + y))
    b.Add(kz)
# SIM7080G HD V1.05 Fig. 4 "Forbidden Area": 2.15 x 5.3 mm hatched box inside the top-right corner of the pad ring,
# from 1.0 to 3.15 mm left of the right column (pin 33) and 1.28 to 6.55 mm below the top row (pin 34) (scaled from the
# drawing using the 1.10 / 2.75 / 3.45 mm pad spacings it dimensions)
p33, p34 = pos("U6", "33"), pos("U6", "34")
keepout("modem_forbidden_area", p33[0] - 3.16, p34[1] + 1.28, p33[0] - 1.0, p34[1] + 6.55)
# SC-32S datasheet: "no pattern under SC-32S" -> keep F.Cu clear between the crystal pads
y1a, y1b = pad("Y1", "1"), pad("Y1", "2")
bb1, bb2 = y1a.GetBoundingBox(), y1b.GetBoundingBox()
if abs(bb1.GetCenter().x - bb2.GetCenter().x) > abs(bb1.GetCenter().y - bb2.GetCenter().y):   # pads side by side
    lft, rgt = sorted((bb1, bb2), key=lambda q: q.GetLeft())
    keepout("crystal_Y1_keepout", ToMM(lft.GetRight()) - OX + 0.1, ToMM(lft.GetTop()) - OY,
            ToMM(rgt.GetLeft()) - OX - 0.1, ToMM(lft.GetBottom()) - OY)
else:
    top, bot = sorted((bb1, bb2), key=lambda q: q.GetTop())
    keepout("crystal_Y1_keepout", ToMM(top.GetLeft()) - OX, ToMM(top.GetBottom()) - OY + 0.1,
            ToMM(top.GetRight()) - OX, ToMM(bot.GetTop()) - OY - 0.1)
# U5 supplies: its VCCA (2) and VCCB (19) pins sit inside the A/B pin rows, between modem lines, so each gets a
# trace under the package body down to its cap below U5: VCCA (with pin 10, OE) to C62, VCCB to C21
a2, a10, b19 = pos("U5", "2"), pos("U5", "10"), pos("U5", "19")
xa, xb = a2[0] - 1.26, b19[0] + 1.46
c62 = pos("C62", "1"); track([a10, (xa, a10[1]), (xa, c62[1]), c62], "/VDD_EXT", w=0.25); track([a2, (xa, a2[1])], "/VDD_EXT", w=0.25)
q = pos("C62", "2"); via(q[0] + 0.77, q[1]); track([q, (q[0] + 0.77, q[1])], "GND", w=0.3)
c21 = pos("C21", "1"); track([b19, (xb, b19[1]), (xb, c21[1]), c21], "+3V3", w=0.25)
q = pos("U5", "11"); via(q[0], q[1] - 1.17); track([q, (q[0], q[1] - 1.17)], "GND", w=0.3)
# H10d: SIM caps above the J8 contacts, GND pad (top) up to its own via; U7 GND via to the left
for ref in ("C52", "C51", "C53", "C50"):
    q = pos(ref, "2"); via(q[0], q[1] - 0.77); track([q, (q[0], q[1] - 0.77)], "GND", w=0.3)
q = pos("U7", "2"); via(q[0] - 1.1, q[1]); track([q, (q[0] - 1.1, q[1])], "GND", w=0.3)   # SC-70 pads are 1.32 mm long
# MCU VSS pin 23 can end up on an orphan pour island between autorouted tracks: give it its own via
q = pos("U4", "23"); via(q[0], q[1] - 1.2); track([q, (q[0], q[1] - 1.2)], "GND", w=0.3)     # top side (U4 at 180)
# H10g: D7 VBAT TVS hangs off the VBAT bus (y = YB) below C31; D8 on PWRKEY next to pin 39's escape via
q = pos("D7", "1"); track([q, (q[0], YB)], "+3V8", w=0.4)
q = pos("D7", "2"); via(q[0] + 0.8, q[1]); track([q, (q[0] + 0.8, q[1])], "GND", w=0.3)
q = pos("D8", "1"); track([(pos("U6", "39")[0], 1.85), q], "/MDM_PWRKEY", w=0.2)
q = pos("D8", "2"); via(q[0] - 0.83, q[1]); track([q, (q[0] - 0.83, q[1])], "GND", w=0.3)

# ---- VSYS and VBAT trunks, locked at 0.5 mm (Freerouting necked them to 0.3 mm and zig-zagged round C4/U8)
# VSYS: Q4 drain + D4 cathode -> B.Cu along the bottom edge under the SIM holder -> x = 57.9 up past U3 to C1/U2
d4, q4 = pos("D4", "1"), pos("Q4", "2")
track([q4, (q4[0], d4[1]), d4], "/VSYS", w=0.5)
xa, yb, xr, yr = d4[0] + 1.15, 45.2, 57.9, 43.3
via(xa, d4[1], "/VSYS"); track([d4, (xa, d4[1])], "/VSYS", w=0.5)
track([(xa, d4[1]), (xa, yb), (xr, yb), (xr, yr)], "/VSYS", w=0.5, layer=pcbnew.B_Cu)
via(xr, yr, "/VSYS"); c1 = pos("C1", "1"); track([(xr, yr), (xr, c1[1]), c1], "/VSYS", w=0.5)
via(54.45, yb, "/VSYS"); track([(54.45, yb), pos("C4", "1")], "/VSYS", w=0.5)          # LDO input cap
u31, u33 = pos("U3", "1"), pos("U3", "3"); yu = u31[1] + 1.16                          # VIN/EN below U3, above C5
track([u31, (u31[0], yu), (xr, yu)], "/VSYS", w=0.5); track([u33, (u33[0], yu)], "/VSYS", w=0.5)
# VBAT: Q3 drain -> B.Cu trunk -> Q4 source; 0.3 mm taps to R35 (DW01A VCC), C44, C45 and U8 CELL/VDD
q3, q43 = pos("Q3", "2"), pos("Q4", "3")
v1 = (q3[0] + 0.7, q3[1] + 0.7); via(*v1, "/VBAT"); track([q3, v1], "/VBAT", w=0.5)
v2 = (q43[0] - 0.72, q43[1]); via(*v2, "/VBAT"); track([v2, q43], "/VBAT", w=0.5)
xd = 29.0
track([v1, (xd, v1[1]), (v2[0], v1[1] + v2[0] - xd), v2], "/VBAT", w=0.5, layer=pcbnew.B_Cu)
v3 = (25.91, v1[1]); via(*v3, "/VBAT")
r35, c44, c45 = pos("R35", "1"), pos("C44", "1"), pos("C45", "1")
track([v3, (v3[0] + 0.3, v3[1] - 0.3), (r35[0], v3[1] - 0.3), r35], "/VBAT")     # under C43, above U8
track([v3, (v3[0], c44[1]), c44, (c44[0], c44[1] + 0.92), c45], "/VBAT")
u82 = pos("U8", "2"); track([pos("U8", "3"), u82, (u82[0], u82[1] + 0.61), c45], "/VBAT")
# DW01A supply: C43 sits beside U9.5/U9.6 (datasheet R1/C1), R35 diagonally above the VBAT tap
c43 = pos("C43", "1"); track([pos("U9", "5"), c43, pos("R35", "2")], "/DW_VCC", w=0.25)
track([pos("U9", "6"), pos("C43", "2")], "/BATT_N", w=0.3)

# ---- modem bundle: MCU (U4 at 180 deg) -> U5 -> modem, one row, every line in pin order, all F.Cu.
# MCU side: TXD/RTS/CTS run straight across, STATUS/RXD leave the top-side corner pins, DTR/RI the lower right;
# pull resistors sit beside their own line with their supply via outside the bundle.
def T(net, *pts, w=0.15): track(list(pts), net, w=w)
u4, u5, u6 = (lambda n: pos("U4", n)), (lambda n: pos("U5", n)), (lambda n: pos("U6", n))
T("/MCU_MDM_TXD", u4("12"), u5("14"))
T("/MCU_MDM_RTS", u4("11"), (27.2, u4("11")[1]), (27.36, u5("15")[1]), u5("15"))
T("/MCU_MDM_CTS", u4("10"), (27.0, u4("10")[1]), (27.3, u5("16")[1]), u5("16"))
q = pos("R31", "2"); T("/MCU_MDM_CTS", q, (q[0], u4("10")[1]))
q = pos("R31", "1"); via(q[0] - 0.72, q[1], "+3V3"); T("+3V3", q, (q[0] - 0.72, q[1]), w=0.2)
q, r = u4("14"), pos("R27", "1"); T("/MCU_MDM_STATUS", q, (q[0], 7.35), (r[0], 7.35), (26.87, u5("12")[1]), u5("12")); T("/MCU_MDM_STATUS", r, (r[0], 7.35))
q, r = u4("13"), pos("R29", "2"); T("/MCU_MDM_RXD", q, (q[0], 7.85), (25.1, 7.85), (26.53, u5("13")[1]), u5("13")); T("/MCU_MDM_RXD", r, (r[0], 7.85))
q = pos("R29", "1"); via(q[0] - 0.79, q[1], "+3V3"); T("+3V3", q, (q[0] - 0.79, q[1]), w=0.2)
q = u4("6"); T("/MCU_MDM_DTR", q, (23.31, q[1]), (23.6, 13.1), (26.7, 13.1), (27.25, u5("18")[1]), u5("18"))
q = u4("5"); T("/MCU_MDM_RI", q, (23.9, q[1]), (24.08, 13.6), (27.6, 13.6), (27.83, u5("20")[1]), u5("20"))
T("/MCU_MDM_RI", u5("20"), pos("R32", "1"))
# DCD (U5 B3) and NRST (U4 pin 7) sit inside the bundle: each drops to B.Cu and leaves northward, DCD above NRST
q = u5("17"); dv = (26.8, 12.3); via(*dv, "/MCU_MDM_DCD"); T("/MCU_MDM_DCD", q, (27.2, q[1]), dv)
p5, r30 = u4("15"), pos("R30", "2"); via(p5[0], 6.95, "/MCU_MDM_DCD"); T("/MCU_MDM_DCD", p5, (p5[0], 6.95), r30)
track([dv, (dv[0], 7.95), (p5[0] + 0.3, 7.95), (p5[0], 7.65), (p5[0], 6.95)], "/MCU_MDM_DCD", w=0.15, layer=pcbnew.B_Cu)
q = pos("R30", "1"); via(q[0], q[1] - 0.8, "+3V3"); T("+3V3", q, (q[0], q[1] - 0.8), w=0.2)
q = u4("7"); nv = (23.8, 12.5); via(*nv, "/NRST"); T("/NRST", q, (23.4, q[1]), nv)
c17 = pos("C17", "1"); nw = (c17[0], 8.5); via(*nw, "/NRST")   # B.Cu hop ends at C17 (NRST cap) beside J3
track([nv, (nv[0], 8.5), nw], "/NRST", w=0.15, layer=pcbnew.B_Cu); T("/NRST", nw, c17)
# LSE: OSC32_OUT (upper pin) over the crystal to its far pad, OSC32_IN straight down to the near pad
q, y = u4("4"), pos("Y1", "2"); T("/OSC32_OUT", q, (23.6, q[1]), (24.0, 14.3), (y[0] - 0.35, 14.3), (y[0], 14.65), y)
q, y = u4("3"), pos("Y1", "1"); T("/OSC32_IN", q, (23.3, q[1]), (y[0], y[1] - 0.33), y)
# modem side: A pins -> parallel 45-degree fan -> modem pins 1-7 (A8 STATUS hops to pin 42 on the top edge)
for a, m, net in (("8", "1", "/MDM_TXD"), ("7", "2", "/MDM_RXD"), ("6", "3", "/MDM_RTS"), ("5", "4", "/MDM_CTS"),
                  ("4", "5", "/MDM_DCD"), ("3", "6", "/MDM_DTR"), ("1", "7", "/MDM_RI")):
    pa, pm = u5(a), u6(m); dy = pa[1] - pm[1]
    T(net, pa, (34.8, pa[1]), (34.8 + dy, pm[1]), pm)
# STATUS, PWRKEY and NETLIGHT all leave the modem's top edge (pins 42, 39, 41) north of the GNSS RF line:
# STATUS crosses under the RF line on B.Cu; PWRKEY runs B.Cu south-west, hops over STATUS on F.Cu in the gap
# between the RF line and the TXD fan, then B.Cu west to Q1; NETLIGHT runs between them, then south under the
# fan and straight down over the modem USB pair on F.Cu to R16.
q = u5("9"); sv = (34.95, 7.55); via(*sv, "/MDM_STATUS"); T("/MDM_STATUS", q, (34.55, q[1]), (34.95, 8.22), sv)
track([sv, (36.4, sv[1]), (36.4, 4.6), (u6("42")[0], 1.85)], "/MDM_STATUS", w=0.15, layer=pcbnew.B_Cu)
v1, v2 = (37.9, 5.75), (35.0, 5.75); via(*v1, "/MDM_PWRKEY"); via(*v2, "/MDM_PWRKEY")
track([(u6("39")[0], 1.85), (u6("39")[0], 2.5), v1], "/MDM_PWRKEY", w=0.2, layer=pcbnew.B_Cu); T("/MDM_PWRKEY", v1, v2, w=0.2)
c = pos("Q1", "3"); qv = (c[0] + 0.5, v2[1]); via(*qv, "/MDM_PWRKEY")
track([v2, qv], "/MDM_PWRKEY", w=0.2, layer=pcbnew.B_Cu); T("/MDM_PWRKEY", c, (qv[0], c[1] + 0.5), qv, w=0.2)
T("/MDM_PWRKEY", qv, pos("TP2", "1"), w=0.2)
n = u6("41"); n1 = (37.2, 13.6); via(*n1, "/MDM_NETLIGHT"); r16 = pos("R16", "1")
track([(n[0], 1.85), (n[0], 2.4), (37.2, 4.9), n1], "/MDM_NETLIGHT", w=0.15, layer=pcbnew.B_Cu)
T("/MDM_NETLIGHT", n1, (37.2, r16[1] - 2.1), (35.1, r16[1]), r16)      # F.Cu over the modem USB pair to R16 (Q2 base)

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
