"""Build JLCPCB BOM + CPL from the KiCad project and check they agree.

usage: make_jlc.py <netlist.net> <pos.csv from kicad-cli> <out_dir>
BOM: every symbol that is in the BOM and not DNP, grouped by (value, footprint, LCSC). Fails if any lacks an LCSC #.
CPL: every footprint KiCad puts in the position file (DNP and exclude-from-position-files already left out).
"""
import csv, re, sys, collections
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

pos = list(csv.DictReader(open(POS)))
with open(f"{OUT}/cpl_jlcpcb.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    for r in sorted(pos, key=lambda r: refkey(r["Ref"])):
        w.writerow([r["Ref"], f'{float(r["PosX"]):.4f}mm', f'{float(r["PosY"]):.4f}mm', "Top" if r["Side"].lower().startswith("top") else "Bottom", f'{float(r["Rot"]):.1f}'])

bom_refs, cpl_refs = set(parts), {r["Ref"] for r in pos}
print(f"BOM: {len(groups)} lines, {len(bom_refs)} parts | CPL: {len(cpl_refs)} placements")
print("in BOM but not CPL:", sorted(bom_refs - cpl_refs, key=refkey) or "none")
print("in CPL but not BOM:", sorted(cpl_refs - bom_refs, key=refkey) or "none")
