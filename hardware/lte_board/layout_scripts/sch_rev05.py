"""Schematic rev 0.5 (antennas): switched bias tee for an active GNSS antenna, ESD on both antenna ports, SMA jacks.
Per SIM7080G Hardware Design V1.05 section 4 (Fig. 28 LTE, Fig. 29 active GNSS antenna):
  LTE : R19 0R / C40,C41 DNP (unchanged) -> C61 100pF series (ESD) -> D6 TVS -> J6 U.FL (fitted)
        -> R40 0R DNP -> J10 SMA edge jack (hand-soldered option; fit R40 when J10 is used)
  GNSS: U6.68 -> R20 0R with C59/C58 DNP shunts -> C56 100pF DC block -> D5 TVS, L2 47nH + R38 10R bias feed
        -> J7 SMA edge jack (hand-soldered). Bias from U10 TPS22945 (100-200 mA current limit) on +3V3,
        ON = PA15 (R39 pull-down: off through reset), OC flag -> PB3 (use the internal pull-up).
Works on the KiCad 9 file format (tab-indented).  usage: sch_rev05.py lte_board.kicad_sch lte_board.kicad_sym"""
import re, sys, uuid
SCH, LIB = sys.argv[1:3]
s = open(SCH).read()
U = lambda: str(uuid.uuid4())
def fmt(v): return ("%.4f" % v).rstrip("0").rstrip(".")
assert '"Reference" "U10"' not in s, "already applied"

def inst_block(ref):
    """the top-level (symbol ...) block whose Reference is ref"""
    i = s.index(f'(property "Reference" "{ref}"')
    a = s.rindex("\n\t(symbol\n", 0, i) + 1
    b = s.index("\n\t)\n", i) + 4
    return a, b

def wire(*pts):
    out = ""
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        out += (f'\t(wire\n\t\t(pts\n\t\t\t(xy {fmt(x0)} {fmt(y0)}) (xy {fmt(x1)} {fmt(y1)})\n\t\t)\n'
                f'\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n\t\t(uuid "{U()}")\n\t)\n')
    return out

def label(name, x, y, ang):
    just = "right bottom" if ang in (180, 270) else "left bottom"
    return (f'\t(label "{name}"\n\t\t(at {fmt(x)} {fmt(y)} {ang})\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n'
            f'\t\t\t)\n\t\t\t(justify {just})\n\t\t)\n\t\t(uuid "{U()}")\n\t)\n')

def clone(src_ref, ref, x, y, props, lib_id=None, dnp=None, in_bom=None):
    """copy an instance block to (x, y) with new uuids, reference and property values"""
    a, b = inst_block(src_ref); blk = s[a:b]
    X0, Y0 = map(float, re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+) 0\)', blk).groups())
    blk = re.sub(r'\(at ([-\d.]+) ([-\d.]+)( [-\d.]+)?\)',
                 lambda m: f'(at {fmt(float(m.group(1)) - X0 + x)} {fmt(float(m.group(2)) - Y0 + y)}{m.group(3) or ""})', blk)
    blk = re.sub(r'\(uuid "[^"]+"\)', lambda m: f'(uuid "{U()}")', blk)
    blk = blk.replace(f'"{src_ref}"', f'"{ref}"')
    for k, v in props.items():
        blk, n = re.subn(r'\(property "%s" "[^"]*"' % k, f'(property "{k}" "{v}"', blk); assert n == 1, (ref, k)
    if lib_id:
        blk = re.sub(r'\(lib_id "[^"]+"\)', f'(lib_id "{lib_id}")', blk)
    if dnp is not None:
        blk = re.sub(r'\n\t\t\(in_bom \w+\)', "\n\t\t(in_bom %s)" % ("no" if dnp else "yes"), blk, 1)
        blk = re.sub(r'\n\t\t\(dnp \w+\)', "\n\t\t(dnp %s)" % ("yes" if dnp else "no"), blk, 1)
    if in_bom is not None:
        blk = re.sub(r'\n\t\t\(in_bom \w+\)', "\n\t\t(in_bom %s)" % ("yes" if in_bom else "no"), blk, 1)
    return blk

pwr_n = [sorted(int(n) for n in re.findall(r'"#PWR(\d+)"', s))[-1]]
def power(src_ref, x, y):
    """copy a power symbol instance (GND / +3V3) to (x, y)"""
    a, b = inst_block(src_ref); g = s[a:b]
    X0, Y0 = map(float, re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+) 0\)', g).groups())
    g = re.sub(r'\(at ([-\d.]+) ([-\d.]+)( [-\d.]+)?\)',
               lambda m: f'(at {fmt(float(m.group(1)) - X0 + x)} {fmt(float(m.group(2)) - Y0 + y)}{m.group(3) or ""})', g)
    pwr_n[0] += 1
    return re.sub(r'\(uuid "[^"]+"\)', lambda m: f'(uuid "{U()}")', g).replace(f'"{src_ref}"', f'"#PWR{pwr_n[0]:03d}"')

def first_ref(lib_id):
    """reference of a rotation-0 instance of lib_id"""
    for m in re.finditer(r'\n\t\(symbol\n\t\t\(lib_id "%s"\)\n\t\t\(at [-\d.]+ [-\d.]+ 0\)' % re.escape(lib_id), s):
        return re.search(r'\(property "Reference" "([^"]+)"', s[m.start():]).group(1)
    raise KeyError(lib_id)
GND, P3V3 = first_ref("lte_board:GND"), first_ref("lte_board:+3V3")

# ---------------------------------------------------------------- 1. library symbols: D_TVS (KiCad Device), TPS22945
dev = open("/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/Device.kicad_sym").read()
i = dev.index('\n\t(symbol "D_TVS"\n') + 1; j = dev.index("\n\t)\n", i) + 4
tvs = dev[i:j].replace('(symbol "D_TVS"', '(symbol "lte_board:D_TVS"', 1)
# TPS22945 from the SY8089 symbol (same 3-left/2-right SOT-23-5 body); pinout per TI SBVS073 / LCSC C47507 EasyEDA symbol:
# 1 VOUT, 2 GND, 3 OC (open drain, active low), 4 ON (active high), 5 VIN
i = s.index('\t\t(symbol "lte_board:SY8089AAAC"\n'); j = s.index("\n\t\t)\n", i) + 5
tps = s[i:j].replace("lte_board:SY8089AAAC", "lte_board:TPS22945").replace('"SY8089AAAC_', '"TPS22945_')
tps = tps.replace('(property "Value" "SY8089AAAC"', '(property "Value" "TPS22945"')
tps = tps.replace('"2A 1MHz synchronous buck, VFB=0.6V"', '"Current-limited load switch, 100-200 mA, active-high ON, open-drain OC flag"')
for (old_name, old_num), (typ, name, num) in {("IN", "4"): ("power_in", "VIN", "5"), ("EN", "1"): ("input", "ON", "4"),
                                            ("LX", "3"): ("power_out", "VOUT", "1"), ("FB", "5"): ("open_collector", "OC", "3")}.items():
    pat = re.compile(r'\(pin (\w+) line(\n(?:(?!\(pin ).)*?)\(name "%s"((?:(?!\(pin ).)*?)\(number "%s"' % (old_name, old_num), re.S)
    tps, n = pat.subn(lambda m: f'(pin {typ} line{m.group(2)}(name "{name}"{m.group(3)}(number "{num}"', tps); assert n == 1, old_name
li = s.index("\n\t(lib_symbols\n"); le = s.index("\n\t)\n", li)
s = s[:le + 1] + "".join("\t" + ln if ln else ln for ln in tvs.splitlines(True)) + tps.lstrip("\n").rstrip("\n") + "\n" + s[le + 1:]
lib = open(LIB).read()
add = []
if '"lte_board:D_TVS"' not in lib: add.append(" ".join(tvs.split()))
if '"lte_board:TPS22945"' not in lib: add.append(" ".join(tps.split()))
if add:
    lib = lib.rstrip().rstrip(")").rstrip() + "".join("\n  " + a for a in add) + "\n)\n"
    open(LIB, "w").write(lib)

# ---------------------------------------------------------------- 2. relabel the existing RF nets
def relabel(old, x, y, new):
    global s
    pat = r'(\t\(label )"%s"(\n\t\t\(at %s %s )' % (old, re.escape(fmt(x)), re.escape(fmt(y)))
    s, n = re.subn(pat, r'\1"%s"\2' % new, s); assert n == 1, (old, x, y)
relabel("LTE_ANT", 426.72, 300.99, "LTE_MATCH")     # R19 pin 2
relabel("LTE_ANT", 441.96, 288.29, "LTE_MATCH")     # C41 (antenna-side pi shunt) stays on R19's output
relabel("GNSS_ANT", 513.08, 300.99, "GNSS_MATCH")   # R20 pin 2; GNSS_ANT is now the antenna side of the DC block

# J7: U.FL -> SMA edge jack, hand-soldered (not in the JLC BOM/CPL)
a, b = inst_block("J7"); blk = s[a:b]
for k, v in {"Value": "GNSS_ANT (SMA)", "Footprint": "lte_board_lcsc:SMA_Amphenol_132322_EdgeMount", "LCSC": "C42394535",
             "MPN": "Amphenol 132322", "Description": "SMA end-launch jack, hand-soldered (not JLC-assembled); active GNSS antenna"}.items():
    blk, n = re.subn(r'\(property "%s" "[^"]*"' % k, f'(property "{k}" "{v}"', blk); assert n == 1, k
blk = re.sub(r'\n\t\t\(in_bom yes\)', "\n\t\t(in_bom no)", blk, 1)
s = s[:a] + blk + s[b:]

# ---------------------------------------------------------------- 3. new parts (free area below the RF block)
C0402 = "Capacitor_SMD:C_0402_1005Metric"; R0402 = "Resistor_SMD:R_0402_1005Metric"
new, w = "", ""
def two_pin(src, ref, x, y, top, bot, props, **kw):
    """vertical 2-pin part: pin 1 (top) and pin 2 (bottom) get a stub + label, or a GND / +3V3 symbol"""
    global new, w
    new += clone(src, ref, x, y, props, **kw)
    for py, sy, net, ang in ((y - 3.81, y - 6.35, top, 90), (y + 3.81, y + 6.35, bot, 270)):
        w += wire((x, py), (x, sy))
        if net == "GND": new += power(GND, x, sy)
        elif net == "+3V3": new += power(P3V3, x, sy)
        else: w += label(net, x, sy, ang)
def tvs_part(ref, x, y, net, props):
    """horizontal TVS: pin 1 (left) to net, pin 2 (right) to GND"""
    global new, w
    new += clone("C34", ref, x, y, props, lib_id="lte_board:D_TVS")
    w += wire((x - 3.81, y), (x - 6.35, y)) + label(net, x - 6.35, y, 180)
    w += wire((x + 3.81, y), (x + 6.35, y), (x + 6.35, y + 2.54)); new += power(GND, x + 6.35, y + 2.54)

# LTE (row at y = 340.36)
two_pin("C34", "C61", 411.48, 340.36, "LTE_MATCH", "LTE_ANT",
        {"Value": "100pF", "Footprint": C0402, "LCSC": "C1546", "MPN": "0402CG101J500NT",
         "Description": "LTE antenna series cap, fitted (SIM7080G HD V1.05 Fig. 28: ESD)"})
tvs_part("D6", 431.8, 340.36, "LTE_ANT", {"Value": "ESD103-B1-02EL", "Footprint": "lte_board_lcsc:TSLP-2-20_L1.0-W0.6-P0.65-BI",
         "LCSC": "C535146", "MPN": "ESD103-B1-02EL E6327", "Description": "LTE antenna ESD, 0.09 pF @1 GHz, VRWM 15 V"})
two_pin("R19", "R40", 452.12, 340.36, "LTE_ANT", "LTE_SMA",
        {"Description": "DNP: fit 0R to use the SMA jack J10 instead of the U.FL J6"}, dnp=True)
new += clone("J6", "J10", 477.52, 340.36, {"Value": "LTE_ANT (SMA)", "Footprint": "lte_board_lcsc:SMA_Amphenol_132322_EdgeMount",
             "LCSC": "C42394535", "MPN": "Amphenol 132322", "Description": "SMA end-launch jack, optional, hand-soldered; fit R40 with it"},
             in_bom=False)
w += wire((471.17, 340.36 - 2.54), (463.55, 340.36 - 2.54)) + label("LTE_SMA", 463.55, 340.36 - 2.54, 180)
w += wire((471.17, 340.36), (468.63, 340.36), (468.63, 342.9)); new += power(GND, 468.63, 342.9)

# GNSS RF (row at y = 340.36)
two_pin("C34", "C56", 500.38, 340.36, "GNSS_MATCH", "GNSS_ANT",
        {"Value": "100pF", "Footprint": C0402, "LCSC": "C1546", "MPN": "0402CG101J500NT",
         "Description": "GNSS DC block: keeps the antenna bias off the module pin (HD V1.05 4.3.2 note 5)"})
two_pin("C40", "C58", 510.54, 340.36, "GNSS_MATCH", "GND", {"Description": "GNSS match shunt (DC-free side), DNP"})
two_pin("C40", "C59", 520.7, 340.36, "MDM_GNSS", "GND", {"Description": "GNSS match shunt, module side, DNP"})
tvs_part("D5", 538.48, 340.36, "GNSS_ANT", {"Value": "WE05DGCF-B", "Footprint": "lte_board_lcsc:DFN1006-2L-BI",
         "LCSC": "C3039401", "MPN": "WE05DGCF-B", "Description": "GNSS antenna ESD, 0.18 pF, VRWM 5 V (clears the 3.3 V bias)"})

# GNSS bias feed (row at y = 370.84)
two_pin("L1", "L2", 500.38, 370.84, "GNSS_ANT", "GNSS_BIAS",
        {"Value": "47nH", "Footprint": "Inductor_SMD:L_0402_1005Metric", "LCSC": "C192855", "MPN": "LQW15AN47NJ00D",
         "Description": "GNSS bias RF choke, SRF >= 2.9 GHz (high impedance at 1575 MHz)"})
two_pin("R19", "R38", 510.54, 370.84, "GNSS_BIAS", "GNSS_VANT",
        {"Value": "10R", "LCSC": "C25077", "MPN": "0402WGF100JTCE", "Description": "GNSS bias series resistor (HD V1.05 Fig. 29)"})
two_pin("C34", "C57", 520.7, 370.84, "GNSS_VANT", "GND",
        {"Value": "100nF", "LCSC": "C1525", "MPN": "CL05B104KO5NNNC", "Description": "antenna supply decoupling"})
two_pin("C34", "C60", 530.86, 370.84, "+3V3", "GND",
        {"Value": "100nF", "LCSC": "C1525", "MPN": "CL05B104KO5NNNC", "Description": "U10 input decoupling"})
two_pin("R19", "R39", 541.02, 370.84, "GNSS_ANT_EN", "GND",
        {"Value": "100k", "LCSC": "C25741", "MPN": "0402WGF1003TCE", "Description": "keeps the antenna supply off through reset"})
new += clone("U2", "U10", 563.88, 370.84, {"Value": "TPS22945", "Footprint": "lte_board_lcsc:SC-70-5_L2.1-W1.3-P0.65-LS2.1-BL",
             "LCSC": "C47507", "MPN": "TPS22945DCKR", "Description": "active GNSS antenna supply switch, 100-200 mA limit"},
             lib_id="lte_board:TPS22945")
XL, XR, Y = 563.88 - 8.89, 563.88 + 8.89, 370.84
w += wire((XL, Y - 2.54), (XL - 2.54, Y - 2.54), (XL - 2.54, Y - 5.08)); new += power(P3V3, XL - 2.54, Y - 5.08)   # VIN
w += wire((XL, Y), (XL - 5.08, Y)) + label("GNSS_ANT_EN", XL - 5.08, Y, 180)                                       # ON
w += wire((XL, Y + 2.54), (XL - 2.54, Y + 2.54), (XL - 2.54, Y + 5.08)); new += power(GND, XL - 2.54, Y + 5.08)   # GND
w += wire((XR, Y - 2.54), (XR + 2.54, Y - 2.54)) + label("GNSS_VANT", XR + 2.54, Y - 2.54, 0)                      # VOUT
w += wire((XR, Y), (XR + 2.54, Y)) + label("GNSS_ANT_FLT", XR + 2.54, Y, 0)                                        # OC

# ---------------------------------------------------------------- 4. MCU: PA15 (pin 38) = GNSS_ANT_EN, PB3 (pin 39) = GNSS_ANT_FLT
for (x, y, x2, net, ang) in ((259.08, 101.6, 261.62, "GNSS_ANT_EN", 0), (228.6, 104.14, 226.06, "GNSS_ANT_FLT", 180)):
    m = re.search(r'\t\(no_connect\n\t\t\(at %s %s\)\n\t\t\(uuid "[^"]+"\)\n\t\)\n' % (re.escape(fmt(x)), re.escape(fmt(y))), s)
    assert m, f"no-connect at {x} {y}"
    s = s[:m.start()] + wire((x, y), (x2, y)) + label(net, x2, y, ang) + s[m.end():]

i = s.index("\n\t(sheet_instances") if "\n\t(sheet_instances" in s else s.rindex("\n)")
s = s[:i + 1] + w + new + s[i + 1:]
open(SCH, "w").write(s)
print("schematic rev 0.5 edits applied")
