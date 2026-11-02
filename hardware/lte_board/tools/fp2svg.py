#!/usr/bin/env python3
"""python3 tools/fp2svg.py <footprint.kicad_mod> <art.svg> -- a footprint's front silk and exposed copper as editable SVG art
for tools/svg2footprint.py: 1 SVG unit = 1 mm, the SVG origin = the footprint origin, drawn as the board looks (BOARD green
background, SILK white, COPPER gold).  Filled polygons become filled <path>s, lines become stroked <line>s with their width
(so a converter run with the same scale gives the same footprint back).  Reads fp_poly / fp_line / fp_circle on F.SilkS and
pads on F.Cu (custom gr_poly / gr_line / gr_circle primitives, circle and rect pads); everything else is left out."""
import math
import re
import sys

BOARD, SILK, COPPER = "#1d5c2e", "#ffffff", "#c8862a"


def parse(s):
    """s-expression -> nested lists of strings"""
    toks = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', s)
    stack = [[]]
    for t in toks:
        if t == "(":
            stack.append([])
        elif t == ")":
            x = stack.pop(); stack[-1].append(x)
        else:
            stack[-1].append(t[1:-1] if t.startswith('"') else t)
    return stack[0][0]


def find(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def one(node, key):
    f = find(node, key)
    return f[0] if f else None


def xy(node):
    return float(node[1]), float(node[2])


def pts(node):
    return [xy(p) for p in find(one(node, "pts"), "xy")]


def width(node):
    w = one(node, "width") or one(one(node, "stroke") or [], "width")
    return float(w[1]) if w else 0.0


def layer(node):
    lay = one(node, "layer")
    return lay[1] if lay else None


fp = parse(open(sys.argv[1]).read())
items = {"silk": [], "copper": []}          # (kind, data, width)
for g in fp:
    if not isinstance(g, list):
        continue
    if g[0] in ("fp_poly", "fp_line", "fp_circle") and layer(g) == "F.SilkS":
        if g[0] == "fp_poly":
            filled = (one(g, "fill") or [None, "no"])[1] in ("solid", "yes")
            items["silk"].append(("poly" if filled else "polyline", pts(g), width(g)))
        elif g[0] == "fp_line":
            items["silk"].append(("line", [xy(one(g, "start")), xy(one(g, "end"))], width(g)))
        else:
            c, e = xy(one(g, "center")), xy(one(g, "end"))
            items["silk"].append(("circle", (c, math.dist(c, e)), width(g)))
    elif g[0] == "pad" and "F.Cu" in (one(g, "layers") or []):
        ax, ay = xy(one(g, "at"))
        rot = math.radians(float(one(g, "at")[3])) if len(one(g, "at")) > 3 else 0.0
        T = lambda p: (ax + p[0] * math.cos(rot) + p[1] * math.sin(rot), ay - p[0] * math.sin(rot) + p[1] * math.cos(rot))  # noqa: E731
        shape = g[3]
        prims = one(g, "primitives")
        if shape == "custom" and prims:
            for p in prims[1:]:
                if p[0] == "gr_poly":
                    items["copper"].append(("poly", [T(q) for q in pts(p)], 0.0))
                elif p[0] == "gr_line":
                    items["copper"].append(("line", [T(xy(one(p, "start"))), T(xy(one(p, "end")))], width(p)))
                elif p[0] == "gr_circle":
                    c, e = xy(one(p, "center")), xy(one(p, "end"))
                    items["copper"].append(("disc", (T(c), math.dist(c, e) + width(p) / 2), 0.0))
        elif shape in ("circle", "rect"):
            w, h = map(float, one(g, "size")[1:3])
            if shape == "circle":
                items["copper"].append(("disc", ((ax, ay), w / 2), 0.0))
            else:
                items["copper"].append(("poly", [T(q) for q in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))], 0.0))

xs, ys = [], []
for kind, d, w in items["silk"] + items["copper"]:
    if kind in ("circle", "disc"):
        (cx, cy), r = d; xs += [cx - r, cx + r]; ys += [cy - r, cy + r]
    else:
        xs += [p[0] for p in d]; ys += [p[1] for p in d]
m = 1.0
x0, y0, x1, y1 = min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m
F = lambda v: ("%.4f" % v).rstrip("0").rstrip(".")  # noqa: E731


def svg_item(kind, d, w, colour):
    if kind == "poly":
        return '<path fill="%s" d="M%s Z"/>' % (colour, " L".join("%s,%s" % (F(x), F(y)) for x, y in d))
    if kind == "polyline":
        return '<polyline fill="none" stroke="%s" stroke-width="%s" stroke-linecap="round" stroke-linejoin="round" points="%s"/>' % (
            colour, F(w), " ".join("%s,%s" % (F(x), F(y)) for x, y in d))
    if kind == "line":
        (ax, ay), (bx, by) = d
        return '<line stroke="%s" stroke-width="%s" stroke-linecap="round" x1="%s" y1="%s" x2="%s" y2="%s"/>' % (colour, F(w), F(ax), F(ay), F(bx), F(by))
    (cx, cy), r = d
    if kind == "disc":
        return '<circle fill="%s" cx="%s" cy="%s" r="%s"/>' % (colour, F(cx), F(cy), F(r))
    return '<circle fill="none" stroke="%s" stroke-width="%s" cx="%s" cy="%s" r="%s"/>' % (colour, F(w), F(cx), F(cy), F(r))


out = ['<?xml version="1.0" encoding="UTF-8"?>',
       '<svg xmlns="http://www.w3.org/2000/svg" width="%smm" height="%smm" viewBox="%s %s %s %s">' % (F(x1 - x0), F(y1 - y0), F(x0), F(y0), F(x1 - x0), F(y1 - y0)),
       '  <!-- art for tools/svg2footprint.py: 1 unit = 1 mm, (0, 0) = footprint origin; %s = silk, %s = exposed copper,'
       ' %s = board (background; painting with it knocks out what is below).  Exported from %s -->' % (SILK, COPPER, BOARD, sys.argv[1].split("/")[-1]),
       '  <rect id="board" fill="%s" x="%s" y="%s" width="%s" height="%s"/>' % (BOARD, F(x0), F(y0), F(x1 - x0), F(y1 - y0)),
       '  <g id="silk">']
out += ["    " + svg_item(k, d, w, SILK) for k, d, w in items["silk"]]
out += ['  </g>', '  <g id="copper">']
out += ["    " + svg_item(k, d, w, COPPER) for k, d, w in items["copper"]]
out += ['  </g>', '</svg>', '']
open(sys.argv[2], "w").write("\n".join(out))
print("%s: %d silk and %d copper shapes, %.1f x %.1f mm" % (sys.argv[2], len(items["silk"]), len(items["copper"]), x1 - x0 - 2 * m, y1 - y0 - 2 * m))
