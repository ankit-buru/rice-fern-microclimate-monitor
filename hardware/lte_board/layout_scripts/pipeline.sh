#!/usr/bin/env bash
# Regenerate the lte_board layout from the schematic: placement -> hand routes -> Freerouting (best of N)
# -> maze-route leftovers -> clean-ups -> DRC -> JLCPCB BOM/CPL.  See ../DESIGN.md, "Layout toolchain".
#
# WARNING: overwrites lte_board.kicad_pcb, lte_board.kicad_pro (rules), bom_jlcpcb.csv and cpl_jlcpcb.csv.
#          Hand edits made in KiCad are LOST. Commit first, or run on a copy (PROJ=/path/to/copy).
#
# usage:  FR_JAR=/path/freerouting-2.5.x.jar JAVA=/path/java25/bin/java ./pipeline.sh
# env:    PROJ       project dir (default: parent of this script)
#         KICAD_APP  KiCad app bundle (default /Applications/KiCad/KiCad.app; KiCad 9)
#         KCLI, KPY  kicad-cli and KiCad's bundled python (derived from KICAD_APP)
#         JAVA       java >= 25 (Freerouting 2.5 class files need it)
#         FR_JAR     freerouting jar (required)
#         ATTEMPTS   autorouter attempts, best kept (default 3)
#         WORK       scratch dir (default: mktemp)
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
PROJ=${PROJ:-$(dirname "$HERE")}
BRD=$PROJ/lte_board.kicad_pcb; PRO=$PROJ/lte_board.kicad_pro; SCH=$PROJ/lte_board.kicad_sch
KICAD_APP=${KICAD_APP:-/Applications/KiCad/KiCad.app}
KCLI=${KCLI:-$KICAD_APP/Contents/MacOS/kicad-cli}
KPY=${KPY:-$KICAD_APP/Contents/Frameworks/Python.framework/Versions/Current/bin/python3}
JAVA=${JAVA:-java}
FR_JAR=${FR_JAR:?set FR_JAR to the freerouting jar}
[ -f "$FR_JAR" ] || { echo "ERROR: FR_JAR not found: $FR_JAR"; exit 1; }
ATTEMPTS=${ATTEMPTS:-3}
WORK=${WORK:-$(mktemp -d)}
mkdir -p "$WORK"
echo "project: $PROJ   work: $WORK"

quiet() { grep -v -e Fontconfig -e "stdpbase" -e "memory leak" || true; }
# pcbnew.SaveBoard() rewrites the .kicad_pro with default rules: re-apply ours after EVERY python step that saves.
rules() { python3 "$HERE/mkpro.py" "$PRO"; }
kpy() { "$KPY" "$@" 2>&1 | quiet; rules; }
drc() { "$KCLI" pcb drc --schematic-parity -o "$WORK/drc.rpt" "$BRD" > "$WORK/drc.out" 2>&1; grep Found "$WORK/drc.out"; }
count() { grep -oE "Found [0-9]+ $1" "$WORK/drc.out" | grep -oE "[0-9]+"; }
clean_dangling() {   # drop vias/stubs left by the autorouter, one layer of the chain per pass
  for i in 1 2 3 4 5 6; do
    grep -q "_dangling" "$WORK/drc.rpt" || break
    kpy "$HERE/drop_dangling.py" "$BRD" "$WORK/drc.rpt" > /dev/null; drc > /dev/null
  done
}

# pcbnew.SaveBoard() resets the .kicad_pro to defaults; keep the saved one (KiCad GUI settings) and restore it at the end
cp "$PRO" "$WORK/project.kicad_pro.orig"
"$KCLI" sch export netlist --format kicadsexpr -o "$WORK/net.net" "$SCH" > /dev/null 2>&1 || { echo "netlist export failed"; exit 1; }

best=999999
for a in $(seq 1 "$ATTEMPTS"); do
  kpy "$HERE/gen_board.py" "$WORK/net.net" "$PROJ" "$BRD"          # placement from the netlist (PLACE table)
  kpy "$HERE/preroute.py" "$BRD" "$WORK/pre.dsn"                    # RF, VBAT bus, USB pair, +5V highway, planes, keepouts
  kpy "$HERE/hole_keepouts.py" "$BRD"
  kpy "$HERE/export_dsn.py" "$BRD" "$WORK/board.dsn"                # In1 track keepout under the RF half, DSN export
  cp "$BRD" "$WORK/prerouted.kicad_pcb"
  rm -f "$WORK/board.ses"
  ( cd "$WORK" && "$JAVA" -Djava.awt.headless=true -jar "$FR_JAR" --gui.enabled=false \
        -de board.dsn -do board.ses -mp 200 > "$WORK/freerouting.log" 2>&1 )
  if [ ! -s "$WORK/board.ses" ]; then
    echo "ERROR: Freerouting produced no session file; see $WORK/freerouting.log"; tail -5 "$WORK/freerouting.log"; exit 1
  fi
  kpy "$HERE/postroute.py" "$BRD" "$WORK/board.ses"                 # import + GND pours
  kpy "$HERE/stitch.py" "$BRD"
  kpy "$HERE/fixup.py" "$BRD"
  drc > /dev/null; clean_dangling; drc > /dev/null
  v=$(count violations); u=$(count unconnected); score=$((v + 10 * u))
  echo "attempt $a: $v violations, $u unconnected"
  if [ "$score" -lt "$best" ]; then best=$score; cp "$BRD" "$WORK/best.kicad_pcb"; cp "$WORK/drc.rpt" "$WORK/best_drc.rpt"; fi
  [ "$score" -eq 0 ] && break
done
cp "$WORK/best.kicad_pcb" "$BRD"; cp "$WORK/best_drc.rpt" "$WORK/drc.rpt"; rules

# finish whatever the autorouter left with the grid maze router (net-by-net, island-by-island)
NETS=$(grep -A3 "unconnected_items" "$WORK/drc.rpt" | grep -oE '\[[^]]+\]' | tr -d '[]' | grep -v '^GND$' | sort -u | tr '\n' ' ')
if [ -n "$NETS" ]; then
  echo "maze-routing: $NETS"
  kpy "$HERE/maze_route.py" "$BRD" $NETS | grep -E "routed|NO PATH|done"
  kpy "$HERE/stitch.py" "$BRD"
  kpy "$HERE/fixup.py" "$BRD"
fi
drc > /dev/null
kpy "$HERE/final_fixes.py" "$BRD" "$WORK/drc.rpt"                  # bridge stray vias, via every orphan GND island
kpy "$HERE/silk_marks.py" "$BRD"
drc > /dev/null; clean_dangling
echo "== final DRC"; drc; grep -E "^\[" "$WORK/drc.rpt" | sort | uniq -c

cp "$WORK/project.kicad_pro.orig" "$PRO"; rules        # original project settings + our rules (minimal diff)

# JLCPCB files (BOM from the schematic, CPL from KiCad's position file; script cross-checks them)
"$KCLI" pcb export pos --format csv --units mm --side front --exclude-dnp -o "$WORK/pos.csv" "$BRD" > /dev/null 2>&1
python3 "$HERE/make_jlc.py" "$WORK/net.net" "$WORK/pos.csv" "$PROJ"
