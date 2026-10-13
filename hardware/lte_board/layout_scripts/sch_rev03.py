"""Schematic rev 0.3: Li-ion input (JST PH, reverse-polarity FET, DW01A/FS8205A protector), MAX17048 fuel gauge,
USB/battery OR-ing into VSYS (Schottky + P-FET), D1 on USB only, R24 -> 1M, non-parts excluded from the BOM."""
import re, sys, uuid
f = sys.argv[1]; s = open(f).read()
ROOT = "/7ded1cb8-0547-516d-a7f6-d4c083a7d11d"
U = lambda: str(uuid.uuid4())
def fmt(v): return ("%.2f" % v).rstrip("0").rstrip(".")
def sub1(a, b):
    global s
    assert s.count(a) == 1, f"{s.count(a)} matches: {a[:80]}"
    s = s.replace(a, b)

# ---------------------------------------------------------------- helpers to find symbol instances / pins
def inst_block(ref):
    i = s.index(f'(property "Reference" "{ref}"')
    a = s.rindex("\n(symbol (lib_id", 0, i) + 1
    b = s.index("\n  )\n", i) + 4
    return a, b
def inst_head(ref):
    a, b = inst_block(ref)
    m = re.match(r'\(symbol \(lib_id "([^"]+)"\) \(at ([-\d.]+) ([-\d.]+) (\d+)\)', s[a:b])
    return m.group(1), float(m.group(2)), float(m.group(3)), int(m.group(4))
def lib_pins(lib_id):
    i = s.index(f'  (symbol "{lib_id}"'); j = s.index('\n  (symbol "lte_board:', i + 10) if '\n  (symbol "lte_board:' in s[i + 10:] else len(s)
    out = {}
    for m in re.finditer(r'\(pin \w+ line \(at ([-\d.]+) ([-\d.]+) (\d+)\).*?\(number "([^"]+)"', s[i:j]):
        out.setdefault(m.group(4), (float(m.group(1)), float(m.group(2))))
    return out
def pin_xy(ref, num):
    lib, X, Y, rot = inst_head(ref); assert rot == 0, ref
    px, py = lib_pins(lib)[num]
    return round(X + px, 2), round(Y - py, 2)
def far_end(x, y):
    """other end of the stub wire starting at (x, y)"""
    m = re.search(r'\(wire \(pts \(xy %s %s\) \(xy ([-\d.]+) ([-\d.]+)\)\)' % (re.escape(fmt(x)), re.escape(fmt(y))), s)
    if m: return float(m.group(1)), float(m.group(2))
    m = re.search(r'\(wire \(pts \(xy ([-\d.]+) ([-\d.]+)\) \(xy %s %s\)\)' % (re.escape(fmt(x)), re.escape(fmt(y))), s)
    assert m, f"no wire at {x},{y}"; return float(m.group(1)), float(m.group(2))
def power_at(x, y, lib):
    m = re.search(r'\n\(symbol \(lib_id "lte_board:%s"\) \(at %s %s \d+\)' % (re.escape(lib), re.escape(fmt(x)), re.escape(fmt(y))), s)
    assert m, f"no {lib} symbol at {x},{y}"
    a = m.start() + 1; b = s.index("\n  )\n", a) + 4
    return a, b
def repower(ref, num, old, new_label=None, new_power=None):
    """swap the power symbol on a pin stub for a net label or another power symbol"""
    global s
    x, y = far_end(*pin_xy(ref, num)); a, b = power_at(x, y, old)
    if new_label:
        rep = f'(label "{new_label}" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid {U()}))\n'
    else:
        blk = s[a:b]
        rep = blk.replace(f'(lib_id "lte_board:{old}")', f'(lib_id "lte_board:{new_power}")').replace(f'(property "Value" "{old}"', f'(property "Value" "{new_power}"')
    s = s[:a] + rep + s[b:]
def set_prop(ref, key, val):
    global s
    a, b = inst_block(ref); blk = s[a:b]
    blk2, n = re.subn(r'\(property "%s" "[^"]*"' % key, f'(property "{key}" "{val}"', blk)
    assert n == 1, (ref, key); s = s[:a] + blk2 + s[b:]
def exclude_bom(ref):
    global s
    a, b = inst_block(ref); blk = s[a:b]
    s = s[:a] + blk.replace("(in_bom yes)", "(in_bom no)", 1) + s[b:]

# ---------------------------------------------------------------- 1. non-parts out of the BOM (copper-only / DNP)
for r in ("JP1", "JP2", "JP3", "JP4", "JP5", "TP1", "TP2", "TP3", "TP4", "C40", "C41", "J4", "J5"):
    exclude_bom(r)
# ---------------------------------------------------------------- 2. always-on loads
set_prop("R24", "Value", "1M"); set_prop("R24", "LCSC", "C26083"); set_prop("R24", "MPN", "0402WGF1004TCE")
repower("R9", "1", "+3V3", new_power="+5V")             # D1 lights only with USB attached
# ---------------------------------------------------------------- 3. buck + LDO now run from VSYS
repower("U2", "4", "+5V", new_label="VSYS")
repower("C1", "1", "+5V", new_label="VSYS")
repower("U3", "1", "+5V", new_label="VSYS")
repower("U3", "3", "+5V", new_label="VSYS")
repower("C4", "1", "+5V", new_label="VSYS")

# ---------------------------------------------------------------- 4. new library symbols
def box(name, desc, left, right, w=7.62):
    """rectangular symbol; left/right = [(num, name, type)], 2.54 mm pitch from the top"""
    n = max(len(left), len(right)); h = 2.54 * (n + 1)
    pins = []
    for side, lst in (("L", left), ("R", right)):
        for k, (num, nm, typ) in enumerate(lst):
            y = h / 2 - 2.54 * (k + 1)
            x, ang = (-w - 2.54, 0) if side == "L" else (w + 2.54, 180)
            pins.append(f'(pin {typ} line (at {fmt(x)} {fmt(y)} {ang}) (length 2.54) (name "{nm}" (effects (font (size 1.27 1.27)))) (number "{num}" (effects (font (size 1.27 1.27)))))')
    return f'''  (symbol "lte_board:{name}"
  (pin_names (offset 1.016))
  (exclude_from_sim no) (in_bom yes) (on_board yes)
  (property "Reference" "U" (at {fmt(-w)} {fmt(h / 2 + 1.27)} 0) (effects (font (size 1.27 1.27)) (justify left)))
  (property "Value" "{name}" (at {fmt(-w)} {fmt(-h / 2 - 1.27)} 0) (effects (font (size 1.27 1.27)) (justify left)))
  (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
  (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
  (property "Description" "{desc}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
  (symbol "{name}_0_1" (rectangle (start {fmt(-w)} {fmt(h / 2)}) (end {fmt(w)} {fmt(-h / 2)}) (stroke (width 0.254) (type default)) (fill (type background))))
  (symbol "{name}_1_1" {" ".join(pins)})
  )
'''
NEWSYMS = [
    box("Conn_Battery", "2-pin battery connector, pin 1 = +", [("1", "+", "passive"), ("2", "-", "passive")], [], w=3.81),
    box("Q_PMOS_GSD", "P-channel MOSFET, SOT-23 G=1 S=2 D=3", [("1", "G", "input")], [("2", "S", "passive"), ("3", "D", "passive")], w=3.81),
    box("D_Schottky", "Schottky diode, pin 1 = K", [("2", "A", "passive")], [("1", "K", "passive")], w=3.81),
    box("DW01A", "1-cell Li-ion protection IC (SOT-23-6)", [("5", "VCC", "passive"), ("6", "GND", "passive"), ("2", "VM", "input"), ("4", "TD", "passive")], [("1", "OD", "output"), ("3", "OC", "output")]),
    box("FS8205A", "dual N-MOSFET, common drain (SOT-23-6)", [("1", "S1", "passive"), ("6", "G1", "input"), ("2", "D", "passive")], [("3", "S2", "passive"), ("4", "G2", "input"), ("5", "D", "passive")]),
    box("MAX17048", "1-cell ModelGauge fuel gauge, I2C 0x36 (TDFN-8 2x2)", [("3", "VDD", "passive"), ("2", "CELL", "input"), ("1", "CTG", "passive"), ("6", "QSTRT", "input"), ("4", "GND", "passive"), ("9", "EP", "passive")], [("8", "SDA", "bidirectional"), ("7", "SCL", "input"), ("5", "~{ALRT}", "open_collector")]),
]
anchor = '  (symbol "lte_board:TXS0108EPW"'
s = s.replace(anchor, "".join(NEWSYMS) + anchor, 1)
LIBDEF = {m.group(1): m for m in []}

# ---------------------------------------------------------------- 5. U4 PA8 -> fuel gauge alert
NEW = []
lib, X, Y, rot = inst_head("U4"); px, py = lib_pins(lib)["29"]
x, y = round(X + px, 2), round(Y - py, 2)
nc = "(no_connect (at %s %s)" % (fmt(x), fmt(y)); i = s.index(nc); j = s.index("\n", i); s = s[:i] + s[j + 1:]
NEW.append(f'(wire (pts (xy {fmt(x)} {fmt(y)}) (xy {fmt(x + 2.54)} {fmt(y)})) (stroke (width 0) (type default)) (uuid {U()}))')
NEW.append(f'(label "BAT_ALRT" (at {fmt(x + 2.54)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid {U()}))')

# ---------------------------------------------------------------- 6. new parts
pwr = max(int(n) for n in re.findall(r'#PWR(\d+)', s))
def power(lib, x, y):
    global pwr; pwr += 1; r = f"#PWR{pwr:03d}"
    return f'''(symbol (lib_id "lte_board:{lib}") (at {fmt(x)} {fmt(y)} 0) (unit 1)
  (exclude_from_sim no) (in_bom no) (on_board yes) (dnp no)
  (uuid {U()})
  (property "Reference" "{r}" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) hide))
  (property "Value" "{lib}" (at {fmt(x)} {fmt(y + (2.54 if lib == "GND" else -2.54))} 0) (effects (font (size 1.27 1.27))))
  (property "Footprint" "" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) hide))
  (property "Datasheet" "" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) hide))
  (property "Description" "" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) hide))
  (pin "1" (uuid {U()}))
  (instances (project "lte_board" (path "{ROOT}" (reference "{r}") (unit 1))))
  )'''
def libpins_src(lib_id):
    i = s.index(f'  (symbol "lte_board:{lib_id}"'); j = s.index("\n  )\n", i)
    return {m.group(4): (float(m.group(1)), float(m.group(2)), int(m.group(3)))
            for m in re.finditer(r'\(pin \w+ line \(at ([-\d.]+) ([-\d.]+) (\d+)\).*?\(number "([^"]+)"', s[i:j])}
def part(lib, ref, val, fp, x, y, nets, lcsc=None, mpn=None, in_bom=True):
    props = [f'  (property "Reference" "{ref}" (at {fmt(x)} {fmt(y - 8.89)} 0) (effects (font (size 1.27 1.27)) (justify left)))',
             f'  (property "Value" "{val}" (at {fmt(x)} {fmt(y + 8.89)} 0) (effects (font (size 1.27 1.27)) (justify left)))',
             f'  (property "Footprint" "{fp}" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) hide))',
             f'  (property "Datasheet" "" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) hide))',
             f'  (property "Description" "" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) hide))']
    if lcsc: props.append(f'  (property "LCSC" "{lcsc}" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) hide))')
    if mpn: props.append(f'  (property "MPN" "{mpn}" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) hide))')
    pins = libpins_src(lib)
    NEW.append(f'''(symbol (lib_id "lte_board:{lib}") (at {fmt(x)} {fmt(y)} 0) (unit 1)
  (exclude_from_sim no) (in_bom {"yes" if in_bom else "no"}) (on_board yes) (dnp no)
  (uuid {U()})
{chr(10).join(props)}
{chr(10).join(f'  (pin "{n}" (uuid {U()}))' for n in pins)}
  (instances (project "lte_board" (path "{ROOT}" (reference "{ref}") (unit 1))))
  )''')
    for num, (px, py, ang) in pins.items():
        net = nets.get(num)
        sx, sy = x + px, y - py
        if net is None:
            NEW.append(f'(no_connect (at {fmt(sx)} {fmt(sy)}) (uuid {U()}))'); continue
        if lib in ("R", "C", "SW_Push", "SolderJumper"):      # vertical 2-pin parts: stub up/down
            ex, ey = sx, sy + (-2.54 if py > 0 else 2.54)
        else:
            ex, ey = sx + (-2.54 if ang == 0 else 2.54), sy
        NEW.append(f'(wire (pts (xy {fmt(sx)} {fmt(sy)}) (xy {fmt(ex)} {fmt(ey)})) (stroke (width 0) (type default)) (uuid {U()}))')
        if net in ("+3V3", "GND", "+5V"):
            NEW.append(power(net, ex, ey))
        else:
            NEW.append(f'(label "{net}" (at {fmt(ex)} {fmt(ey)} 0) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid {U()}))')

R0402, C0402, C0603 = "Resistor_SMD:R_0402_1005Metric", "Capacitor_SMD:C_0402_1005Metric", "Capacitor_SMD:C_0603_1608Metric"
SOT23, SOT236 = "Package_TO_SOT_SMD:SOT-23", "Package_TO_SOT_SMD:SOT-23-6"
Y0, Y1 = 386.08, 406.4
# battery input: J9 -> Q3 (reverse polarity) -> VBAT; protector in the negative lead (BATT_N -> FS8205A -> GND)
part("Conn_Battery", "J9", "BATTERY", "Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical", 25.4, Y0, {"1": "BATT_IN", "2": "BATT_N"}, "C5251182", "B2B-PH-K-S-GW")
part("Q_PMOS_GSD", "Q3", "AO3401A", SOT23, 63.5, Y0, {"1": "RP_G", "2": "VBAT", "3": "BATT_IN"}, "C15127", "AO3401A")
part("R", "R33", "100k", R0402, 83.82, Y0, {"1": "RP_G", "2": "GND"}, "C25741", "0402WGF1003TCE")
part("DW01A", "U9", "DW01A", SOT236, 116.84, Y0, {"5": "DW_VCC", "6": "BATT_N", "2": "DW_VM", "4": None, "1": "DW_OD", "3": "DW_OC"}, "C351410", "DW01A")
part("R", "R35", "100R", R0402, 142.24, Y0, {"1": "VBAT", "2": "DW_VCC"}, "C25076", "0402WGF1000TCE")
part("C", "C43", "100nF", C0402, 154.94, Y0, {"1": "DW_VCC", "2": "BATT_N"}, "C1525", "CL05B104KO5NNNC")
part("R", "R36", "1k", R0402, 167.64, Y0, {"1": "DW_VM", "2": "GND"}, "C11702", "0402WGF1001TCE")
part("FS8205A", "Q5", "FS8205A", SOT236, 198.12, Y0, {"1": "BATT_N", "6": "DW_OD", "2": "DW_D", "3": "GND", "4": "DW_OC", "5": "DW_D"}, "C908265", "FS8205A")
part("C", "C45", "10uF", C0603, 223.52, Y0, {"1": "VBAT", "2": "GND"}, "C19702", "CL10A106KP8NNNC")
# fuel gauge on VBAT, I2C shared with Qwiic, alert to PA8
part("MAX17048", "U8", "MAX17048G+T10", "lte_board_lcsc:MAX17048_TDFN-8_2x2mm", 25.4, Y1, {"3": "VBAT", "2": "VBAT", "1": "GND", "6": "GND", "4": "GND", "9": "GND", "8": "I2C_SDA", "7": "I2C_SCL", "5": "BAT_ALRT"}, "C2682616", "MAX17048G+T10")
part("C", "C44", "1uF", C0402, 63.5, Y1, {"1": "VBAT", "2": "GND"}, "C52923", "CL05A105KA5NQNC")
part("R", "R37", "100k", R0402, 76.2, Y1, {"1": "+3V3", "2": "BAT_ALRT"}, "C25741", "0402WGF1003TCE")
# USB / battery OR-ing into VSYS
part("D_Schottky", "D4", "B5819W", "Diode_SMD:D_SOD-123", 116.84, Y1, {"2": "+5V", "1": "VSYS"}, "C8598", "B5819W SL")
part("Q_PMOS_GSD", "Q4", "AO3401A", SOT23, 154.94, Y1, {"1": "+5V", "2": "VSYS", "3": "VBAT"}, "C15127", "AO3401A")
part("R", "R34", "100k", R0402, 177.8, Y1, {"1": "+5V", "2": "GND"}, "C25741", "0402WGF1003TCE")
# power flags: VSYS and VBAT are fed through a diode / FETs
flg = 3
for net, fx in (("VSYS", 200.66), ("VBAT", 215.9)):
    flg += 1
    NEW.append(f'''(symbol (lib_id "lte_board:PWR_FLAG") (at {fmt(fx)} {fmt(Y1)} 0) (unit 1)
  (exclude_from_sim no) (in_bom no) (on_board yes) (dnp no)
  (uuid {U()})
  (property "Reference" "#FLG{flg:02d}" (at {fmt(fx)} {fmt(Y1)} 0) (effects (font (size 1.27 1.27)) hide))
  (property "Value" "PWR_FLAG" (at {fmt(fx)} {fmt(Y1 - 2.54)} 0) (effects (font (size 1.27 1.27))))
  (property "Footprint" "" (at {fmt(fx)} {fmt(Y1)} 0) (effects (font (size 1.27 1.27)) hide))
  (property "Datasheet" "" (at {fmt(fx)} {fmt(Y1)} 0) (effects (font (size 1.27 1.27)) hide))
  (property "Description" "" (at {fmt(fx)} {fmt(Y1)} 0) (effects (font (size 1.27 1.27)) hide))
  (pin "1" (uuid {U()}))
  (instances (project "lte_board" (path "{ROOT}" (reference "#FLG{flg:02d}") (unit 1))))
  )''')
    NEW.append(f'(wire (pts (xy {fmt(fx)} {fmt(Y1)}) (xy {fmt(fx)} {fmt(Y1 + 2.54)})) (stroke (width 0) (type default)) (uuid {U()}))')
    NEW.append(f'(label "{net}" (at {fmt(fx)} {fmt(Y1 + 2.54)} 0) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid {U()}))')
NEW.append(f'(text "Rev 0.3 battery input: J9 (JST PH, pin 1 = +) -> Q3 reverse-polarity P-FET -> VBAT. U9 DW01A + Q5 FS8205A protect in the negative lead (BATT_N -> GND). U8 MAX17048 fuel gauge (I2C 0x36, ALRT -> PA8). VSYS = USB via D4 Schottky, or VBAT via Q4 (off while USB present). VSYS feeds the modem buck and the 3.3V LDO." (exclude_from_sim no) (at 10.16 373.38 0) (effects (font (size 2 2)) (justify left bottom)) (uuid {U()}))')

i = s.index('\n(text "Power:')
s = s[:i] + "\n" + "\n".join(NEW) + s[i:]
s = s.replace('(rev "0.2")', '(rev "0.3")')
open(f, "w").write(s)
print("rev 0.3 items added:", len(NEW), "last #PWR", pwr)
