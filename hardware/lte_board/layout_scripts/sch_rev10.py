"""Schematic rev 0.10: a second Qwiic port J11 (DNP, for the bottom side) on its own bus, I2C3, so a damaged cable on
one sensor string can't hang the other (J3 = I2C2, the fuel gauge = I2C1).
  I2C3_SCL  PA8 (AF7)                      LED_USER moves PA8 -> PB15 (pin 28, next to PA8 on the package)
  I2C3_SDA  PB4 (AF7)                      stays on J4 pin 6 as well (was EXP_PB4): SPI1 MISO there now has a pull-up
  J11       clone of J3 (JST SH 4-pin, C145956), DNP, not in the BOM
  R43 R44   4.7k pull-ups to +3V3 (clones of R12/R13, C25900), fitted
usage: sch_rev10.py lte_board.kicad_sch"""
import re, sys, uuid
SCH = sys.argv[1]
s = open(SCH).read()
U = lambda: str(uuid.uuid4())
def fmt(v): return ("%.4f" % v).rstrip("0").rstrip(".")
assert '"Reference" "J11"' not in s, "already applied"

def span(head):
    i = s.index(head) + 1
    return i, s.index("\n\t)\n", i) + 4

def inst_block(ref):
    i = s.index(f'(property "Reference" "{ref}"')
    a = s.rindex("\n\t(symbol\n", 0, i) + 1
    return a, s.index("\n\t)\n", i) + 4

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

def rename(x, y, old, new):
    global s
    a, b = span(f'\n\t(label "{old}"\n\t\t(at {fmt(x)} {fmt(y)} ')
    s = s[:a] + s[a:b].replace(f'(label "{old}"', f'(label "{new}"', 1) + s[b:]

def shift(blk, X0, Y0, x, y):
    return re.sub(r'\(at ([-\d.]+) ([-\d.]+)( [-\d.]+)?\)',
                  lambda m: f'(at {fmt(float(m.group(1)) - X0 + x)} {fmt(float(m.group(2)) - Y0 + y)}{m.group(3) or ""})', blk)

def clone(src, ref, x, y):
    """copy of the instance src at (x, y) as ref (new uuids)"""
    a, b = inst_block(src); blk = s[a:b]
    X0, Y0 = map(float, re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+) [-\d.]+\)', blk).groups())
    blk = re.sub(r'\(uuid "[^"]+"\)', lambda m: f'(uuid "{U()}")', shift(blk, X0, Y0, x, y))
    return blk.replace(f'"{src}"', f'"{ref}"')

pwr_n = [sorted(int(n) for n in re.findall(r'"#PWR(\d+)"', s))[-1]]
def power_at(lib_id, sx, sy, x, y):
    """copy of the power symbol lib_id placed at (sx, sy) (same rotation), moved to (x, y)"""
    m = re.search(r'\n\t\(symbol\n\t\t\(lib_id "%s"\)\n\t\t\(at %s %s \d+\)' % (re.escape(lib_id), fmt(sx), fmt(sy)), s)
    ref = re.search(r'\(property "Reference" "([^"]+)"', s[m.start():]).group(1)
    pwr_n[0] += 1
    return clone(ref, "#PWR%03d" % pwr_n[0], x, y)

new = ""
# ---------------------------------------------------------------- U4: PA8 -> I2C3_SCL, PB15 -> LED_USER, PB4 -> I2C3_SDA
rename(261.62, 83.82, "LED_USER", "I2C3_SCL")                       # PA8 (pin 29)
a, b = span('\n\t(no_connect\n\t\t(at 259.08 119.38)'); s = s[:a] + s[b:]   # PB15 (pin 28)
new += wire((259.08, 119.38), (261.62, 119.38)) + label("LED_USER", 261.62, 119.38, 0)
rename(226.06, 106.68, "EXP_PB4", "I2C3_SDA")                       # PB4 (pin 40) at U4 ...
rename(48.26, 297.18, "EXP_PB4", "I2C3_SDA")                        # ... and at J4 pin 6

# ---------------------------------------------------------------- J11: J3's clone, DNP / not in BOM, wired like J3
JX, JY = 104.14, 264.16                                              # J3 sits at 86.36, 264.16
blk = clone("J3", "J11", JX, JY)
blk = blk.replace("\t\t(in_bom yes)\n", "\t\t(in_bom no)\n").replace("\t\t(dnp no)\n", "\t\t(dnp yes)\n")
blk = blk.replace('"I2C_Qwiic"', '"I2C3_Qwiic"')
new += blk
px, lx = JX - 6.35, JX - 8.89                                        # pin ends, stub ends (2.54 to the left)
new += wire((px, JY - 5.08), (lx, JY - 5.08)) + power_at("lte_board:GND", 77.47, 259.08, lx, JY - 5.08)
new += wire((px, JY - 2.54), (lx, JY - 2.54)) + power_at("lte_board:+3V3", 77.47, 261.62, lx, JY - 2.54)
new += wire((px, JY), (lx, JY)) + label("I2C3_SDA", lx, JY, 180)
new += wire((px, JY + 2.54), (lx, JY + 2.54)) + label("I2C3_SCL", lx, JY + 2.54, 180)

# ---------------------------------------------------------------- R43 / R44: I2C3 pull-ups, copies of R12 / R13
RY = 260.35
for ref, src, x, net in (("R43", "R12", 116.84, "I2C3_SCL"), ("R44", "R13", 124.46, "I2C3_SDA")):
    new += clone(src, ref, x, RY)                                    # vertical: pin 1 top (+3V3), pin 2 bottom
    m = re.search(r'\n\t\(symbol\n\t\t\(lib_id "lte_board:\+3V3"\)\n\t\t\(at ([-\d.]+) ([-\d.]+) 0\)', s)
    pwr_n[0] += 1
    new += wire((x, RY - 3.81), (x, RY - 6.35)) + clone(re.search(r'\(property "Reference" "([^"]+)"', s[m.start():]).group(1),
                                                        "#PWR%03d" % pwr_n[0], x, RY - 6.35)
    new += wire((x, RY + 3.81), (x, RY + 6.35)) + label(net, x, RY + 6.35, 0)

i = s.index("\n\t(sheet_instances") if "\n\t(sheet_instances" in s else s.rindex("\n)")
s = s[:i + 1] + new + s[i + 1:]
open(SCH, "w").write(s)
print("schematic rev 0.10 edits applied")
