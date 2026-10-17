#!/usr/bin/env python3
"""A knitting chart for a cup cosy with coffee beans, graded on the beans as
they would come out in the fabric. Written 2026-10-10, before any model saw
the prompt.

A knit stitch is wider than it is tall. A usual gauge is about 5 stitches to
7 rows over the same distance, so one stitch is about 1.35 times as wide as
it is tall. A bean drawn nicely on square cells knits up squat. The chart has
to either draw its cells wider than tall, so what you see is what you knit,
or draw the bean stretched tall on square cells, so the fabric squashes it
back into shape. Either way the fabric is what counts, and the fabric only
depends on which stitches are coloured and on the gauge. So the bean is
measured in stitches and rows and turned into fabric units.

How the chart is read:

  1. The grid comes from the vector drawing. Cells are rectangles: <rect>,
     <use> of a rect, or square subpaths of a <path>, after every transform.
     The most common cell size, at least 20 of them, and the biggest
     touching block of them on one lattice is the grid. A cell is as wide
     and tall as the step from one cell to the next, so a gap drawn between
     cells counts as part of them. Grid lines are the
     other way: long horizontal and vertical strokes at an even pitch. A
     rectangle filled with a <pattern> tile is the third: the tile is the
     cell. The reading that finds more cells wins.
  2. The page is rendered with rsvg-convert and every cell's middle (the
     cell less a fifth on each side, so grid lines stay out) is sampled. Of
     the two colours most cells have, the background is the one whose
     cells make the biggest touching region. A cell is marked when at
     least a fifth of its middle is another colour, so a filled cell and a
     cell holding a symbol (a dot, a cross) both count.
  3. Marked cells are joined into shapes, 8-connected. Two shapes with one
     blank cell between them (across, down or on a slant) are then joined
     when the joined shape is less drawn out than the rounder of the two:
     two halves of a bean split by its crease make a rounder bean, two
     whole beans a stitch apart make a longer blob and stay apart. Until
     2026-10-11 every one-cell gap was bridged, which fused beans set a
     stitch apart into bands. A
     shape of at least 8 cells is a bean, unless it is a band: one that
     runs from the left edge of the grid to the right, or is more than four
     times as long one way as the other in cells. Beans cut by the edge of
     the chart are only used when there is no whole one.

  is_chart        a grid of at least 10 stitches by 10 rows. A repeat chart
                  is fine; a picture with no grid is not a chart.
  motif_in_cells  at least one bean made of marked cells, and no filled
                  shape with curves or off-grid corners, bigger than a cell
                  and a half each way, laid over the grid. A bean drawn as a
                  smooth path on top of the grid does not say which stitches
                  to knit.
  cells_not_tall  the drawn cell is at least 0.95 times as wide as it is
                  tall. A chart with tall cells shows the fabric the wrong
                  way round, whatever its stitches are.
  bean_knits_true the beans as knitted are 1.3 to 1.8 times as long as they
                  are wide, about a real coffee bean. Fabric units: a stitch
                  is G wide and a row 1 tall, where G is the drawn width over
                  height of the cell if that is between 1.15 and 1.7 (the
                  chart's own gauge, measured as drawn) and 1.35 otherwise.
                  Length over width is the square root of the ratio of the
                  two spreads (principal axes) of the cell centres, so a
                  bean set at a slant is measured along its own length.
                  The median over all beans is the one judged. Left to the
                  eye (null) when the motif is drawn over the grid.
  has_legend      some text on the page says what the marks mean: "key",
                  "legend", MC/CC, main or contrast colour, colour A, bean
                  colour, or a mark set equal (=, :, or a dot as in
                  "A · oat") to knit, purl or a colour name. A title alone
                  does not count. The dot and the yarn names (oat,
                  espresso, ...) were added 2026-10-11, for two keys of
                  GPT-6.1 Sol's that were missed, and "knit, contrast" or
                  "purl / background" for one of GLM 5.3 flashx's.

Row numbers, and which side they sit on, are written down as `row_numbers`,
a hint and not a check. Everything it read is written out so a wrong verdict
can be traced.
"""
import math
import os
import re
import statistics
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter, deque

import numpy as np
from PIL import Image
from _grade import finish

DEFAULT_GAUGE = 1.35        # stitch width over row height, about 5 st to 7 rows
OWN_GAUGE = (1.15, 1.7)     # a drawn cell aspect in here is taken as the chart's gauge
BEAN = (1.3, 1.8)           # length over width of a coffee bean, as knitted
MIN_GRID = 10               # stitches and rows
MIN_BEAN = 8                # cells

src, out = sys.argv[1], sys.argv[2]
r = {"checks": {}}


def fail_all(why):
    for k in ("is_chart", "motif_in_cells", "cells_not_tall", "bean_knits_true", "has_legend"):
        r["checks"].setdefault(k, False)
    r["error"] = why
    finish(r, out)
    sys.exit()


if not os.path.exists(src) or os.path.getsize(src) == 0:
    fail_all("no file")

# --- the words ------------------------------------------------------------------
try:
    tree = ET.parse(src)
except ET.ParseError as e:
    fail_all(f"not readable XML: {e}")
local = lambda t: t.rsplit("}", 1)[-1]
words = [" ".join("".join(el.itertext()).split()) for el in tree.iter() if local(el.tag) == "text"]
words = [w for w in words if w]
LEGEND = re.compile(
    r"\b(?:legend|key)\b|\b(?:MC|CC)\b|\b(?:main|contrast(?:ing)?|background)\s+(?:colou?r|yarn)\b"
    r"|\b(?:colou?r|yarn)\s*[A-D1-4]\b|\bknit\s+(?:in|with)\b|\b(?:bean|crease)\s+(?:colou?r|yarn|stitch(?:es)?)\b"
    r"|[=:\u00b7\u2022]\s*(?:knit|purl|k|p|brown|dark|light|cream|beige|tan|white|black|ivory|natural|coffee|bean|background"
    r"|oat|oatmeal|ecru|grey|gray|espresso|latte|mocha|chocolate|caramel)\b"
    r"|\b(?:knit|purl)\s*[,/]\s*(?:contrast|main|background)\b",
    re.I)
r["legend_text"] = [w[:80] for w in words if LEGEND.search(w)][:6]
r["checks"]["has_legend"] = bool(r["legend_text"])

# --- the vector drawing -------------------------------------------------------
from svgelements import SVG, Shape, Path, Rect, Text, Line, Move, Close, CubicBezier, QuadraticBezier, Arc

try:
    svg = SVG.parse(src)
except Exception as e:
    fail_all(f"svgelements could not read it: {e}")
W, H = float(svg.width or 0), float(svg.height or 0)
if W <= 0 or H <= 0:
    fail_all("the SVG has no size")

rects, hseg, vseg, filled = [], [], [], []   # filled: (bbox, has_curve, corners)
texts = []
# A grid can also be a <pattern> tile filling one rectangle. Its tile size is
# the cell, read from the source, since the pattern itself is never drawn as
# shapes. Added 2026-10-11 for a chart drawn that way.
patterns = {}
for el in tree.iter():
    if local(el.tag) == "pattern" and el.get("id"):
        try:
            pw, ph = float(el.get("width", "0")), float(el.get("height", "0"))
        except ValueError:
            continue
        if pw > 0 and ph > 0:
            patterns[el.get("id")] = (pw, ph, el.get("patternUnits", "objectBoundingBox") == "userSpaceOnUse")
pattern_fills = []   # (bbox, tile width, tile height)
for el in svg.elements():
    if isinstance(el, Rect):
        m_ = re.match(r"\s*url\(\s*#([^)\s]+)\s*\)", str(el.values.get("fill", "")))
        if m_ and m_.group(1) in patterns:
            bb = abs(Path(el)).bbox()
            pw, ph, user = patterns[m_.group(1)]
            if bb:
                if not user:
                    pw, ph = pw * (bb[2] - bb[0]), ph * (bb[3] - bb[1])
                sc = el.transform
                pattern_fills.append((bb, pw * math.hypot(sc.a, sc.b), ph * math.hypot(sc.c, sc.d)))
            continue
    if isinstance(el, Text):
        bb = el.bbox()
        if bb and el.text and el.text.strip():
            texts.append((el.text.strip(), bb[0], bb[1]))
        continue
    if not isinstance(el, Shape):
        continue
    if el.values.get("visibility") == "hidden" or el.values.get("display") == "none":
        continue
    try:
        p = abs(Path(el))
    except Exception:
        continue
    has_fill = el.fill is not None and el.fill.value is not None and el.fill.alpha > 0
    if isinstance(el, Rect) and (el.rx or el.ry) and abs(el.transform.b) < 1e-9 and abs(el.transform.c) < 1e-9:
        # A cell with rounded corners is still a cell, if it is not turned.
        bb = p.bbox()
        if bb and bb[2] - bb[0] > 0.5 and bb[3] - bb[1] > 0.5:
            rects.append(bb)
            if has_fill:
                filled.append((bb, False, {(bb[0], bb[1]), (bb[2], bb[3])}))
        continue
    for sub in p.as_subpaths():
        segs = [s for s in sub if not isinstance(s, (Move, Close))]
        if not segs:
            continue
        curve = any(isinstance(s, (CubicBezier, QuadraticBezier, Arc)) for s in segs)
        pts = []
        for s in segs:
            if s.start is not None:
                pts.append((s.start.x, s.start.y))
            pts.append((s.end.x, s.end.y))
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        bb = (min(xs), min(ys), max(xs), max(ys))
        hv = not curve and all(isinstance(s, Line) and (abs(s.start.x - s.end.x) < 1e-6 or abs(s.start.y - s.end.y) < 1e-6) for s in segs)
        corners = {(round(x, 3), round(y, 3)) for x, y in pts}
        if hv and len(corners) == 4 and bb[2] - bb[0] > 0.5 and bb[3] - bb[1] > 0.5:
            rects.append(bb)
        elif hv:
            for s in segs:
                if abs(s.start.y - s.end.y) < 1e-6 and abs(s.start.x - s.end.x) > 0.5:
                    hseg.append((s.start.y, min(s.start.x, s.end.x), max(s.start.x, s.end.x)))
                elif abs(s.start.x - s.end.x) < 1e-6 and abs(s.start.y - s.end.y) > 0.5:
                    vseg.append((s.start.x, min(s.start.y, s.end.y), max(s.start.y, s.end.y)))
        if has_fill:
            filled.append((bb, curve, corners))


def grid_from_rects():
    """The biggest touching block of same-size rectangles on one lattice."""
    if not rects:
        return None
    size = Counter((round(b[2] - b[0], 1), round(b[3] - b[1], 1)) for b in rects)
    (cw, ch), n = size.most_common(1)[0]
    if n < 20:
        return None
    cells = [b for b in rects if abs((b[2] - b[0]) - cw) < 0.03 * cw and abs((b[3] - b[1]) - ch) < 0.03 * ch]
    # Cells may be drawn with a gap between them, so the step from one cell
    # to the next is the pitch: the commonest gap between neighbouring
    # positions, if it is no more than a third bigger than the cell.
    def pitch(pos, size):
        u = sorted({round(v, 1) for v in pos})
        steps = Counter(round(b - a, 1) for a, b in zip(u, u[1:]) if size * 0.97 <= b - a <= size * 1.34)
        return steps.most_common(1)[0][0] if steps else size
    cw, ch = pitch([b[0] for b in cells], cw), pitch([b[1] for b in cells], ch)
    # The lattice is set by where most cells sit, so a legend swatch of the
    # same size off to one side does not shift it.
    x0 = Counter(round(b[0] % cw, 1) % round(cw, 1) for b in cells).most_common(1)[0][0]
    y0 = Counter(round(b[1] % ch, 1) % round(ch, 1) for b in cells).most_common(1)[0][0]
    lat = set()
    for b in cells:
        i, j = (b[0] - x0) / cw, (b[1] - y0) / ch
        if abs(i - round(i)) < 0.15 and abs(j - round(j)) < 0.15:
            lat.add((round(i), round(j)))
    best, seen = set(), set()
    for start in lat:
        if start in seen:
            continue
        comp, q = set(), deque([start])
        seen.add(start)
        while q:
            a = q.popleft(); comp.add(a)
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (a[0] + d[0], a[1] + d[1])
                if nb in lat and nb not in seen:
                    seen.add(nb); q.append(nb)
        if len(comp) > len(best):
            best = comp
    if not best:
        return None
    i0, i1 = min(a[0] for a in best), max(a[0] for a in best)
    j0, j1 = min(a[1] for a in best), max(a[1] for a in best)
    return dict(source="cells", cw=cw, ch=ch, x0=x0 + i0 * cw, y0=y0 + j0 * ch, cols=i1 - i0 + 1, rows=j1 - j0 + 1)


def run_of_lines(segs):
    """Positions of long parallel strokes; the longest run at an even pitch."""
    if not segs:
        return None
    longest = max(s[2] - s[1] for s in segs)
    pos = sorted(s[0] for s in segs if s[2] - s[1] >= 0.5 * longest)
    merged = []
    for x in pos:
        if not merged or x - merged[-1] > 0.5:
            merged.append(x)
    if len(merged) < 3:
        return None
    gaps = Counter(round(b - a, 1) for a, b in zip(merged, merged[1:]))
    pitch = gaps.most_common(1)[0][0]
    if pitch <= 0:
        return None
    best, cur = (0, 0), (0, 0)
    for k in range(1, len(merged)):
        if abs(merged[k] - merged[k - 1] - pitch) < 0.1 * pitch:
            cur = (cur[0], k) if cur[1] == k - 1 else (k - 1, k)
            if cur[1] - cur[0] > best[1] - best[0]:
                best = cur
        else:
            cur = (k, k)
    return pitch, merged[best[0]], best[1] - best[0]


def grid_from_lines():
    v, h = run_of_lines(vseg), run_of_lines(hseg)
    if not v or not h or v[2] < 1 or h[2] < 1:
        return None
    return dict(source="lines", cw=v[0], ch=h[0], x0=v[1], y0=h[1], cols=v[2], rows=h[2])


def grid_from_pattern():
    """The biggest rectangle filled with a pattern tile, the tile as the cell."""
    best = None
    for bb, pw, ph in pattern_fills:
        cols, rows = round((bb[2] - bb[0]) / pw), round((bb[3] - bb[1]) / ph)
        if cols >= 1 and rows >= 1 and (not best or cols * rows > best["cols"] * best["rows"]):
            best = dict(source="pattern", cw=(bb[2] - bb[0]) / cols, ch=(bb[3] - bb[1]) / rows,
                        x0=bb[0], y0=bb[1], cols=cols, rows=rows)
    return best


grids = [g for g in (grid_from_rects(), grid_from_lines()) if g]
# A pattern is only the grid when nothing drawn is: a page can have a
# patterned background as well as a chart.
if not any(g["cols"] >= MIN_GRID and g["rows"] >= MIN_GRID for g in grids):
    grids += [g for g in (grid_from_pattern(),) if g]
if not grids:
    r["checks"]["is_chart"] = False
    fail_all("no grid of cells found")
g = max(grids, key=lambda g: g["cols"] * g["rows"])
cw, ch, cols, rows = g["cw"], g["ch"], g["cols"], g["rows"]
r["grid"] = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in g.items()}
r["checks"]["is_chart"] = cols >= MIN_GRID and rows >= MIN_GRID
aspect = cw / ch
r["cell_aspect_drawn"] = round(aspect, 3)
r["checks"]["cells_not_tall"] = aspect >= 0.95
gauge = aspect if OWN_GAUGE[0] <= aspect <= OWN_GAUGE[1] else DEFAULT_GAUGE
r["gauge_used"] = round(gauge, 3)

# --- sample every cell from a rendering ---------------------------------------
zoom = max(1.0, 14.0 / min(cw, ch))
zoom = min(zoom, 6000.0 / max(W, H))
T = tempfile.mkdtemp()
png = os.path.join(T, "page.png")
rr = subprocess.run(["rsvg-convert", "-z", f"{zoom:.4f}", "-b", "white", src, "-o", png], capture_output=True, text=True, timeout=120)
if rr.returncode != 0 or not os.path.exists(png):
    fail_all("rsvg-convert failed: " + rr.stderr.strip()[:200])
img = np.asarray(Image.open(png).convert("RGB")).astype(int)
sx, sy = img.shape[1] / W, img.shape[0] / H


def middle(i, j):
    x0, y0 = g["x0"] + i * cw, g["y0"] + j * ch
    a, b = int(round((x0 + 0.2 * cw) * sx)), int(round((x0 + 0.8 * cw) * sx))
    c, d = int(round((y0 + 0.2 * ch) * sy)), int(round((y0 + 0.8 * ch) * sy))
    patch = img[max(c, 0):max(d, c + 1), max(a, 0):max(b, a + 1)]
    return patch.reshape(-1, 3)


patches = [[middle(i, j) for i in range(cols)] for j in range(rows)]
medians = Counter()
for row in patches:
    for p in row:
        if len(p):
            medians[tuple((np.median(p, axis=0) // 24).astype(int))] += 1
if not medians:
    fail_all("the grid lies outside the page")
keys = [[tuple((np.median(p, axis=0) // 24).astype(int)) if len(p) else None for p in row] for row in patches]


def biggest_region(key):
    """The most cells of this colour that touch one another."""
    seen, best = set(), 0
    for j in range(rows):
        for i in range(cols):
            if keys[j][i] != key or (j, i) in seen:
                continue
            n, q = 0, deque([(j, i)])
            seen.add((j, i))
            while q:
                a, b = q.popleft(); n += 1
                for na, nb in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                    if 0 <= na < rows and 0 <= nb < cols and keys[na][nb] == key and (na, nb) not in seen:
                        seen.add((na, nb)); q.append((na, nb))
            best = max(best, n)
    return best


# The background is the colour that runs between the motifs as one piece,
# of the two commonest. Until 2026-10-11 it was the commonest alone, which
# took the beans for the background on a chart with more bean than ground.
bg_key = max((k for k, _ in medians.most_common(2)), key=biggest_region)
bg = np.array([np.median(p, axis=0) for row in patches for p in row if len(p) and tuple((np.median(p, axis=0) // 24).astype(int)) == bg_key]).mean(axis=0)
marked = np.zeros((rows, cols), bool)
for j in range(rows):
    for i in range(cols):
        p = patches[j][i]
        if len(p):
            marked[j, i] = (np.sqrt(((p - bg) ** 2).sum(axis=1)) > 60).mean() >= 0.2
r["background_rgb"] = [int(v) for v in bg]
r["marked_cells"] = int(marked.sum())

def fabric_ratio(cells):
    """Length over width as knitted, from the two spreads of the cell centres."""
    if len(cells) < 3:
        return float("inf")
    pts = np.array([(c[1] * gauge, c[0]) for c in cells], float)
    ev = np.sort(np.linalg.eigvalsh(np.cov(pts.T)))
    return math.sqrt(ev[1] / ev[0]) if ev[0] > 1e-9 else float("inf")


# Shapes of touching marked cells, corners included.
label = -np.ones((rows, cols), int)
pieces = []
for j in range(rows):
    for i in range(cols):
        if not marked[j, i] or label[j, i] >= 0:
            continue
        comp, q = [], deque([(j, i)])
        label[j, i] = len(pieces)
        while q:
            a, b = q.popleft(); comp.append((a, b))
            for da in (-1, 0, 1):
                for db in (-1, 0, 1):
                    na, nb = a + da, b + db
                    if 0 <= na < rows and 0 <= nb < cols and marked[na, nb] and label[na, nb] < 0:
                        label[na, nb] = len(pieces); q.append((na, nb))
        pieces.append(comp)

# The blank cells that sit between two different shapes, one cell wide: where
# a crease might be.
gaps = {}
for j in range(rows):
    for i in range(cols):
        if marked[j, i]:
            continue
        for (a1, b1), (a2, b2) in (((j, i - 1), (j, i + 1)), ((j - 1, i), (j + 1, i)),
                                   ((j - 1, i - 1), (j + 1, i + 1)), ((j - 1, i + 1), (j + 1, i - 1))):
            if 0 <= a1 < rows and 0 <= a2 < rows and 0 <= b1 < cols and 0 <= b2 < cols \
                    and marked[a1, b1] and marked[a2, b2] and label[a1, b1] != label[a2, b2]:
                pair = tuple(sorted((label[a1, b1], label[a2, b2])))
                gaps.setdefault(pair, set()).add((j, i))

# Join across a gap only when that makes the shape rounder than either part
# was: a bean's two halves do, two whole beans side by side do not.
group = {k: k for k in range(len(pieces))}
cells_of = {k: list(p) for k, p in enumerate(pieces)}
def root(k):
    while group[k] != k:
        k = group[k]
    return k
joined = True
while joined:
    joined = False
    for (p, q), between in sorted(gaps.items(), key=lambda kv: -len(kv[1])):
        a, b = root(p), root(q)
        if a == b:
            continue
        both = cells_of[a] + cells_of[b] + [c for c in between if c not in set(cells_of[a]) | set(cells_of[b])]
        if fabric_ratio(both) < min(fabric_ratio(cells_of[a]), fabric_ratio(cells_of[b])):
            group[b] = a
            cells_of[a] = both
            del cells_of[b]
            joined = True
# A crease that does not split its bean is still part of it: a blank cell
# with the same shape on both sides of it is filled in.
shapes = []
for comp in cells_of.values():
    own = set(comp)
    fill = set()
    for j in range(min(c[0] for c in own), max(c[0] for c in own) + 1):
        for i in range(min(c[1] for c in own), max(c[1] for c in own) + 1):
            if (j, i) not in own and any((j + da, i + db) in own and (j - da, i - db) in own
                                         for da, db in ((0, 1), (1, 0), (1, 1), (1, -1))):
                fill.add((j, i))
    shapes.append(list(own | fill))

beans, cut = [], []
for comp in shapes:
    if len(comp) < MIN_BEAN:
        continue
    js, is_ = [c[0] for c in comp], [c[1] for c in comp]
    w, h = max(is_) - min(is_) + 1, max(js) - min(js) + 1
    if (min(is_) == 0 and max(is_) == cols - 1) or w > 4 * h or h > 4 * w:
        continue  # a band, a border or ribbing
    ratio = fabric_ratio(comp)
    rec = {"stitches": w, "rows": h, "cells": len(comp), "fabric_ratio": round(ratio, 2)}
    edge = min(is_) == 0 or max(is_) == cols - 1 or min(js) == 0 or max(js) == rows - 1
    (cut if edge else beans).append(rec)
if not beans:
    beans = cut
r["beans"] = beans[:12]

# A filled shape with curves or off-lattice corners, more than a cell and a
# half each way, inside the grid: a picture laid over the chart.
gx0, gy0, gx1, gy1 = g["x0"], g["y0"], g["x0"] + cols * cw, g["y0"] + rows * ch
def on_lattice(x, y):
    i, j = (x - gx0) / cw, (y - gy0) / ch
    return abs(i - round(i)) < 0.15 and abs(j - round(j)) < 0.15
overlay = []
for bb, curve, corners in filled:
    bw, bh = bb[2] - bb[0], bb[3] - bb[1]
    if bw < 1.5 * cw or bh < 1.5 * ch or bw * bh > 0.9 * (gx1 - gx0) * (gy1 - gy0):
        continue
    if bb[0] < gx0 - 0.5 * cw or bb[2] > gx1 + 0.5 * cw or bb[1] < gy0 - 0.5 * ch or bb[3] > gy1 + 0.5 * ch:
        continue
    if curve or not all(on_lattice(x, y) for x, y in corners):
        overlay.append([round(v, 1) for v in bb])
r["overlay_shapes"] = overlay[:5]

r["checks"]["motif_in_cells"] = bool(beans) and not overlay
if overlay:
    r["checks"]["bean_knits_true"] = None
elif beans:
    med = statistics.median(b["fabric_ratio"] for b in beans)
    r["bean_ratio_knitted"] = round(med, 2)
    r["checks"]["bean_knits_true"] = BEAN[0] <= med <= BEAN[1]
else:
    r["checks"]["bean_knits_true"] = False

# --- row numbers, a hint ------------------------------------------------------
left = sum(1 for t, x, y in texts if t.isdigit() and x < gx0 and gy0 <= y <= gy1 + ch)
right = sum(1 for t, x, y in texts if t.isdigit() and x > gx1 - 1 and gy0 <= y <= gy1 + ch)
r["row_numbers"] = {"left": left, "right": right}

problems = []
if not r["checks"]["is_chart"]:
    problems.append(f"grid only {cols} by {rows}")
if overlay:
    problems.append("motif drawn as a picture over the grid")
elif not beans:
    problems.append("no bean made of cells")
if not r["checks"]["cells_not_tall"]:
    problems.append(f"cells drawn tall ({aspect:.2f} wide to 1 tall)")
if r.get("bean_ratio_knitted") is not None and not r["checks"]["bean_knits_true"]:
    problems.append(f"bean knits {r['bean_ratio_knitted']} long to 1 wide at gauge {gauge:.2f}")
if not r["checks"]["has_legend"]:
    problems.append("no legend")

# finish() counts a check as passed only when it is true; a null check is
# left to the eye, so it is left out of the verdict (as in exploded.py).
r["undecided"] = [k for k, v in r["checks"].items() if v is None]
r["checks"] = {k: v for k, v in r["checks"].items() if v is not None}
if problems:
    r["detail"] = "; ".join(problems)
if r["undecided"]:
    r["detail"] = (r.get("detail") or "passed what it measured") + "; left to the eye: " + ", ".join(r["undecided"])
finish(r, out)
