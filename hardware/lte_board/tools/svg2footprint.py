#!/usr/bin/env python3
"""$KICAD_PY tools/svg2footprint.py art.svg out.kicad_mod [options] -- board art drawn in two colours -> a KiCad footprint.

The colour of every fill and stroke picks its layer (nearest colour wins, an unknown colour is an error):
    SILK   (default #ffffff)  front silkscreen
    COPPER (default #c8862a)  exposed copper (F.Cu + F.Mask): custom pads all numbered "1", so one symbol pin ties them to a net
    BOARD  (default #1d5c2e)  the board itself: painting with it knocks out whatever silk / copper lies underneath
Shapes are painted in document order like any SVG (fill, then stroke): a later shape covers earlier ones, so silk drawn over
copper removes that copper and vice versa.  Draw the art as it should look on a green board (tools/fp2svg.py exports an existing
footprint that way).  <path>, <rect>, <circle>, <ellipse>, <line>, <polyline>, <polygon> and <g> with transforms, fill-rule,
presentation attributes, style="" and simple <style> class rules are understood; text must be converted to paths first.

Size and position: SVG lengths are converted with the root width / height (1 unit = 1 mm for tools/fp2svg.py output, else px at
96 dpi); --scale multiplies, --height sets the finished art height instead.  --origin svg (default) keeps the SVG point (0, 0)
as the footprint origin, --origin center centres the art.  --mirror flips left / right (after scaling, about the origin).
After painting, silk is pulled back --silk-clear (0.10 mm) from exposed copper (no silk-over-copper DRC warnings), strokes are
widened to at least --min-stroke (0.15 mm), and silk / copper features narrower than --min-width (0.15 mm) or gaps narrower than
--min-gap (0.15 mm) are reported (not changed).

Options: --name NAME (default: the output file name)  --descr TEXT  --tags TEXT  --silk COLOUR  --copper COLOUR  --board COLOUR
         --scale S  --height MM  --origin svg|center  --mirror  --silk-clear MM  --min-stroke MM  --min-width MM  --min-gap MM
         --tol MM (curve flattening, 0.005)
"""
import argparse
import math
import os
import re
import xml.etree.ElementTree as ET

import pcbnew

NM = 1e6
ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
ap.add_argument("svg")
ap.add_argument("out")
ap.add_argument("--name")
ap.add_argument("--descr", default="")
ap.add_argument("--tags", default="logo")
ap.add_argument("--silk", default="#ffffff")
ap.add_argument("--copper", default="#c8862a")
ap.add_argument("--board", default="#1d5c2e")
ap.add_argument("--scale", type=float, default=1.0)
ap.add_argument("--height", type=float)
ap.add_argument("--origin", choices=("svg", "center"), default="svg")
ap.add_argument("--mirror", action="store_true")
ap.add_argument("--silk-clear", type=float, default=0.10)
ap.add_argument("--min-stroke", type=float, default=0.15)
ap.add_argument("--min-width", type=float, default=0.15)
ap.add_argument("--min-gap", type=float, default=0.15)
ap.add_argument("--tol", type=float, default=0.005)
A = ap.parse_args()
NAME = A.name or os.path.splitext(os.path.basename(A.out))[0]

# ------------------------------------------------------------------------------------------------ colours
NAMED = {"black": "#000000", "white": "#ffffff", "red": "#ff0000", "green": "#008000", "blue": "#0000ff", "yellow": "#ffff00",
         "gold": "#ffd700", "orange": "#ffa500", "gray": "#808080", "grey": "#808080", "silver": "#c0c0c0"}


def rgb(c):
    c = c.strip().lower()
    c = NAMED.get(c, c)
    if c.startswith("#"):
        h = c[1:]
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    m = re.match(r"rgb\(\s*([\d.]+%?)\s*,\s*([\d.]+%?)\s*,\s*([\d.]+%?)\s*\)", c)
    if m:
        return tuple(round(float(v[:-1]) * 2.55) if v.endswith("%") else int(float(v)) for v in m.groups())
    raise SystemExit("unknown colour %r" % c)


PALETTE = {"silk": rgb(A.silk), "copper": rgb(A.copper), "board": rgb(A.board)}


def layer_of(c):
    """'silk' / 'copper' / 'board' for a paint value, None for none / transparent"""
    if c is None or c.strip().lower() in ("none", "transparent") or c.startswith("url("):
        if c and c.startswith("url("):
            raise SystemExit("gradients / patterns are not supported (%s)" % c)
        return None
    v = rgb(c)
    best = min(PALETTE, key=lambda k: sum((a - b) ** 2 for a, b in zip(v, PALETTE[k])))
    if math.dist(v, PALETTE[best]) > 80:
        raise SystemExit("colour %s is none of silk %s / copper %s / board %s (set --silk / --copper / --board)" % (c, A.silk, A.copper, A.board))
    return best


# ------------------------------------------------------------------------------------------------ transforms (a b c d e f)
def mul(m, n):
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (a * a2 + c * b2, b * a2 + d * b2, a * c2 + c * d2, b * c2 + d * d2, a * e2 + c * f2 + e, b * e2 + d * f2 + f)


def parse_transform(t):
    m = (1, 0, 0, 1, 0, 0)
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", t or ""):
        v = [float(x) for x in re.findall(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?", args)]
        if name == "matrix":
            n = tuple(v)
        elif name == "translate":
            n = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale":
            n = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate":
            r = math.radians(v[0]); cs, sn = math.cos(r), math.sin(r)
            n = (cs, sn, -sn, cs, 0, 0)
            if len(v) == 3:
                n = mul(mul((1, 0, 0, 1, v[1], v[2]), n), (1, 0, 0, 1, -v[1], -v[2]))
        elif name == "skewX":
            n = (1, 0, math.tan(math.radians(v[0])), 1, 0, 0)
        elif name == "skewY":
            n = (1, math.tan(math.radians(v[0])), 0, 1, 0, 0)
        else:
            raise SystemExit("unknown transform %s" % name)
        m = mul(m, n)
    return m


def apply(m, p):
    return (m[0] * p[0] + m[2] * p[1] + m[4], m[1] * p[0] + m[3] * p[1] + m[5])


# ------------------------------------------------------------------------------------------------ path data -> polylines
NUM = r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?"


def path_polylines(d, tol):
    """SVG path data -> [(points, closed)] in user units, curves flattened to within ~tol"""
    toks = re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|" + NUM, d)
    out, cur, i = [], [], 0
    x = y = sx = sy = 0.0
    last_c = last_q = None
    cmd = None

    def nums(k):
        nonlocal i
        v = [float(t) for t in toks[i:i + k]]
        i += k
        return v

    def seg_count(pts):
        L = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
        return max(2, min(200, int(math.sqrt(L / max(tol, 1e-6)) * 1.5)))

    def bez(p0, p1, p2, p3):
        n = seg_count([p0, p1, p2, p3])
        return [((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t * t * p2[0] + t ** 3 * p3[0],
                 (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t * t * p2[1] + t ** 3 * p3[1])
                for t in (k / n for k in range(1, n + 1))]

    def arc(p0, rx, ry, phi, large, sweep, p1):
        if rx == 0 or ry == 0:
            return [p1]
        cp, sp = math.cos(math.radians(phi)), math.sin(math.radians(phi))
        dx, dy = (p0[0] - p1[0]) / 2, (p0[1] - p1[1]) / 2
        x1, y1 = cp * dx + sp * dy, -sp * dx + cp * dy
        rx, ry = abs(rx), abs(ry)
        lam = x1 * x1 / (rx * rx) + y1 * y1 / (ry * ry)
        if lam > 1:
            rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
        num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
        co = math.sqrt(max(0.0, num / (rx * rx * y1 * y1 + ry * ry * x1 * x1))) * (-1 if large == sweep else 1)
        cx1, cy1 = co * rx * y1 / ry, -co * ry * x1 / rx
        cx, cy = cp * cx1 - sp * cy1 + (p0[0] + p1[0]) / 2, sp * cx1 + cp * cy1 + (p0[1] + p1[1]) / 2
        a0 = math.atan2((y1 - cy1) / ry, (x1 - cx1) / rx)
        a1 = math.atan2((-y1 - cy1) / ry, (-x1 - cx1) / rx)
        da = a1 - a0
        if sweep and da < 0:
            da += 2 * math.pi
        elif not sweep and da > 0:
            da -= 2 * math.pi
        n = max(2, min(200, int(abs(da) * max(rx, ry) / max(math.sqrt(8 * tol * max(rx, ry)), 1e-6)) + 1))
        return [(cx + rx * math.cos(a0 + da * k / n) * cp - ry * math.sin(a0 + da * k / n) * sp,
                 cy + rx * math.cos(a0 + da * k / n) * sp + ry * math.sin(a0 + da * k / n) * cp) for k in range(1, n + 1)]

    def flush(closed):
        nonlocal cur
        if len(cur) > 1:
            out.append((cur, closed))
        cur = []

    while i < len(toks):
        if re.match(r"[A-Za-z]", toks[i]):
            cmd = toks[i]; i += 1
            if cmd in "Zz":
                flush(True); x, y = sx, sy; last_c = last_q = None
                continue
        rel = cmd.islower()
        C = cmd.upper()
        ox, oy = (x, y) if rel else (0.0, 0.0)
        if C == "M":
            flush(False)
            px, py = nums(2); x, y = ox + px, oy + py; sx, sy = x, y; cur = [(x, y)]
            cmd = "l" if rel else "L"
            last_c = last_q = None
            continue
        if not cur:
            cur = [(x, y)]
        if C == "L":
            px, py = nums(2); x, y = ox + px, oy + py; cur.append((x, y)); last_c = last_q = None
        elif C == "H":
            (px,) = nums(1); x = ox + px; cur.append((x, y)); last_c = last_q = None
        elif C == "V":
            (py,) = nums(1); y = oy + py; cur.append((x, y)); last_c = last_q = None
        elif C in "CS":
            if C == "C":
                x1, y1, x2, y2, px, py = nums(6); c1 = (ox + x1, oy + y1)
            else:
                x2, y2, px, py = nums(4); c1 = (2 * x - last_c[0], 2 * y - last_c[1]) if last_c else (x, y)
            c2, p = (ox + x2, oy + y2), (ox + px, oy + py)
            cur += bez((x, y), c1, c2, p); last_c, last_q = c2, None; x, y = p
        elif C in "QT":
            if C == "Q":
                x1, y1, px, py = nums(4); q = (ox + x1, oy + y1)
            else:
                px, py = nums(2); q = (2 * x - last_q[0], 2 * y - last_q[1]) if last_q else (x, y)
            p = (ox + px, oy + py)
            c1 = (x + 2 / 3 * (q[0] - x), y + 2 / 3 * (q[1] - y)); c2 = (p[0] + 2 / 3 * (q[0] - p[0]), p[1] + 2 / 3 * (q[1] - p[1]))
            cur += bez((x, y), c1, c2, p); last_q, last_c = q, None; x, y = p
        elif C == "A":
            rx, ry, phi, large, sweep, px, py = nums(7); p = (ox + px, oy + py)
            cur += arc((x, y), rx, ry, phi, int(large), int(sweep), p); x, y = p; last_c = last_q = None
        else:
            raise SystemExit("bad path command %s" % cmd)
    flush(False)
    return out


def ellipse_pts(cx, cy, rx, ry, tol):
    n = max(12, min(256, int(2 * math.pi / math.acos(max(-1.0, 1 - tol / max(rx, ry, 1e-9))) + 1)))
    return [(cx + rx * math.cos(2 * math.pi * k / n), cy + ry * math.sin(2 * math.pi * k / n)) for k in range(n)]


# ------------------------------------------------------------------------------------------------ styles
root = ET.parse(A.svg).getroot()
SVGNS = "{http://www.w3.org/2000/svg}"
tag = lambda e: e.tag.replace(SVGNS, "")  # noqa: E731
CLASS = {}
for st in root.iter(SVGNS + "style"):
    for sel, body in re.findall(r"([^{}]+)\{([^}]*)\}", re.sub(r"/\*.*?\*/", "", st.text or "", flags=re.S)):
        props = dict((k.strip(), v.strip()) for k, v in (p.split(":", 1) for p in body.split(";") if ":" in p))
        for s in sel.split(","):
            s = s.strip()
            if s.startswith("."):
                CLASS.setdefault(s[1:], {}).update(props)
INHERIT = ("fill", "stroke", "stroke-width", "fill-rule", "display", "visibility", "stroke-linecap", "stroke-linejoin")


def style_of(e, parent):
    s = {k: parent[k] for k in INHERIT if k in parent}
    for c in (e.get("class") or "").split():
        s.update(CLASS.get(c, {}))
    for k in INHERIT + ("opacity",):
        if e.get(k) is not None:
            s[k] = e.get(k)
    for p in (e.get("style") or "").split(";"):
        if ":" in p:
            k, v = p.split(":", 1); s[k.strip()] = v.strip()
    return s


def length(v, default=0.0):
    if v is None:
        return default
    m = re.match(r"\s*(" + NUM + r")\s*(\w*|%)", v)
    return float(m.group(1)) if m else default


# root units: user unit -> mm
vb = [float(v) for v in re.findall(NUM, root.get("viewBox") or "")]
UNIT = {"mm": 1.0, "cm": 10.0, "in": 25.4, "pt": 25.4 / 72, "pc": 25.4 / 6, "px": 25.4 / 96, "": 25.4 / 96}
w_attr = root.get("width")
if w_attr and vb and not w_attr.strip().endswith("%"):
    m = re.match(r"\s*(" + NUM + r")\s*([a-z]*)", w_attr)
    USER_MM = float(m.group(1)) * UNIT.get(m.group(2), 25.4 / 96) / vb[2]
else:
    USER_MM = 25.4 / 96

# ------------------------------------------------------------------------------------------------ collect painted shapes
SHAPES = []          # (layer, kind 'fill' / 'stroke', [(pts, closed)] in mm (pre scale), fill-rule, stroke width mm)
WARN = []


def walk(e, m, st):
    t = tag(e)
    if t in ("defs", "clipPath", "mask", "symbol", "metadata", "title", "desc", "style"):
        return
    st = style_of(e, st)
    if st.get("display") == "none" or st.get("visibility") == "hidden":
        return
    m = mul(m, parse_transform(e.get("transform")))
    tol = A.tol / USER_MM / max(1e-9, math.sqrt(abs(m[0] * m[3] - m[1] * m[2])))
    if t in ("svg", "g", "a"):
        for c in e:
            walk(c, m, st)
        return
    if t == "path":
        polys = path_polylines(e.get("d") or "", tol)
    elif t == "rect":
        x, y, w, h = (length(e.get(k)) for k in ("x", "y", "width", "height"))
        polys = [([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], True)]
        if e.get("rx") or e.get("ry"):
            WARN.append("rounded rect corners ignored")
    elif t in ("circle", "ellipse"):
        cx, cy = length(e.get("cx")), length(e.get("cy"))
        rx = length(e.get("r")) if t == "circle" else length(e.get("rx"))
        ry = length(e.get("r")) if t == "circle" else length(e.get("ry"))
        polys = [(ellipse_pts(cx, cy, rx, ry, tol), True)]
    elif t == "line":
        polys = [([(length(e.get("x1")), length(e.get("y1"))), (length(e.get("x2")), length(e.get("y2")))], False)]
    elif t in ("polyline", "polygon"):
        v = [float(x) for x in re.findall(NUM, e.get("points") or "")]
        polys = [(list(zip(v[0::2], v[1::2])), t == "polygon")]
    elif t in ("text", "image", "use"):
        WARN.append("<%s> skipped (convert to paths / unlink first)" % t)
        return
    else:
        return
    k = USER_MM
    polys = [([(apply(m, p)[0] * k, apply(m, p)[1] * k) for p in pts], closed) for pts, closed in polys]
    if t != "line" and any(len(p) > 2 for p, _ in polys):          # a line has no fill
        fill = layer_of(st.get("fill", "#000000"))                  # SVG default fill is black
        if fill:
            SHAPES.append((fill, "fill", polys, st.get("fill-rule", "nonzero"), 0.0))
    stroke = layer_of(st.get("stroke"))
    if stroke:
        sw = length(st.get("stroke-width"), 1.0) * k * math.sqrt(abs(m[0] * m[3] - m[1] * m[2]))
        SHAPES.append((stroke, "stroke", polys, None, sw))


walk(root, (1, 0, 0, 1, 0, 0), {})
for w in sorted(set(WARN)):
    print("warning:", w)


# ------------------------------------------------------------------------------------------------ geometry
def poly_set(pts):
    s = pcbnew.SHAPE_POLY_SET(); s.NewOutline()
    for x, y in pts:
        s.Append(int(round(x * NM)), int(round(y * NM)))
    return s


def area2(pts):
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))


def fill_region(polys, rule):
    """the filled area of a set of subpaths (evenodd: XOR; nonzero: same-winding-as-the-largest minus the opposite)"""
    subs = [p for p, _ in polys if len(p) > 2 and abs(area2(p)) > 1e-12]
    out = pcbnew.SHAPE_POLY_SET()
    if not subs:
        return out
    if rule == "evenodd":
        for p in subs:
            out.BooleanXor(poly_set(p))
        return out
    sign = 1 if area2(max(subs, key=lambda p: abs(area2(p)))) > 0 else -1
    neg = pcbnew.SHAPE_POLY_SET()
    for p in subs:
        (out if area2(p) * sign > 0 else neg).BooleanAdd(poly_set(p))
    out.BooleanSubtract(neg)
    return out


def capsule(a, b, r):
    """the outline of a round-capped segment a-b of half-width r"""
    L = math.dist(a, b)
    ux, uy = ((b[0] - a[0]) / L, (b[1] - a[1]) / L) if L > 1e-9 else (1.0, 0.0)
    n = max(4, int(math.pi / math.acos(max(-1.0, 1 - A.tol / max(r, 1e-9)))) + 1)
    base = math.atan2(uy, ux)
    pts = [(b[0] + r * math.cos(base - math.pi / 2 + math.pi * k / n), b[1] + r * math.sin(base - math.pi / 2 + math.pi * k / n)) for k in range(n + 1)]
    pts += [(a[0] + r * math.cos(base + math.pi / 2 + math.pi * k / n), a[1] + r * math.sin(base + math.pi / 2 + math.pi * k / n)) for k in range(n + 1)]
    return pts


def stroke_region(polys, w):
    """round-capped, round-joined stroke of every subpath"""
    out = pcbnew.SHAPE_POLY_SET()
    for pts, closed in polys:
        pp = pts + [pts[0]] if closed else pts
        for a, b in zip(pp, pp[1:]):
            out.BooleanAdd(poly_set(capsule(a, b, w / 2)))
    return out


def transform_shapes(scale, dx, dy, mirror):
    """shapes in finished-footprint mm: scaled about the SVG origin, shifted, mirrored"""
    sx = -scale if mirror else scale
    return [(lay, kind, [([(sx * (x + dx), scale * (y + dy)) for x, y in pts], c) for pts, c in polys], rule, sw * scale)
            for lay, kind, polys, rule, sw in SHAPES]


def paint(shapes, min_stroke):
    L = {"silk": pcbnew.SHAPE_POLY_SET(), "copper": pcbnew.SHAPE_POLY_SET()}
    for lay, kind, polys, rule, sw in shapes:
        R = fill_region(polys, rule) if kind == "fill" else stroke_region(polys, max(sw, min_stroke))
        if R.OutlineCount() == 0:
            continue
        for k in L:
            if k == lay:
                L[k].BooleanAdd(R)
            else:
                L[k].BooleanSubtract(R)
    return L


def bbox(L):
    boxes = [L[k].BBox() for k in L if L[k].OutlineCount()]
    return (min(b.GetLeft() for b in boxes) / NM, min(b.GetTop() for b in boxes) / NM,
            max(b.GetRight() for b in boxes) / NM, max(b.GetBottom() for b in boxes) / NM)


# pass 1 (unscaled) for the size / centre, pass 2 for real
scale, dx, dy = A.scale, 0.0, 0.0
if A.height or A.origin == "center":
    x0, y0, x1, y1 = bbox(paint(transform_shapes(1.0, 0, 0, False), 0.0))
    if A.height:
        scale = A.height / (y1 - y0)
    if A.origin == "center":
        dx, dy = -(x0 + x1) / 2, -(y0 + y1) / 2
L = paint(transform_shapes(scale, dx, dy, A.mirror), A.min_stroke)
if A.silk_clear > 0 and L["copper"].OutlineCount():
    keep = pcbnew.SHAPE_POLY_SET(L["copper"]); keep.Inflate(int(A.silk_clear * NM), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, int(A.tol * NM))
    L["silk"].BooleanSubtract(keep)
for k in L:
    L[k].Simplify()


# ------------------------------------------------------------------------------------------------ fab checks (report only)
def thin_spots(S, d, what):
    """regions of S narrower than d (an opening by d/2 removes them) or gaps narrower than d (a closing fills them)"""
    h, err = int((d / 2 - 2 * A.tol) * NM), int(A.tol * NM)            # a little slack: a stroke of exactly d loses ~tol to flattening
    o = pcbnew.SHAPE_POLY_SET(S); o.Inflate(-h, pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, err); o.Inflate(h, pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, err)
    c = pcbnew.SHAPE_POLY_SET(S); c.Inflate(h, pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, err); c.Inflate(-h, pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, err)
    thin = pcbnew.SHAPE_POLY_SET(S); thin.BooleanSubtract(o)
    gaps = pcbnew.SHAPE_POLY_SET(c); gaps.BooleanSubtract(S)
    for name, R in (("narrower than %.2f mm" % d, thin), ("gap under %.2f mm" % d, gaps)):
        spots = []
        for i in range(R.OutlineCount()):
            ol = R.Outline(i)
            a = abs(ol.Area()) / NM ** 2
            if a > (d * d) * 0.6:                     # ignore slivers at sharp tips and corners
                b = ol.BBox(); spots.append((a, (b.Centre().x / NM, b.Centre().y / NM)))
        if spots:
            print("check: %s %s at %d place(s): %s" % (what, name, len(spots), ", ".join("(%.2f, %.2f)" % p for _, p in sorted(spots, reverse=True)[:6])))


thin_spots(L["silk"], A.min_width, "silk")
thin_spots(L["copper"], A.min_width, "copper")


# ------------------------------------------------------------------------------------------------ output
def outlines(S):
    T = pcbnew.SHAPE_POLY_SET(S); T.Fracture()
    for i in range(T.OutlineCount()):
        ol = T.COutline(i)
        yield [(ol.CPoint(j).x / NM, ol.CPoint(j).y / NM) for j in range(ol.PointCount())]


def anchor(pts):
    """a point well inside the island and the radius of the largest anchor circle that stays inside it"""
    S = poly_set(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    best, bd = None, -1
    n = 24
    for i in range(1, n):
        for j in range(1, n):
            x, y = min(xs) + (max(xs) - min(xs)) * i / n, min(ys) + (max(ys) - min(ys)) * j / n
            if not S.Contains(pcbnew.VECTOR2I(int(x * NM), int(y * NM))):
                continue
            d = min(seg_dist((x, y), a, b) for a, b in zip(pts, pts[1:] + pts[:1]))
            if d > bd:
                best, bd = (x, y), d
    return best, bd


def seg_dist(p, a, b):
    ax, ay = b[0] - a[0], b[1] - a[1]
    L2 = ax * ax + ay * ay
    t = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / L2))
    return math.dist(p, (a[0] + t * ax, a[1] + t * ay))


F = lambda v: "%.4f" % v  # noqa: E731
x0, y0, x1, y1 = bbox(L)
txt = ['(footprint "%s" (version 20240108) (generator "svg2footprint")' % NAME,
       '  (layer "F.Cu")',
       '  (descr "%s")' % (A.descr or "%s from %s" % (NAME, os.path.basename(A.svg))).replace('"', "'"),
       '  (tags "%s")' % A.tags,
       '  (attr exclude_from_pos_files exclude_from_bom)',
       '  (property "Reference" "G***" (at 0 %s 0) (layer "F.SilkS") hide (effects (font (size 1 1) (thickness 0.15))))' % F(y0 - 0.8),
       '  (property "Value" "%s" (at 0 %s 0) (layer "F.Fab") hide (effects (font (size 1 1) (thickness 0.15))))' % (NAME, F(y1 + 0.8)),
       '  (property "Footprint" "" (at 0 0 0) (layer "F.Fab") hide (effects (font (size 1.27 1.27) (thickness 0.15))))',
       '  (property "Datasheet" "" (at 0 0 0) (layer "F.Fab") hide (effects (font (size 1.27 1.27) (thickness 0.15))))',
       '  (property "Description" "" (at 0 0 0) (layer "F.Fab") hide (effects (font (size 1.27 1.27) (thickness 0.15))))']
ns = 0
for pts in outlines(L["silk"]):
    txt.append('  (fp_poly (pts %s)\n    (stroke (width 0) (type solid)) (fill solid) (layer "F.SilkS"))' % " ".join("(xy %s %s)" % (F(x), F(y)) for x, y in pts))
    ns += 1
nc = 0
for pts in outlines(L["copper"]):
    (ax, ay), r = anchor(pts)
    d = max(0.01, min(0.5, 1.8 * r))
    txt.append('  (pad "1" smd custom (at %s %s) (size %s %s) (layers "F.Cu" "F.Mask") (zone_connect 2)\n'
               '    (options (clearance outline) (anchor circle))\n    (primitives\n      (gr_poly (pts %s) (width 0) (fill yes))\n    ))'
               % (F(ax), F(ay), F(d), F(d), " ".join("(xy %s %s)" % (F(x - ax), F(y - ay)) for x, y in pts)))
    nc += 1
txt.append(")")
open(A.out, "w").write("\n".join(txt) + "\n")
print("%s: %d silk polygons, %d copper islands (pads \"1\"), %.2f x %.2f mm, scale %.4f%s" % (
    NAME, ns, nc, x1 - x0, y1 - y0, scale, ", mirrored" if A.mirror else ""))
