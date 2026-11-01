"""Schematic rev 0.6 (audit follow-up, DESIGN.md H10): parts the 2026-10-31 audit asked for.
  C62  100 nF on VDD_EXT at U5 VCCA pin 2 (H10a; C20/C35 sit ~16 mm away at modem pin 40)
  D7   ESD5651N-2/TR TVS on +3V8 at the VBAT bus (H10g; SIM7080G HD V1.05 Table 8, part 3)
  D8   WE05DGCF-B ESD on MDM_PWRKEY (H10g; HD V1.05 3.2.1 "strongly recommended" near the pin; 5 V VRWM > 1.8 V)
  C1   10 uF 10 V 0603 -> 10 uF 25 V 0805 (H10h; the 0603 drops to ~5 uF at the 4.6 V buck input)
Works on the KiCad 9 file format (tab-indented).  usage: sch_rev06.py lte_board.kicad_sch"""
import re, sys, uuid
SCH = sys.argv[1]
s = open(SCH).read()
U = lambda: str(uuid.uuid4())
def fmt(v): return ("%.4f" % v).rstrip("0").rstrip(".")
assert '"Reference" "D8"' not in s, "already applied"

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

def clone(src_ref, ref, x, y, props):
    """copy an instance block to (x, y) with new uuids, reference and property values"""
    a, b = inst_block(src_ref); blk = s[a:b]
    X0, Y0 = map(float, re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+) 0\)', blk).groups())
    blk = re.sub(r'\(at ([-\d.]+) ([-\d.]+)( [-\d.]+)?\)',
                 lambda m: f'(at {fmt(float(m.group(1)) - X0 + x)} {fmt(float(m.group(2)) - Y0 + y)}{m.group(3) or ""})', blk)
    blk = re.sub(r'\(uuid "[^"]+"\)', lambda m: f'(uuid "{U()}")', blk)
    blk = blk.replace(f'"{src_ref}"', f'"{ref}"')
    for k, v in props.items():
        blk, n = re.subn(r'\(property "%s" "[^"]*"' % k, f'(property "{k}" "{v}"', blk); assert n == 1, (ref, k)
    return blk

pwr_n = [sorted(int(n) for n in re.findall(r'"#PWR(\d+)"', s))[-1]]
def power(src_ref, x, y):
    """copy a power symbol instance (GND / +3V8) to (x, y)"""
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
GND, P3V8 = first_ref("lte_board:GND"), first_ref("lte_board:+3V8")

# ---------------------------------------------------------------- 1. C1: 0805 25 V (DC-bias derating at the buck input)
a, b = inst_block("C1"); blk = s[a:b]
for k, v in {"Footprint": "Capacitor_SMD:C_0805_2012Metric", "LCSC": "C15850", "MPN": "CL21A106KAYNNNE",
             "Description": "buck input cap; 25 V 0805 keeps more of its 10 uF at 4.6 V than a 10 V 0603"}.items():
    blk, n = re.subn(r'\(property "%s" "[^"]*"' % k, f'(property "{k}" "{v}"', blk); assert n == 1, k
s = s[:a] + blk + s[b:]

# ---------------------------------------------------------------- 2. new parts (free area left of the rev 0.5 rows)
new, w = "", ""
Y = 340.36
# C62: vertical, pin 1 (top) VDD_EXT, pin 2 (bottom) GND
x = 330.2
new += clone("C34", "C62", x, Y, {"Value": "100nF", "LCSC": "C1525", "MPN": "CL05B104KO5NNNC",
                                  "Description": "U5 VCCA (pin 2) decoupling, at the pin"})
w += wire((x, Y - 3.81), (x, Y - 6.35)) + label("VDD_EXT", x, Y - 6.35, 90)
w += wire((x, Y + 3.81), (x, Y + 6.35)); new += power(GND, x, Y + 6.35)
# TVS diodes: horizontal, pin 1 (left) to the protected net, pin 2 (right) to GND
def tvs(ref, x, props, net=None, sym=None):
    global new, w
    new += clone("D5", ref, x, Y, props)
    if sym:
        w += wire((x - 3.81, Y), (x - 6.35, Y), (x - 6.35, Y - 2.54)); new += power(sym, x - 6.35, Y - 2.54)
    else:
        w += wire((x - 3.81, Y), (x - 6.35, Y)) + label(net, x - 6.35, Y, 180)
    w += wire((x + 3.81, Y), (x + 6.35, Y), (x + 6.35, Y + 2.54)); new += power(GND, x + 6.35, Y + 2.54)
tvs("D7", 350.52, {"Value": "ESD5651N-2/TR", "Footprint": "lte_board_lcsc:DFN1006-2L-BI-1", "LCSC": "C239784",
                   "MPN": "ESD5651N-2/TR", "Description": "VBAT TVS, VRWM 4.5 V, 35 A 8/20 us (SIM7080G HD V1.05 Table 8)"},
    sym=P3V8)
tvs("D8", 375.92, {"Description": "PWRKEY ESD diode (SIM7080G HD V1.05 3.2.1), VRWM 5 V"}, net="MDM_PWRKEY")

i = s.index("\n\t(sheet_instances") if "\n\t(sheet_instances" in s else s.rindex("\n)")
s = s[:i + 1] + w + new + s[i + 1:]
open(SCH, "w").write(s)
print("schematic rev 0.6 edits applied")
