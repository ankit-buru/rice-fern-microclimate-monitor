"""Schematic rev 0.9: J4 grows from the 1x5 debug header to a 2x5 (2.54 mm, DNP) with the four pins freed when
MDM_PWR_EN moved to PC13 and LED_USER to PA8: PA15, PB3, PB4, PB5 (SPI1 NSS/SCK/MISO/MOSI on AF0; also USART5
TX/RX on PB3/PB4, TIM2_CH1/CH2 on PA15/PB3, LPTIM1_IN1 on PB5) plus a second GND.
The 2x5 odd pins sit where the 1x5 pins were (symbol and footprint), so the debug pins keep their wiring:
  J4 pin  1 GND      2 EXP_PA15
          3 DBG_RX   4 EXP_PB3
          5 DBG_TX   6 EXP_PB4
          7 +3V3     8 EXP_PB5
          9 BOOT0   10 GND
usage: sch_rev09.py lte_board.kicad_sch"""
import re, sys, uuid
SCH = sys.argv[1]
s = open(SCH).read()
U = lambda: str(uuid.uuid4())
def fmt(v): return ("%.4f" % v).rstrip("0").rstrip(".")
assert '"lte_board:Conn_1x05"' in s and "EXP_PB3" not in s, "already applied"

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

def stock(name, new):
    """a KiCad stock connector symbol, renamed into the lte_board library"""
    std = open("/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/Connector_Generic.kicad_sym").read()
    i = std.index(f'(symbol "{name}"'); d = 0
    for k in range(i, len(std)):
        d += {"(": 1, ")": -1}.get(std[k], 0)
        if d == 0: break
    return std[i:k + 1].replace(f'(symbol "{name}"', f'(symbol "lte_board:{new}"', 1).replace(f'"{name}_', f'"{new}_')

new = ""
# ---------------------------------------------------------------- U4: PB3/PB4/PB5 (left side), PA15 (right side) -> labels
L_PIN, L_LAB, R_PIN, R_LAB = 228.6, 226.06, 259.08, 261.62
for (pin, lab, y, name, ang) in ((L_PIN, L_LAB, 104.14, "EXP_PB3", 180), (L_PIN, L_LAB, 106.68, "EXP_PB4", 180),
                                 (L_PIN, L_LAB, 109.22, "EXP_PB5", 180), (R_PIN, R_LAB, 101.6, "EXP_PA15", 0)):
    for x in (pin, lab):                                   # no-connect flag at the pin end or at the end of a stub
        h = f'\n\t(no_connect\n\t\t(at {fmt(x)} {fmt(y)})'
        if h in s:
            a, b = span(h); s = s[:a] + s[b:]
    if f'(xy {fmt(pin)} {fmt(y)}) (xy {fmt(lab)} {fmt(y)})' not in s and f'(xy {fmt(lab)} {fmt(y)}) (xy {fmt(pin)} {fmt(y)})' not in s:
        new += wire((pin, y), (lab, y))
    new += label(name, lab, y, ang)

# ---------------------------------------------------------------- lib symbol + J4 instance: 1x05 -> 2x05 (odd pins in place)
sym = stock("Conn_02x05_Odd_Even", "Conn_2x05")
L = s.index("\n\t(lib_symbols\n") + len("\n\t(lib_symbols\n")
s = s[:L] + "\t\t" + sym.replace("\n", "\n\t") + "\n" + s[L:]
a, b = inst_block("J4"); blk = s[a:b]
JX, JY = map(float, re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+) 0\)', blk).groups())
blk = blk.replace('(lib_id "lte_board:Conn_1x05")', '(lib_id "lte_board:Conn_2x05")')
blk = blk.replace('"DEBUG_UART"', '"DEBUG_EXP"').replace("PinHeader_1x05_P2.54mm_Vertical", "PinHeader_2x05_P2.54mm_Vertical")
old = {str(k): str(2 * k - 1) for k in range(1, 6)}            # 1x05 pin k is now 2x05 pin 2k-1
blk = re.sub(r'\(pin "(\d)"\n', lambda m: f'(pin "{old[m.group(1)]}"\n', blk)
last = blk.rindex('\t\t(pin "')
last = blk.index("\t\t)\n", last) + 4
blk = blk[:last] + "".join(f'\t\t(pin "{n}"\n\t\t\t(uuid "{U()}")\n\t\t)\n' for n in (2, 4, 6, 8, 10)) + blk[last:]
s = s[:a] + blk + s[b:]

# even pins (right, x = JX + 7.62): 2 PA15, 4 PB3, 6 PB4, 8 PB5, 10 GND
pwr_n = [sorted(int(n) for n in re.findall(r'"#PWR(\d+)"', s))[-1]]
def power(lib_id, x, y):
    m = re.search(r'\n\t\(symbol\n\t\t\(lib_id "%s"\)\n\t\t\(at ([-\d.]+) ([-\d.]+) 0\)' % re.escape(lib_id), s)
    ref = re.search(r'\(property "Reference" "([^"]+)"', s[m.start():]).group(1)
    a, b = inst_block(ref); g = s[a:b]
    gx, gy = map(float, m.groups())
    pwr_n[0] += 1
    g = re.sub(r'\(at ([-\d.]+) ([-\d.]+)( [-\d.]+)?\)',
               lambda m: f'(at {fmt(float(m.group(1)) - gx + x)} {fmt(float(m.group(2)) - gy + y)}{m.group(3) or ""})', g)
    g = re.sub(r'\(uuid "[^"]+"\)', lambda m: f'(uuid "{U()}")', g)
    return g.replace(f'"{ref}"', f'"#PWR{pwr_n[0]:03d}"')
xe = JX + 7.62
for dy, name in ((-5.08, "EXP_PA15"), (-2.54, "EXP_PB3"), (0, "EXP_PB4"), (2.54, "EXP_PB5")):
    new += wire((xe, JY + dy), (xe + 2.54, JY + dy)) + label(name, xe + 2.54, JY + dy, 0)
new += wire((xe, JY + 5.08), (xe + 2.54, JY + 5.08)) + power("lte_board:GND", xe + 2.54, JY + 5.08)

i = s.index("\n\t(sheet_instances") if "\n\t(sheet_instances" in s else s.rindex("\n)")
s = s[:i + 1] + new + s[i + 1:]
open(SCH, "w").write(s)
print("schematic rev 0.9 edits applied")
