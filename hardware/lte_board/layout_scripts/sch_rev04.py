"""Schematic rev 0.4 (pre-fab audit): 32.768 kHz LSE crystal Y1 + C54/C55 on PC14/PC15 (U4 pins 3/4),
L1 on the Sunlord SWPA4030S recommended land. Works on the KiCad 9 file format (tab-indented).
usage: sch_rev04.py lte_board.kicad_sch lte_board.kicad_sym"""
import re, sys, uuid
SCH, LIB = sys.argv[1:3]
s = open(SCH).read()
ROOT = "/7ded1cb8-0547-516d-a7f6-d4c083a7d11d"
U = lambda: str(uuid.uuid4())
def fmt(v): return ("%.4f" % v).rstrip("0").rstrip(".")
def sub1(a, b):
    global s
    assert s.count(a) == 1, f"{s.count(a)} matches: {a[:80]}"
    s = s.replace(a, b)
assert '"Reference" "Y1"' not in s, "already applied"

def inst_block(ref):
    """the top-level (symbol ...) block whose Reference is ref"""
    i = s.index(f'(property "Reference" "{ref}"')
    a = s.rindex("\n\t(symbol\n", 0, i) + 1
    b = s.index("\n\t)\n", i) + 4
    return a, b

def wire(x0, y0, x1, y1):
    return (f'\t(wire\n\t\t(pts\n\t\t\t(xy {fmt(x0)} {fmt(y0)}) (xy {fmt(x1)} {fmt(y1)})\n\t\t)\n'
            f'\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n\t\t(uuid "{U()}")\n\t)\n')

def label(name, x, y, ang):
    just = "right bottom" if ang in (180, 270) else "left bottom"
    return (f'\t(label "{name}"\n\t\t(at {fmt(x)} {fmt(y)} {ang})\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n'
            f'\t\t\t)\n\t\t\t(justify {just})\n\t\t)\n\t\t(uuid "{U()}")\n\t)\n')

def clone(src_ref, ref, x, y, props, lib_id=None):
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
    return blk

# ---------------------------------------------------------------- 1. crystal library symbol (from KiCad's Device:Crystal)
dev = open("/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/Device.kicad_sym").read()
i = dev.index('\n\t(symbol "Crystal"\n') + 1; j = dev.index("\n\t)\n", i) + 4
xtal = dev[i:j].replace('(symbol "Crystal"', '(symbol "lte_board:Crystal"', 1)
xtal = "".join("\t" + ln if ln else ln for ln in xtal.splitlines(True))          # lib_symbols entries sit one tab deeper
li = s.index("\n\t(lib_symbols\n"); le = s.index("\n\t)\n", li)          # end of lib_symbols
s = s[:le + 1] + xtal + s[le + 1:]
lib = open(LIB).read()
if '"lte_board:Crystal"' not in lib:
    one = " ".join(dev[i:j].replace('(symbol "Crystal"', '(symbol "lte_board:Crystal"', 1).split())
    lib = lib.rstrip().rstrip(")").rstrip() + "\n  " + one + "\n)\n"
    open(LIB, "w").write(lib)

# ---------------------------------------------------------------- 2. U4 PC14/PC15: no-connects -> stubs + labels
for (y, net) in ((83.82, "OSC32_IN"), (86.36, "OSC32_OUT")):
    m = re.search(r'\t\(no_connect\n\t\t\(at 228\.6 %s\)\n\t\t\(uuid "[^"]+"\)\n\t\)\n' % re.escape(fmt(y)), s)
    assert m, f"no-connect at 228.6 {y}"
    s = s[:m.start()] + wire(228.6, y, 226.06, y) + label(net, 226.06, y, 180) + s[m.end():]

# ---------------------------------------------------------------- 3. Y1, C54, C55 (left of U4)
XY, YY = 205.74, 86.36               # crystal pins at XY -/+ 3.81
XC1, XC2, YC = 199.39, 212.09, 97.79  # caps: pin 1 at YC - 3.81, pin 2 at YC + 3.81
new = clone("C34", "Y1", XY, YY, {"Value": "32.768kHz", "Footprint": "Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm",
                                     "LCSC": "C97604", "MPN": "SC-32S 32.768kHz 20PPM 7pF",
                                     "Description": "32.768 kHz, 7 pF load, +/-20 ppm (Seiko SC-32S); LSE for the RTC"},
            lib_id="lte_board:Crystal")
new = re.sub(r'(\(property "(Reference|Value)" "[^"]*"\n\t\t\t\(at )([-\d.]+) ([-\d.]+) 0\)',     # labels above the body
             lambda m: f'{m.group(1)}{fmt(XY)} {fmt(YY - (5.08 if m.group(2) == "Reference" else 3.3))} 0)', new)
new = new.replace("\t\t\t\t(justify left)\n", "")
for ref, x in (("C54", XC1), ("C55", XC2)):
    new += clone("C34", ref, x, YC, {"Description": "LSE load capacitor (C0G)"})
pwr = sorted(int(n) for n in re.findall(r'"#PWR(\d+)"', s))[-1]
a, b = inst_block("#PWR088"); gblk = s[a:b]
for k, x in enumerate((XC1, XC2)):
    g = gblk; X0, Y0 = 487.68, 231.14
    g = g.replace(f"(at {fmt(X0)} {fmt(Y0)}", f"(at {fmt(x)} {fmt(YC + 6.35)}")
    g = re.sub(r'\(uuid "[^"]+"\)', lambda m: f'(uuid "{U()}")', g).replace('"#PWR088"', f'"#PWR{pwr + 1 + k:03d}"')
    new += g
w = ""
w += wire(XY - 3.81, YY, XY - 6.35, YY) + label("OSC32_IN", XY - 6.35, YY, 180)
w += wire(XY + 3.81, YY, XY + 6.35, YY) + label("OSC32_OUT", XY + 6.35, YY, 0)
for x, net in ((XC1, "OSC32_IN"), (XC2, "OSC32_OUT")):
    w += wire(x, YC - 3.81, x, YC - 6.35) + label(net, x, YC - 6.35, 90)
    w += wire(x, YC + 3.81, x, YC + 6.35)
i = s.index("\n\t(sheet_instances") if "\n\t(sheet_instances" in s else s.rindex("\n)")
s = s[:i + 1] + w + new + s[i + 1:]

# ---------------------------------------------------------------- 4. L1 -> Sunlord recommended land
a, b = inst_block("L1")
assert '"Inductor_SMD:L_Wuerth_MAPI-4030"' in s[a:b]
s = s[:a] + s[a:b].replace('"Inductor_SMD:L_Wuerth_MAPI-4030"', '"lte_board_lcsc:L_Sunlord_SWPA4030S"') + s[b:]

open(SCH, "w").write(s)
print("schematic rev 0.4 edits applied")
