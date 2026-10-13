"""Schematic rev 0.2 edits: STM32L072 + USB select jumpers + modem power override + BOOT0 button + UART pulls + low-Iq LDO."""
import re, sys, uuid
f = sys.argv[1]; s = open(f).read()
ROOT = "/7ded1cb8-0547-516d-a7f6-d4c083a7d11d"
U = lambda: str(uuid.uuid4())
def sub1(a, b, count=1):
    global s
    n = s.count(a)
    assert n >= 1, f"not found: {a[:70]}"
    if count == 1: assert n == 1, f"{n} matches: {a[:70]}"
    s = s.replace(a, b)

# ---- 1. MCU: STM32L071 -> STM32L072 (only LQFP-48 difference: pin 36 VDDIO2 -> VDD_USB)
s = s.replace("STM32L071CBTx", "STM32L072CBTx")
sub1('(name "VDDIO2"', '(name "VDD_USB"')
s = s.replace("STM32L071CBT6 Cortex-M0+ ultra-low-power MCU, 128K flash, LQFP-48", "STM32L072CBT6 Cortex-M0+ ultra-low-power MCU with crystal-less USB FS, 128K flash, LQFP-48")
s = s.replace("STM32L071CBT6", "STM32L072CBT6").replace("STM32L071", "STM32L072")
sub1('(property "LCSC" "C79758"', '(property "LCSC" "C465977"')

# ---- 2. 3.3V LDO: ME6211 (40 uA Iq) -> TPS7A0233PDBVR (25 nA Iq), same SOT-23-5 pinout
s = s.replace('(property "Value" "ME6211C33M5G-N"', '(property "Value" "TPS7A0233PDBVR"')
sub1('(property "LCSC" "C82942"', '(property "LCSC" "C2887324"')
s = s.replace('(property "MPN" "ME6211C33M5G-N"', '(property "MPN" "TPS7A0233PDBVR"')

# ---- 3. U4 pin re-assignment (labels sit 2.54 mm out from each pin end)
UX, UY = 243.84, 96.52
pins = {}   # number -> (sheet x, sheet y, side)
lib = s[s.index('(symbol "lte_board:STM32L072CBTx"'):]
lib = lib[:lib.index('\n  (symbol "lte_board:', 10)]
for m in re.finditer(r'\(pin \w+ line \(at ([-\d.]+) ([-\d.]+) (\d+)\).*?\(number "(\d+)"', lib):
    px, py, ang, num = float(m.group(1)), float(m.group(2)), int(m.group(3)), m.group(4)
    pins[num] = (round(UX + px, 2), round(UY - py, 2), "L" if ang == 0 else "R")
def fmt(v): return ("%.2f" % v).rstrip("0").rstrip(".")
def relabel(num, new):
    global s
    x, y, side = pins[num]; lx = x - 2.54 if side == "L" else x + 2.54
    pat = re.compile(r'\(label "([^"]+)" \(at %s %s (?:0|180)\)' % (re.escape(fmt(lx)), re.escape(fmt(y))))
    m = pat.search(s); assert m, f"no label at pin {num} ({lx},{y})"
    s = s[:m.start(1)] + new + s[m.end(1):]
    return m.group(1)
def add_label(num, name):
    global s
    x, y, side = pins[num]
    nc = "(no_connect (at %s %s)" % (fmt(x), fmt(y))
    i = s.index(nc); j = s.index("\n", i); s = s[:i] + s[j + 1:]           # drop the no-connect flag
    lx, ang, just = (x - 2.54, 180, "right") if side == "L" else (x + 2.54, 0, "left")
    s += ""  # appended below with the other new items
    NEW.append(f'(wire (pts (xy {fmt(x)} {fmt(y)}) (xy {fmt(lx)} {fmt(y)})) (stroke (width 0) (type default)) (uuid {U()}))')
    NEW.append(f'(label "{name}" (at {fmt(lx)} {fmt(y)} {ang}) (effects (font (size 1.27 1.27)) (justify {just} bottom)) (uuid {U()}))')
NEW = []
changes = {"10": "MCU_MDM_CTS", "11": "MCU_MDM_RTS", "12": "MCU_MDM_TXD", "13": "MCU_MDM_RXD",   # modem on USART2 (+RTS/CTS)
           "30": "DBG_TX", "31": "DBG_RX",                                                      # debug UART on USART1
           "32": "MCU_USB_DN", "33": "MCU_USB_DP",                                              # USB FS
           "19": "MCU_MDM_PWR_EN"}                                                              # via R28 to buck EN
old = {n: relabel(n, v) for n, v in changes.items()}
print("U4 relabel:", {n: f"{old[n]} -> {v}" for n, v in changes.items()})
add_label("45", "EXP_PB8"); add_label("46", "EXP_PB9")
# J5 pins 3/4 follow the spare pins
for a, b in (("EXP_PA0", "EXP_PB8"), ("EXP_PA1", "EXP_PB9")):
    assert s.count(f'(label "{a}"') == 1, a; s = s.replace(f'(label "{a}"', f'(label "{b}"')
# R3/R4 now sit behind the USB select jumpers
sub1('(label "USB_DP" (at 101.6 29.21 0)', '(label "MDM_USBJ_DP" (at 101.6 29.21 0)')
sub1('(label "USB_DN" (at 114.3 29.21 0)', '(label "MDM_USBJ_DN" (at 114.3 29.21 0)')

# ---- 4. 3-pad solder jumper symbol (pin 2 = common)
SJ3 = '''  (symbol "lte_board:SolderJumper3"
  (pin_names (offset 0.508) hide)
  (exclude_from_sim no) (in_bom yes) (on_board yes)
  (property "Reference" "JP" (at 2.54 3.81 0) (effects (font (size 1.27 1.27)) (justify left)))
  (property "Value" "SolderJumper3" (at 2.54 -3.81 0) (effects (font (size 1.27 1.27)) (justify left)))
  (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
  (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
  (property "Description" "3-pad solder jumper, pin 2 common" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
  (symbol "SolderJumper3_0_1" (rectangle (start -1.27 -2.54) (end 1.27 2.54) (stroke (width 0.254) (type default)) (fill (type none))) (polyline (pts (xy -0.635 1.27) (xy 0.635 1.27)) (stroke (width 0.254) (type default)) (fill (type none))) (polyline (pts (xy -0.635 -1.27) (xy 0.635 -1.27)) (stroke (width 0.254) (type default)) (fill (type none))))
  (symbol "SolderJumper3_1_1" (pin passive line (at 0 5.08 270) (length 2.54) (name "A" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27))))) (pin passive line (at 3.81 0 180) (length 2.54) (name "C" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27))))) (pin passive line (at 0 -5.08 90) (length 2.54) (name "B" (effects (font (size 1.27 1.27)))) (number "3" (effects (font (size 1.27 1.27))))))
  )
'''
anchor = '  (symbol "lte_board:TXS0108EPW"'
sub1(anchor, SJ3 + anchor)

# ---- 5. new parts in the rev 0.2 block (bottom band of the sheet)
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
def end(net, x, y, side):
    """wire 2.54 mm away from a pin end, then a label or power symbol"""
    dx, dy = {"up": (0, -2.54), "down": (0, 2.54), "right": (2.54, 0)}[side]
    ex, ey = x + dx, y + dy
    NEW.append(f'(wire (pts (xy {fmt(x)} {fmt(y)}) (xy {fmt(ex)} {fmt(ey)})) (stroke (width 0) (type default)) (uuid {U()}))')
    if net in ("+3V3", "GND", "+5V"):
        NEW.append(power(net, ex, ey))
    else:
        NEW.append(f'(label "{net}" (at {fmt(ex)} {fmt(ey)} 0) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid {U()}))')
def part(lib, ref, val, fp, x, y, nets, lcsc=None, mpn=None):
    props = [f'  (property "Reference" "{ref}" (at {fmt(x + 2.032)} {fmt(y - 1.27)} 0) (effects (font (size 1.27 1.27)) (justify left)))',
             f'  (property "Value" "{val}" (at {fmt(x + 2.032)} {fmt(y + 1.27)} 0) (effects (font (size 1.27 1.27)) (justify left)))',
             f'  (property "Footprint" "{fp}" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) hide))',
             f'  (property "Datasheet" "" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) hide))',
             f'  (property "Description" "" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) hide))']
    if lcsc: props.append(f'  (property "LCSC" "{lcsc}" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) hide))')
    if mpn: props.append(f'  (property "MPN" "{mpn}" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) hide))')
    pinl = "\n".join(f'  (pin "{n}" (uuid {U()}))' for n in nets)
    NEW.append(f'''(symbol (lib_id "lte_board:{lib}") (at {fmt(x)} {fmt(y)} 0) (unit 1)
  (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
  (uuid {U()})
{chr(10).join(props)}
{pinl}
  (instances (project "lte_board" (path "{ROOT}" (reference "{ref}") (unit 1))))
  )''')
    if lib == "SolderJumper3":
        end(nets["1"], x, y - 5.08, "up"); end(nets["2"], x + 3.81, y, "right"); end(nets["3"], x, y + 5.08, "down")
    elif lib == "TestPoint":
        end(nets["1"], x, y, "down")
    else:  # vertical 2-pin: pin 1 top, pin 2 bottom
        end(nets["1"], x, y - 3.81, "up"); end(nets["2"], x, y + 3.81, "down")

Y = 365.76
R0402 = "Resistor_SMD:R_0402_1005Metric"
part("SolderJumper3", "JP3", "USB_SEL_DP", "Jumper:SolderJumper-3_P1.3mm_Bridged12_RoundedPad1.0x1.5mm", 20.32, Y, {"1": "MCU_USB_DP", "2": "USB_DP", "3": "MDM_USBJ_DP"})
part("SolderJumper3", "JP4", "USB_SEL_DN", "Jumper:SolderJumper-3_P1.3mm_Bridged12_RoundedPad1.0x1.5mm", 45.72, Y, {"1": "MCU_USB_DN", "2": "USB_DN", "3": "MDM_USBJ_DN"})
part("SolderJumper", "JP5", "MDM_PWR_FORCE", "Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm", 76.2, Y, {"1": "+3V3", "2": "MDM_PWR_EN"})
part("R", "R28", "1k", R0402, 96.52, Y, {"1": "MCU_MDM_PWR_EN", "2": "MDM_PWR_EN"}, "C11702", "0402WGF1001TCE")
part("TestPoint", "TP4", "GND", "TestPoint:TestPoint_Pad_D1.0mm", 116.84, Y - 3.81, {"1": "GND"})
part("SW_Push", "SW2", "BOOT0", "lte_board_lcsc:SW_TS-1187A", 137.16, Y, {"1": "+3V3", "2": "BOOT0"}, "C318884", "TS-1187A-B-A-B")
part("R", "R29", "100k", R0402, 162.56, Y, {"1": "+3V3", "2": "MCU_MDM_RXD"}, "C25741", "0402WGF1003TCE")
part("R", "R30", "100k", R0402, 177.8, Y, {"1": "+3V3", "2": "MCU_MDM_DCD"}, "C25741", "0402WGF1003TCE")
part("R", "R31", "100k", R0402, 193.04, Y, {"1": "+3V3", "2": "MCU_MDM_CTS"}, "C25741", "0402WGF1003TCE")
part("R", "R32", "100k", R0402, 208.28, Y, {"1": "MCU_MDM_RI", "2": "GND"}, "C25741", "0402WGF1003TCE")
NEW.append(f'(text "Rev 0.2: USB select (JP3/JP4 bridged 1-2 = MCU, 2-3 = modem), JP5 forces modem 3.8V rail on (modem-USB mode; PWRKEY via TP2->TP4), BOOT0 button SW2, 100k pulls (>=47k per SIMCom) on shifter MCU side" (exclude_from_sim no) (at 10.16 345.44 0) (effects (font (size 2 2)) (justify left bottom)) (uuid {U()}))')

i = s.index('\n(text "Power:')
s = s[:i] + "\n" + "\n".join(NEW) + s[i:]
s = s.replace('(rev "0.1")', '(rev "0.2")')
open(f, "w").write(s)
print("added", len(NEW), "items; last power ref #PWR%03d" % pwr)
