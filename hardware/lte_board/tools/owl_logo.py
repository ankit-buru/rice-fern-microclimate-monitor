#!/usr/bin/env python3
"""$KICAD_PY tools/owl_logo.py -- the board logo, lte_board_art.pretty/OwlTree_*, from art/OwlTree.svg: the lab owl (from
LaserHAT's art/OwlLogo.svg, laser beams and neuron removed) next to a tree.  Edit the art in any vector editor: white = silk,
gold #c8862a = exposed copper (the eyes, pad 1, tied to GND on the board), board green = knock-out; 1 unit = 1 mm before scaling.
Converted by tools/svg2footprint.py (copied from LaserHAT).  After a change: re-run this, then update LOGO1 from the library
(or re-place it) and check DRC around the exposed-copper eyes."""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")) + "/"
ART = ROOT + "art/OwlTree.svg"
DESCR = "Owl next to a tree, %s wide: silk, exposed-copper eyes (pad 1, tie to GND); from art/OwlTree.svg"
VARIANTS = [  # name, converter options, size for the description
    ("OwlTree_6mm", ["--scale", "0.39", "--origin", "center"], "6.6 mm"),
]
os.makedirs(ROOT + "lte_board_art.pretty", exist_ok=True)
for name, opts, size in VARIANTS:
    subprocess.run([sys.executable, ROOT + "tools/svg2footprint.py", ART, ROOT + "lte_board_art.pretty/%s.kicad_mod" % name,
                    "--tags", "logo owl tree", "--descr", DESCR % size] + opts, check=True)
