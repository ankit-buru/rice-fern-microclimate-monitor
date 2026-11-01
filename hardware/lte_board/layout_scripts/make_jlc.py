"""Build JLCPCB BOM + CPL from the KiCad project and check they agree.

usage: make_jlc.py <netlist.net> <pos.csv from kicad-cli> <out_dir>
BOM: every symbol that is in the BOM and not DNP, grouped by (value, footprint, LCSC). Fails if any lacks an LCSC #.
CPL: every footprint KiCad puts in the position file (DNP and exclude-from-position-files already left out),
     with JLC's rotation/origin corrections (JLC_CORR) applied.
"""
import csv, math, re, sys, collections
NET, POS, OUT = sys.argv[1:4]
t = open(NET).read()
parts = {}
for m in re.finditer(r'\(comp \(ref "([^"]+)"\)(.*?)\(tstamps "[0-9a-f-]{36}"\)\)', t, re.S):
    ref, body = m.groups()
    if '(property (name "exclude_from_bom"))' in body or '(property (name "dnp"))' in body:
        continue
    props = dict(re.findall(r'\(property \(name "([^"]+)"\) \(value "([^"]*)"\)\)', body))
    val = re.search(r'\(value "([^"]*)"\)', body).group(1)
    fp = re.search(r'\(footprint "([^"]*)"\)', body).group(1).split(":")[-1]
    parts[ref] = (val, fp, props.get("LCSC", ""), props.get("MPN", ""))

missing = sorted(r for r, p in parts.items() if not p[2])
if missing:
    sys.exit("ERROR: BOM parts without an LCSC number: " + ", ".join(missing))

def refkey(r):
    m = re.match(r"([A-Za-z#]+)(\d+)", r); return (m.group(1), int(m.group(2))) if m else (r, 0)
groups = collections.OrderedDict()          # one line per (footprint, LCSC #); comments of merged lines are joined
vals = {}
for ref in sorted(parts, key=refkey):
    val, fp, lcsc, mpn = parts[ref]
    key = ("", fp, lcsc, mpn)
    groups.setdefault(key, []).append(ref); vals.setdefault(key, [])
    if val not in vals[key]: vals[key].append(val)
groups = collections.OrderedDict((("/".join(vals[k]),) + k[1:], v) for k, v in groups.items())
with open(f"{OUT}/bom_jlcpcb.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #", "MPN", "Qty"])
    for (val, fp, lcsc, mpn), refs in sorted(groups.items(), key=lambda kv: refkey(kv[1][0])):
        w.writerow([val, ",".join(refs), fp, lcsc, mpn, len(refs)])

# JLC places each part using its own (LCSC/EasyEDA) footprint, whose zero orientation and origin often differ from
# KiCad's. LCSC # -> (extra rotation, CCW degrees; origin offset of the EasyEDA footprint in KiCad footprint-local mm,
# y down). Derived by fitting every KiCad footprint's pads onto the easyeda2kicad import of the same LCSC part:
# by pad number for ICs/transistors, by geometry for U.FL/SIM/buttons, and by the LCSC symbol's K/A pin names for
# diodes and LEDs (their EasyEDA pad numbers don't consistently mean cathode). Re-derive if a footprint or LCSC # changes.
JLC_CORR = {
    "C20526": (180, 0, 0), "C15127": (180, 0, 0),           # MMBT3904, AO3401A (SOT-23)
    "C908265": (180, 0, 0),                                 # FS8205A (SOT-23-6, EasyEDA "BR")
    "C7519": (270, 0, 0), "C351410": (270, 0, 0),           # USBLC6-2SC6, DW01A (SOT-23-6, EasyEDA "BL")
    "C78988": (180, 0, 0), "C2887324": (180, 0, 0),         # SY8089, TPS7A0233 (SOT-23-5)
    "C48677": (180, 0, 0),                                  # ESDA6V1W5 (SC-70-5)
    "C465977": (270, 0, 0), "C17206": (270, 0, 0),          # STM32L072 LQFP-48, TXS0108E TSSOP-20
    "C3975188": (270, 0, 0),                                # SWD header 2x5 1.27 mm
    "C88374": (270, -0.29, 0),                              # U.FL
    "C165948": (0, 0, -1.575),                              # USB-C TYPE-C-31-M-12
    "C145956": (0, 0, -0.22),                               # Qwiic 1.0T-4P
    "C5251182": (180, 1.0, 0),                              # JST PH 2-pin THT (pin 1 = +)
    "C2286": (0, 0, 0), "C2287": (0, 0, 0), "C12624": (0, 0, 0), "C8598": (0, 0, 0),   # LEDs, B5819W: cathode -x in both
    "C2943992": (0, 0, 0), "C266888": (0, 0, 0), "C2682616": (0, 0, 0), "C318884": (0, 0, 0),
    "C279948": (0, 0, 0), "C97604": (180, 0, 0),           # L1 (Sunlord land, centred), Y1 crystal (EasyEDA pad 1 at -x)
    "C47507": (0, 0, 0), "C3039401": (0, 0, 0), "C535146": (0, 0, 0),   # TPS22945, WE05DGCF-B, ESD103: the EasyEDA land itself
    "C192855": (0, 0, 0),                                   # LQW15AN 47 nH on KiCad L_0402 (symmetric)
    "C239784": (0, 0, 0),                                   # ESD5651N-2/TR VBAT TVS: the EasyEDA land itself
}
lcsc_of = {ref: p[2] for ref, p in parts.items()}
fp_of = {ref: p[1] for ref, p in parts.items()}
unknown = sorted({lcsc_of[r] + " (" + fp_of[r] + ")" for r in parts
                  if lcsc_of[r] not in JLC_CORR and not re.match(r"(R|C)_\d{4}_", fp_of[r])})
if unknown:
    sys.exit("ERROR: no JLC rotation entry for: " + ", ".join(unknown))

pos = list(csv.DictReader(open(POS)))
def jlc_place(r):
    """KiCad position file row -> JLC (x, y, rotation). pos.csv has y up; offsets are in footprint coords, y down."""
    x, y, rot = float(r["PosX"]), float(r["PosY"]), float(r["Rot"])
    dr, ox, oy = JLC_CORR.get(lcsc_of.get(r["Ref"], ""), (0, 0, 0))
    a = math.radians(rot)                      # KiCad rotation, CCW on screen
    gx = ox * math.cos(a) + oy * math.sin(a)   # offset rotated into board coords (y down)
    gy = -ox * math.sin(a) + oy * math.cos(a)
    return x + gx, y - gy, (rot + dr) % 360
with open(f"{OUT}/cpl_jlcpcb.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    for r in sorted(pos, key=lambda r: refkey(r["Ref"])):
        x, y, rot = jlc_place(r)
        w.writerow([r["Ref"], f'{x:.4f}mm', f'{y:.4f}mm', "Top" if r["Side"].lower().startswith("top") else "Bottom", f'{rot:.1f}'])

bom_refs, cpl_refs = set(parts), {r["Ref"] for r in pos}
print(f"BOM: {len(groups)} lines, {len(bom_refs)} parts | CPL: {len(cpl_refs)} placements")
print("in BOM but not CPL:", sorted(bom_refs - cpl_refs, key=refkey) or "none")
print("in CPL but not BOM:", sorted(cpl_refs - bom_refs, key=refkey) or "none")
