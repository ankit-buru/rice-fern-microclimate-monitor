"""Generate lte_board.kicad_pcb from the schematic netlist with a hand-planned placement.

usage: python gen_board.py <netlist.net> <project_dir> <out.kicad_pcb>
"""
import re, sys, os
import pcbnew
from pcbnew import VECTOR2I, FromMM

NETLIST, PROJ, OUT = sys.argv[1:4]
STDLIB = os.environ.get("KICAD9_FOOTPRINT_DIR", "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")
OX, OY = 100.0, 100.0          # board origin (top-left) in sheet mm
W, H = 63.5, 46.0              # board size, mm

def P(x, y):
    return VECTOR2I(FromMM(OX + x), FromMM(OY + y))

# ---------------------------------------------------------------- placement
# ref: (x, y, rot_deg)   coordinates relative to board top-left, y down
PLACE = {
    # --- modem + RF
    "U6": (36.0, 12.3, 0),
    "J6": (48.4, 10.4, 270),  "R19": (46.0, 7.35, 0), "C40": (45.5, 5.8, 90), "C41": (47.6, 5.9, 90),
    "R20": (26.05, 5.0, 180), "J7": (19.3, 0.0, 0),    # J7: SMA edge jack, origin = board edge (see sch_rev05.py)
    # VBAT bulk / HF caps at pins 34/35 (top-right)
    # C30 sits left of the VBAT pins and C31 stands upright, clear of corner hole H2
    "C30": (37.4, 1.2, 180), "C31": (46.6, 1.9, 90), "C32": (44.7, 1.4, 0), "C33": (42.8, 1.4, 0), "C34": (40.9, 1.4, 0),
    # VDD_EXT decoupling
    "C35": (28.0, 1.4, 0), "C20": (30.0, 1.4, 0),
    # --- SIM
    "J8": (36.2, 36.9, 0),   # front face 2.35 mm from the bottom edge: locked card fully over the PCB, ejected card ~1.85 mm out; nothing may sit in front of it
    "R21": (33.8, 23.15, 270), "R22": (34.9, 23.15, 270), "R23": (36.0, 23.15, 270),   # in the modem->SIM gap, under pins 15-17
    # rev 0.6 (audit H10d): SIM ESD/filter parts within ~1-3 mm of the J8 contacts. Caps stand one above each contact
    # (CLK 42.37, DATA 43.64, RST 44.91, VDD 47.45 final x), GND pad up to its own via; U7 left of R21-R23
    "C52": (30.5, 28.0, 90), "C51": (32.4, 28.0, 90), "C53": (34.3, 28.0, 90), "C50": (36.45, 28.0, 90),
    "U7": (30.0, 25.0, 0), "R24": (26.2, 34.2, 90),
    # --- buck (bottom right)
    "L1": (47.6, 26.6, 90), "U2": (47.1, 31.6, 270), "C1": (45.1, 34.7, 180), "C3": (46.0, 22.6, 0),
    "R6": (49.9, 30.46, 0), "R8": (49.9, 32.74, 0), "R7": (49.9, 33.9, 180),   # EN pull-down / FB divider at their U2 pins
    # --- modem USB / misc on right strip
    "R4": (46.0, 13.8, 180), "R3": (46.0, 15.0, 180), "JP1": (50.3, 22.8, 0), "R25": (46.0, 19.4, 0),   # JP1 below the LTE SMA
    # --- USB-C + protection + LDO (top left)
    "J1": (3.3, 28.0, 270), "U1": (11.0, 28.0, 180), "R1": (10.2, 24.1, 0), "R2": (11.25, 30.5, 0), "C2": (12.2, 25.4, 0),   # rev 0.7: USB-C lowest on the left edge
    "U3": (56.0, 38.8, 90), "C5": (56.0, 42.3, 0), "C4": (55.5, 44.4, 0),   # LDO on VSYS, bottom-right corner by the buck
    # --- rev 0.2: USB select jumpers (pad 1 = MCU, 3 = modem), modem power override, BOOT0, shifter pulls
    "JP4": (15.0, 21.0, 0, "B"), "JP3": (15.0, 23.7, 0, "B"),   # bare-copper USB select jumpers on the bottom, between U1 and the MCU
    "R28": (16.4, 29.6, 270), "JP5": (20.5, 30.2, 0),
    "SW2": (34.3, 42.0, 90), "TP4": (33.1, 21.6, 0),
    "R29": (24.2, 9.05, 0), "R30": (20.15, 5.6, 270), "R31": (25.8, 11.55, 0), "R32": (28.5, 15.6, 270),
    # --- rev 0.3: battery input (bottom left) and USB/battery OR-ing (under the SIM holder)
    "J9": (11.5, 35.2, 0), "Q3": (19.0, 33.4, 0), "R33": (19.0, 36.3, 0),
    "U9": (23.6, 33.6, 0), "Q5": (23.6, 37.2, 0), "R35": (27.6, 33.4, 90), "C43": (26.55, 33.125, 90), "R36": (31.2, 33.4, 90),
    "U8": (29.4, 36.6, 0), "C44": (26.6, 36.6, 90), "R37": (31.4, 36.6, 90), "C45": (29.4, 39.0, 0),
    "D4": (39.6, 39.0, 90), "Q4": (38.7, 43.5, 270), "R34": (37.6, 39.0, 90),   # OR-ing between SW2 and the SIM holder
    # --- level shifter
    "U5": (25.9, 10.9, 180), "C21": (25, 15.4, 0), "TP3": (24.4, 16.2, 0),
    # --- MCU
    "U4": (18.4, 12.67, 180),
    "C10": (13.4, 19.3, 0), "C11": (13.75, 8.0, 180), "C12": (12.2, 16.07, 270), "C13": (21.0, 24.2, 0),
    "C14": (22.6, 19.9, 0), "C15": (23.4, 21.8, 0), "C16": (21.2, 18.47, 180),   # C14/C15 at VDDA pin 9
    "C17": (7.5, 42.25, 270), "R10": (34.8, 37.2, 0),  # C17 (NRST) beside the RESET button (owner placement)
    "R12": (9.5, 11.5, 90), "R13": (9.5, 9.0, 270),    # I2C pull-ups beside J3 (owner placement)
    "Y1": (25.8, 16, 180),                          # 32.768 kHz LSE: pin 1 top -> PC14 (pin 3), pin 2 bottom -> PC15 (pin 4)
    "C54": (24, 18.3, 90), "C55": (27.6, 18.3, 90),   # LSE load caps, OSC pad toward Y1
    # --- connectors left / bottom
    "J3": (3.4, 9.5, 270), "J2": (4.6, 18.0, 0),      # left edge top -> bottom: Qwiic (I2C2 pins), SWD, USB-C
    "J4": (11.0, 40.9, 90), "SW1": (4.5, 38.0, 180),  # RESET in the bottom-left corner, below USB-C (owner placement)
    # --- modem control
    "Q1": (18, 3.4, 0), "R14": (15, 2.3, 0), "R15": (15, 1.1, 0), "TP2": (17.4, 6.1, 0),
    "Q2": (22.6, 25.4, 0), "R16": (22.6, 28.0, 180), "R17": (20.5, 28, 0),
    "R27": (20.6, 6.3, 90), "R26": (25.6, 18.6, 90), "JP2": (25.6, 21.6, 90), "TP1": (20.6, 20.6, 0),
    # --- rev 0.5 antennas (final board coordinates, no block offset). GNSS chain along y = 5.0 from the module's
    # top-left corner to the J7 SMA: R20 0R (C59/C58 DNP shunts above) -> C56 DC block -> D5 TVS + L2/R38 bias feed below
    "C56": (35.1, 5.0, 180), "C58": (36.08, 3.5, 90), "C59": (38.03, 3.5, 90),
    "D5": (33.55, 6.3, 270), "L2": (32.5, 6.3, 270), "R38": (9.8, 3, 90), "C57": (11.4, 3, 90),
    "U10": (14, 3, 0), "R39": (16.5, 3, 90), "C60": (16.5, 1, 0),
    # LTE: R19 -> C61 -> node (J6 U.FL below, D6 TVS above, R40 DNP 0R east) -> J10 SMA on the right edge
    "C61": (59.0, 7.35, 0), "D6": (60.45, 6.2, 90), "R40": (62.6, 8.0, 270), "J10": (63.5, 17.6, 270),
    # --- rev 0.6 audit parts (final coordinates): U5 VCCA cap, VBAT TVS between C31 and the LTE match (supply end of
    # the VBAT bus, as in HD V1.05 Fig. 5), PWRKEY ESD between pin 39's escape via and the top edge
    "R41": (21.4, 26.4, 90), "R42": (22.4, 26.4, 90),   # rev 0.8: fuel-gauge bus (I2C1) pull-ups
    "C62": (32.98, 15.4, 0), "D7": (57.35, 4.05, 0), "D8": (45.1, 0.85, 180),
    # --- LEDs
    "D1": (27.0, 30.0, 0), "R9": (27.0, 31.5, 0),   # LEDs in the bottom middle: keeps the MCU bottom edge free
    "D2": (30.4, 30.0, 0), "R11": (30.4, 31.5, 0),
    "D3": (33.8, 30.0, 0), "R18": (33.8, 31.5, 0),
}

# Widened from 51 to 63.5 mm: modem/RF/SIM/buck block moves right by 11 mm,
# level shifter + modem control block by 5 mm, opening two routing channels.
BIG = set("U6 J6 R19 C40 C41 R20 J7 C30 C31 C32 C33 C34 C35 C20 J8 R21 R22 R23 R24 C50 C51 C52 C53 U7 "
          "L1 U2 C1 C3 R7 R8 R6 R3 R4 JP1 R25 TP3".split())
MID = set("U5 C21 Q1 R14 R15 TP2 Q2 R16 R17 R27 R26 JP2 TP1".split())
for r, (x, y, a, *side) in list(PLACE.items()):
    PLACE[r] = (x + (11.0 if r in BIG else 5.0 if r in MID else 0.0), y, a, *side)

# ---------------------------------------------------------------- netlist
txt = open(NETLIST).read()
comps = []
for m in re.finditer(r'\(comp \(ref "([^"]+)"\)(.*?)\(tstamps "([0-9a-f-]{36})"\)\)', txt, re.S):
    ref, body, uuid = m.groups()
    val = re.search(r'\(value "([^"]*)"\)', body).group(1)
    fp = re.search(r'\(footprint "([^"]*)"\)', body).group(1)
    props = dict(re.findall(r'\(property \(name "([^"]+)"\) \(value "([^"]*)"\)\)', body))
    dnp = '(property (name "dnp"))' in body
    exbom = '(property (name "exclude_from_bom"))' in body
    comps.append(dict(ref=ref, val=val, fp=fp, props=props, uuid=uuid, dnp=dnp, exbom=exbom))

pinnet = {}
netnames = []
nets_txt = txt[txt.index("(nets"):]
for m in re.finditer(r'\(net \(code "\d+"\) \(name "([^"]*)"\)(.*?)(?=\(net \(code|\Z)', nets_txt, re.S):
    name, body = m.groups()
    netnames.append(name)
    for r, p in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', body):
        pinnet[(r, p)] = name

# ---------------------------------------------------------------- board
board = pcbnew.CreateEmptyBoard() if hasattr(pcbnew, "CreateEmptyBoard") else pcbnew.BOARD()
board.SetCopperLayerCount(4)
ds = board.GetDesignSettings()
ds.SetBoardThickness(FromMM(1.6))

netinfo = {}
for n in netnames:
    ni = pcbnew.NETINFO_ITEM(board, n)
    board.Add(ni)
    netinfo[n] = ni

missing = []
for c in comps:
    lib, name = c["fp"].split(":")
    path = os.path.join(PROJ, "lte_board_lcsc.pretty") if lib == "lte_board_lcsc" else f"{STDLIB}/{lib}.pretty"
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise SystemExit(f"cannot load {c['fp']}")
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetReference(c["ref"])
    fp.SetValue(c["val"])
    fp.SetPath(pcbnew.KIID_PATH("/" + c["uuid"]))
    fp.SetSheetname("/")
    fp.SetSheetfile("lte_board.kicad_sch")
    for k in ("LCSC", "MPN"):
        if k in c["props"]:
            fld = pcbnew.PCB_FIELD(fp, fp.GetNextFieldId(), k) if hasattr(fp, "GetNextFieldId") else pcbnew.PCB_FIELD(fp, 0, k)
            fld.SetText(c["props"][k]); fld.SetVisible(False); fld.SetLayer(pcbnew.F_Fab)
            fp.Add(fld)
    if c["dnp"]:
        fp.SetDNP(True)
    fp.SetExcludedFromBOM(c["exbom"])                     # follow the symbol (jumpers, test pads, DNP parts are not BOM items)
    board.Add(fp)
    for pad in fp.Pads():
        n = pad.GetNumber()
        if n and (c["ref"], n) in pinnet:
            pad.SetNet(netinfo[pinnet[(c["ref"], n)]])
    if c["ref"] in PLACE:
        x, y, r = PLACE[c["ref"]][:3]
        fp.SetPosition(P(x, y))
        if PLACE[c["ref"]][3:] == ("B",):                  # bottom side (bare-copper solder jumpers only)
            try: fp.Flip(P(x, y), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
            except (AttributeError, TypeError): fp.Flip(P(x, y), True)
        fp.SetOrientationDegrees(r)
    else:
        missing.append(c["ref"])
        fp.SetPosition(P(W + 10 + 4 * (len(missing) % 8), 5 + 4 * (len(missing) // 8)))
    # small silk refs
    t = fp.Reference()
    t.SetTextSize(VECTOR2I(FromMM(0.6), FromMM(0.6))); t.SetTextThickness(FromMM(0.1))
print("unplaced:", missing)

# ---------------------------------------------------------------- M2 mounting holes, 2.5 mm in from each corner
for i, (hx, hy) in enumerate([(2.5, 2.5), (W - 2.5, 2.5), (2.5, H - 2.5), (W - 2.5, H - 2.5)], 1):
    h = pcbnew.FootprintLoad(f"{STDLIB}/MountingHole.pretty", "MountingHole_2.2mm_M2")
    h.SetFPID(pcbnew.LIB_ID("MountingHole", "MountingHole_2.2mm_M2"))
    h.SetReference(f"H{i}"); h.SetValue("M2"); h.SetBoardOnly(True)
    h.SetExcludedFromBOM(True); h.SetExcludedFromPosFiles(True)
    h.SetPosition(P(hx, hy)); board.Add(h)

# ---------------------------------------------------------------- outline (rounded rect)
def edge_line(a, b):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(a); s.SetEnd(b); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(FromMM(0.1)); board.Add(s)
def edge_arc(c, start, angle):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_ARC)
    s.SetCenter(c); s.SetStart(start); s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T))
    s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(FromMM(0.1)); board.Add(s)
R = 1.0
edge_line(P(R, 0), P(W - R, 0)); edge_line(P(W, R), P(W, H - R))
edge_line(P(W - R, H), P(R, H)); edge_line(P(0, H - R), P(0, R))
edge_arc(P(W - R, R), P(W - R, 0), 90); edge_arc(P(W - R, H - R), P(W, H - R), 90)
edge_arc(P(R, H - R), P(R, H), 90); edge_arc(P(R, R), P(0, R), 90)

pcbnew.SaveBoard(OUT, board)
print("saved", OUT)
