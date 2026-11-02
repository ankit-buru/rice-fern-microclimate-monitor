"""Schematic rev 0.8 (routing simplification, part 2): peripheral pins chosen for the 180-degree MCU (after sch_rev07).
  Qwiic J3      I2C1 PB6/PB7 -> I2C2 PB13 (SCL) / PB14 (SDA): left side of U4, facing J3
  fuel gauge U8 own bus on I2C1 PB7 (FG_SDA, AF1) / PB8 (FG_SCL, AF4), new 4.7k pull-ups R41/R42; BAT_ALRT
                PA8 -> PB9: bottom side of U4 in U8's pin order SDA, SCL, ALRT (a damaged sensor cable can no
                longer hang the battery monitor)
  LED_USER      PB4 -> PB5;  SIM_DET PB5 -> PB6;  MDM_PWR_EN PB9 -> PB3 (straight down to R28)
usage: sch_rev08.py lte_board.kicad_sch"""
import re, sys, uuid
SCH = sys.argv[1]
s = open(SCH).read()
U = lambda: str(uuid.uuid4())
def fmt(v): return ("%.4f" % v).rstrip("0").rstrip(".")
assert '"Reference" "R41"' not in s, "already applied"

def inst_block(ref):
    i = s.index(f'(property "Reference" "{ref}"')
    a = s.rindex("\n\t(symbol\n", 0, i) + 1
    return a, s.index("\n\t)\n", i) + 4

def item(kind, x, y, text=None):
    head = f'\n\t(no_connect\n\t\t(at {fmt(x)} {fmt(y)})' if kind == "no_connect" else f'\n\t({kind} "{text}"\n\t\t(at {fmt(x)} {fmt(y)} '
    i = s.index(head) + 1
    return i, s.index("\n\t)\n", i) + 4

def cut(a, b):
    global s
    s = s[:a] + s[b:]

def wire_span(p, q):
    for a, c in ((p, q), (q, p)):
        h = f'(xy {fmt(a[0])} {fmt(a[1])}) (xy {fmt(c[0])} {fmt(c[1])})'
        if h in s:
            i = s.rindex("\n\t(wire\n", 0, s.index(h)) + 1
            return i, s.index("\n\t)\n", i) + 4
    raise KeyError((p, q))

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

def no_connect(x, y):
    return f'\t(no_connect\n\t\t(at {fmt(x)} {fmt(y)})\n\t\t(uuid "{U()}")\n\t)\n'

def rename(x, y, old, new):
    global s
    a, b = item("label", x, y, old); blk = s[a:b]
    s = s[:a] + blk.replace(f'(label "{old}"', f'(label "{new}"', 1) + s[b:]

new = ""
R_PIN, R_LAB, L_PIN, L_LAB = 259.08, 261.62, 228.6, 226.06
def free(pin, lab, y, name):
    global new
    cut(*item("label", lab, y, name)); cut(*wire_span((pin, y), (lab, y))); new += no_connect(pin, y)
def take(pin, lab, y, name, ang):
    global new
    cut(*item("no_connect", pin, y)); new += wire((pin, y), (lab, y)) + label(name, lab, y, ang)

# ---------------------------------------------------------------- U4 pins (two passes via '@' names: no transient clashes)
rename(L_LAB, 111.76, "I2C_SCL", "@SIM_DET")             # PB6
rename(L_LAB, 114.3, "I2C_SDA", "@FG_SDA")               # PB7
rename(L_LAB, 109.22, "SIM_DET", "@LED_USER")            # PB5
rename(L_LAB, 119.38, "MCU_MDM_PWR_EN", "@BAT_ALRT")     # PB9
free(L_PIN, L_LAB, 106.68, "LED_USER")                   # PB4 -> free
free(R_PIN, R_LAB, 83.82, "BAT_ALRT")                    # PA8 -> free
take(L_PIN, L_LAB, 116.84, "@FG_SCL", 180)               # PB8
take(L_PIN, L_LAB, 104.14, "@MCU_MDM_PWR_EN", 180)       # PB3
take(R_PIN, R_LAB, 114.3, "@I2C_SCL", 0)                 # PB13
take(R_PIN, R_LAB, 116.84, "@I2C_SDA", 0)                # PB14
# ---------------------------------------------------------------- U8 joins the new bus
rename(39.37, 393.7, "I2C_SCL", "@FG_SCL")
rename(39.37, 391.16, "I2C_SDA", "@FG_SDA")

# ---------------------------------------------------------------- R41/R42: FG_SCL/FG_SDA pull-ups, copies of R12/R13
def clone(src_ref, ref, x, y):
    a, b = inst_block(src_ref); blk = s[a:b]
    X0, Y0 = map(float, re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+) 0\)', blk).groups())
    blk = re.sub(r'\(at ([-\d.]+) ([-\d.]+)( [-\d.]+)?\)',
                 lambda m: f'(at {fmt(float(m.group(1)) - X0 + x)} {fmt(float(m.group(2)) - Y0 + y)}{m.group(3) or ""})', blk)
    blk = re.sub(r'\(uuid "[^"]+"\)', lambda m: f'(uuid "{U()}")', blk)
    return blk.replace(f'"{src_ref}"', f'"{ref}"')
pwr_n = [sorted(int(n) for n in re.findall(r'"#PWR(\d+)"', s))[-1]]
def first_ref(lib_id):
    for m in re.finditer(r'\n\t\(symbol\n\t\t\(lib_id "%s"\)\n\t\t\(at [-\d.]+ [-\d.]+ 0\)' % re.escape(lib_id), s):
        return re.search(r'\(property "Reference" "([^"]+)"', s[m.start():]).group(1)
def power(src_ref, x, y):
    a, b = inst_block(src_ref); g = s[a:b]
    X0, Y0 = map(float, re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+) 0\)', g).groups())
    g = re.sub(r'\(at ([-\d.]+) ([-\d.]+)( [-\d.]+)?\)',
               lambda m: f'(at {fmt(float(m.group(1)) - X0 + x)} {fmt(float(m.group(2)) - Y0 + y)}{m.group(3) or ""})', g)
    pwr_n[0] += 1
    return re.sub(r'\(uuid "[^"]+"\)', lambda m: f'(uuid "{U()}")', g).replace(f'"{src_ref}"', f'"#PWR{pwr_n[0]:03d}"')
P3V3 = first_ref("lte_board:+3V3")
Y = 360.68
for ref, src, x, net in (("R41", "R12", 330.2, "FG_SCL"), ("R42", "R13", 345.44, "FG_SDA")):
    new += clone(src, ref, x, Y)                                        # vertical: pin 1 top (+3V3), pin 2 bottom
    new += wire((x, Y - 3.81), (x, Y - 6.35)); new += power(P3V3, x, Y - 6.35)
    new += wire((x, Y + 3.81), (x, Y + 6.35)) + label(net, x, Y + 6.35, 0)

s = re.sub(r'\(label "@', '(label "', s)
i = s.index("\n\t(sheet_instances") if "\n\t(sheet_instances" in s else s.rindex("\n)")
s = s[:i + 1] + new + s[i + 1:]
s = re.sub(r'\(label "@', '(label "', s)
open(SCH, "w").write(s)
print("schematic rev 0.8 edits applied")
