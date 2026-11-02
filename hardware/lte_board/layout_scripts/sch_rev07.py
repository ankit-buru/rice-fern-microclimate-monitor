"""Schematic rev 0.7 (routing simplification): drop the expansion header, re-pin the modem lines for the 180-degree MCU.
  J5   expansion header removed (EXP_PA4-7, PB8-11 freed)
  U4   modem GPIOs moved so the MCU pins run in the modem's pin order after U4 is rotated 180 degrees:
       STATUS PB12 -> PA4, DCD PB15 -> PA5 (one B.Cu hop), DTR PB13 -> PH1, RI PB14 -> PH0 (EXTI0),
       GNSS_ANT_EN PA15 -> PB0, GNSS_ANT_FLT PB3 -> PB1, MDM_PWRKEY_CTRL PB0 -> PA7, MDM_PWR_EN PB1 -> PB9; USART2 (PA0-PA3) unchanged
  U5   channels reordered to the modem's pin order: ch8 STATUS, ch7 TXD, ch6 RXD, ch5 RTS, ch4 CTS, ch3 DCD,
       ch2 DTR, ch1 RI (A8 top ... A1 bottom faces modem pins 42, 1-7)
Works on the KiCad 9 file format (tab-indented).  usage: sch_rev07.py lte_board.kicad_sch"""
import re, sys, uuid
SCH = sys.argv[1]
s = open(SCH).read()
U = lambda: str(uuid.uuid4())
def fmt(v): return ("%.4f" % v).rstrip("0").rstrip(".")
assert '"Reference" "J5"' in s, "already applied"

def inst_block(ref):
    """the top-level (symbol ...) block whose Reference is ref"""
    i = s.index(f'(property "Reference" "{ref}"')
    a = s.rindex("\n\t(symbol\n", 0, i) + 1
    b = s.index("\n\t)\n", i) + 4
    return a, b

def cut(a, b):
    global s
    s = s[:a] + s[b:]

def item(kind, x, y, text=None):
    """span of the top-level (wire|label|no_connect) whose first point is (x, y)"""
    head = f'\n\t({kind} "{text}"\n\t\t(at {fmt(x)} {fmt(y)} ' if text else None
    if kind == "no_connect": head = f'\n\t(no_connect\n\t\t(at {fmt(x)} {fmt(y)})'
    i = s.index(head) + 1
    return i, s.index("\n\t)\n", i) + 4

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
# ---------------------------------------------------------------- 1. J5: symbol, its two power symbols, stubs, labels
for ref in ("J5", "#PWR064", "#PWR065"):
    cut(*inst_block(ref))
for y, name in ((288.29, None), (290.83, None), (293.37, "EXP_PB8"), (295.91, "EXP_PB9"), (298.45, "EXP_PA4"),
                (300.99, "EXP_PA5"), (303.53, "EXP_PA6"), (306.07, "EXP_PA7"), (308.61, "EXP_PB10"), (311.15, "EXP_PB11")):
    cut(*wire_span((88.9, y), (86.36, y)))
    if name: cut(*item("label", 86.36, y, name))

# ---------------------------------------------------------------- 2. U4 pins (stub from the pin end to the label)
R_PIN, R_LAB, L_PIN, L_LAB = 259.08, 261.62, 228.6, 226.06
def free(side, y, name):            # label + stub -> no-connect flag at the pin end
    global new
    pin, lab = (R_PIN, R_LAB) if side == "R" else (L_PIN, L_LAB)
    cut(*item("label", lab, y, name)); cut(*wire_span((pin, y), (lab, y))); new += no_connect(pin, y)
def take(y, name):                  # left-side no-connect pin -> stub + label
    global new
    cut(*item("no_connect", L_PIN, y)); new += wire((L_PIN, y), (L_LAB, y)) + label(name, L_LAB, y, 180)
rename(R_LAB, 73.66, "EXP_PA4", "MCU_MDM_STATUS")      # PA4
rename(R_LAB, 76.2, "EXP_PA5", "MCU_MDM_DCD")          # PA5
rename(R_LAB, 81.28, "EXP_PA7", "MDM_PWRKEY_CTRL")     # PA7
rename(L_LAB, 96.52, "MDM_PWRKEY_CTRL", "GNSS_ANT_EN")  # PB0
rename(L_LAB, 99.06, "MCU_MDM_PWR_EN", "GNSS_ANT_FLT")  # PB1
rename(L_LAB, 119.38, "EXP_PB9", "MCU_MDM_PWR_EN")     # PB9
for y, name in ((78.74, "EXP_PA6"), (101.6, "GNSS_ANT_EN"), (106.68, "EXP_PB10"), (109.22, "EXP_PB11"), (111.76, "MCU_MDM_STATUS"),
                (114.3, "MCU_MDM_DTR"), (116.84, "MCU_MDM_RI"), (119.38, "MCU_MDM_DCD")):
    free("R", y, name)                                   # PA6, PA15, PB10, PB11, PB12, PB13, PB14, PB15
for y, name in ((104.14, "GNSS_ANT_FLT"), (116.84, "EXP_PB8")):
    free("L", y, name)                                   # PB3, PB8
take(91.44, "MCU_MDM_DTR")                               # PH1
take(88.9, "MCU_MDM_RI")                                 # PH0

# ---------------------------------------------------------------- 3. U5 channel order (A side x 342.9, B side x 368.3)
old_a = ["MDM_RXD", "MDM_TXD", "MDM_RTS", "MDM_CTS", "MDM_DTR", "MDM_RI", "MDM_STATUS", "MDM_DCD"]
new_a = ["MDM_RI", "MDM_DTR", "MDM_DCD", "MDM_CTS", "MDM_RTS", "MDM_RXD", "MDM_TXD", "MDM_STATUS"]
pair = {"MDM_RXD": "MCU_MDM_TXD", "MDM_TXD": "MCU_MDM_RXD"}
for k in range(8):
    y = 78.74 + 2.54 * k
    rename(342.9, y, old_a[k], f"@{new_a[k]}")           # two passes: no transient duplicate names
    rename(368.3, y, pair.get(old_a[k], "MCU_" + old_a[k]), "@" + pair.get(new_a[k], "MCU_" + new_a[k]))
s = re.sub(r'\(label "@', '(label "', s)

i = s.index("\n\t(sheet_instances") if "\n\t(sheet_instances" in s else s.rindex("\n)")
s = s[:i + 1] + new + s[i + 1:]
open(SCH, "w").write(s)
print("schematic rev 0.7 edits applied")
