"""Set power track widths to the layer rules in lte_board.kicad_dru:
  Power (+3V3, +5V, VDD_EXT, GNSS)                    0.5 mm on In2, 0.3 mm on F.Cu/B.Cu
  Batt  (BATT_IN, BATT_N, VBAT, VSYS, BUCK_SW)        0.5 mm on In2, 0.4 mm on F.Cu/B.Cu (battery current)
A track that can't take the full width (fine-pitch pins, tight gaps) steps down until DRC is clean around it, else
it keeps its old width. DRC violations that existed before the run are ignored. +3V8 (class VBAT) is not touched.
usage: power_widths.py board.kicad_pcb      (run mkpro.py on the project afterwards)"""
import sys, os, json, subprocess, tempfile, pcbnew
from pcbnew import FromMM, ToMM
BRD = sys.argv[1]
KCLI = os.environ.get("KCLI", "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")
LADDER = {("Power", True): [0.5, 0.45, 0.4, 0.35, 0.3], ("Power", False): [0.3, 0.25, 0.2, 0.15],
          ("Batt", True): [0.5, 0.45, 0.4], ("Batt", False): [0.4, 0.35, 0.3]}     # (class, inner?) -> widths
INNER = (pcbnew.In1_Cu, pcbnew.In2_Cu)

def drc():
    """{uuid: [violation types]} for every item in a DRC violation"""
    out = tempfile.mktemp(suffix=".json")
    subprocess.run([KCLI, "pcb", "drc", "--format", "json", "--severity-error", "-o", out, BRD], capture_output=True)
    d = json.load(open(out)); os.remove(out); hit = {}
    for v in d["violations"]:
        for it in v["items"]:
            hit.setdefault(it["uuid"], []).append(v["type"])
    return hit

def save(b):
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(BRD, b)

before = set(drc())
b = pcbnew.LoadBoard(BRD)
todo = {}                                     # uuid -> [ladder index, original width]
for t in b.GetTracks():
    if t.Type() != pcbnew.PCB_TRACE_T or t.GetNetClassName() not in ("Power", "Batt"): continue
    lad = LADDER[(t.GetNetClassName(), t.GetLayer() in INNER)]
    if round(ToMM(t.GetWidth()), 3) != lad[0] and t.m_Uuid.AsString() not in before:
        todo[t.m_Uuid.AsString()] = [0, t.GetWidth()]; t.SetWidth(FromMM(lad[0]))
print("tracks set to the layer width:", len(todo))
for it in range(8):
    save(b); hit = drc()
    bad = [u for u in todo if u in hit]
    print(f"pass {it + 1}: {len(bad)} tracks in a DRC violation")
    if not bad: break
    b = pcbnew.LoadBoard(BRD); tracks = {t.m_Uuid.AsString(): t for t in b.GetTracks()}
    for u in bad:
        t = tracks[u]; lad = LADDER[(t.GetNetClassName(), t.GetLayer() in INNER)]; todo[u][0] += 1
        if todo[u][0] < len(lad):
            t.SetWidth(FromMM(lad[todo[u][0]]))
        else:
            t.SetWidth(todo[u][1]); todo[u][0] = 99      # give up: original width
b = pcbnew.LoadBoard(BRD)
final = {}
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_TRACE_T and t.GetNetClassName() in ("Power", "Batt"):
        k = (t.GetNetClassName(), b.GetLayerName(t.GetLayer()), round(ToMM(t.GetWidth()), 3))
        final[k] = final.get(k, 0) + 1
print("power tracks now (class, layer, width): count ->", dict(sorted(final.items())))
