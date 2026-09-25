#!/usr/bin/env python3
"""Where every label in a three-set Venn diagram actually landed.

Compiles the TeX, reads the circles back out of the PDF as vector paths and
the words with their boxes, then asks which circles contain each drink. The
answer is a set of memberships, so a drink is either in its region or not.

Which circle is which set comes from the set names: each name goes to the
circle whose centre is nearest, over the assignment with the least total
distance. The assignment is printed so a person can see it was the right one.
"""
import itertools, os, re, shutil, subprocess, sys, tempfile
from _grade import finish

E, M, C = "Has espresso", "Has milk", "Served cold"
SETS = (E, M, C)
# Ground truth: which sets each drink belongs to.
DRINKS = {
    "short black": {E},
    "babyccino": {M},
    "cold brew": {C},
    "flat white": {E, M},
    "iced long black": {E, C},
    "milkshake": {M, C},
    "iced latte": {E, M, C},
    "pour-over": set(),
}

src, out = sys.argv[1], sys.argv[2]
r = {"checks": {}}
T = tempfile.mkdtemp()
shutil.copy(src, os.path.join(T, "doc.tex"))


def run(*cmd):
    return subprocess.run(cmd, cwd=T, capture_output=True, text=True, timeout=120)


b = run("pdflatex", "-interaction=nonstopmode", "-halt-on-error", "doc.tex")
r["checks"]["compiles"] = os.path.exists(os.path.join(T, "doc.pdf")) and b.returncode == 0
if not r["checks"]["compiles"]:
    r["error"] = "pdflatex failed"
    finish(r, out); sys.exit()

run("pdftocairo", "-svg", "-f", "1", "-l", "1", "doc.pdf", "page.svg")
run("pdftotext", "-bbox", "-f", "1", "-l", "1", "doc.pdf", "words.html")

# --- circles: the largest closed paths drawn only with curves ---------------
from svgelements import SVG, Path, CubicBezier, QuadraticBezier, Arc, Move, Close, Line
from shapely.geometry import Polygon, Point, box

# cairo writes width="...pt" over a viewBox already in points; dropping the unit
# keeps svgelements from rescaling to 96 dpi, so shapes and words share units.
svg = open(os.path.join(T, "page.svg")).read()
svg = re.sub(r"<svg[^>]*>", lambda m: re.sub(r'="([\d.]+)pt"', r'="\1"', m.group(0)), svg, count=1)
open(os.path.join(T, "page.svg"), "w").write(svg)
shapes = []
for el in SVG.parse(os.path.join(T, "page.svg")).elements():
    if not isinstance(el, Path) or not len(el):
        continue
    segs = [s for s in abs(el).segments() if not isinstance(s, (Move, Close))]  # abs() applies the transform
    curves = [s for s in segs if isinstance(s, (CubicBezier, QuadraticBezier, Arc))]
    lines = [s for s in segs if isinstance(s, Line) and s.length() > 0.5]
    if len(curves) < 4 or lines:
        continue
    pts = [(p.x, p.y) for s in curves for p in (s.point(t / 16) for t in range(16))]
    try:
        poly = Polygon(pts).buffer(0)
    except Exception:
        continue
    x0, y0, x1, y1 = poly.bounds
    if min(x1 - x0, y1 - y0) < 40 or poly.area < 0.6 * (x1 - x0) * (y1 - y0):
        continue  # glyphs and small decoration; an ellipse fills ~78% of its box
    if any(poly.symmetric_difference(q).area < 0.02 * poly.area for q in shapes):
        continue  # the same circle drawn twice, e.g. a fill and a stroke
    shapes.append(poly)
shapes.sort(key=lambda p: -p.area)
circles = shapes[:3]
r["circles_found"] = len(shapes)

seven = False
if len(circles) == 3:
    a, b_, c = circles
    regions = [
        a - b_ - c, b_ - a - c, c - a - b_,
        a.intersection(b_) - c, a.intersection(c) - b_, b_.intersection(c) - a,
        a.intersection(b_).intersection(c),
    ]
    seven = all(g.area > 100 for g in regions)  # 100 pt^2, room for a word
r["checks"]["seven_regions"] = seven

# --- words ------------------------------------------------------------------
words = []
for m in re.finditer(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>',
                     open(os.path.join(T, "words.html"), errors="replace").read()):
    x0, y0, x1, y1 = map(float, m.groups()[:4])
    t = re.sub(r"[^a-z]", "", m.group(5).lower().replace("&amp;", ""))
    words.append((t, (x0, y0, x1, y1)))


def find(phrase, used):
    """Every place the phrase occurs as consecutive words, as a union box."""
    target = re.sub(r"[^a-z ]", " ", phrase.lower()).split()
    hits = []
    for i in range(len(words)):
        # A word may carry a hyphenated pair ("pour-over" is one word in the PDF).
        j, k, boxes = i, 0, []
        while k < len(target) and j < len(words) and j not in used:
            w = words[j][0]
            joined = "".join(target[k:k + 2])
            if w == target[k]:
                k += 1
            elif len(target) > k + 1 and w == joined:
                k += 2
            else:
                break
            boxes.append(j); j += 1
        if k == len(target):
            bs = [words[n][1] for n in boxes]
            far = any(abs(bs[n + 1][1] - bs[n][1]) > 30 or abs(bs[n + 1][0] - bs[n][2]) > 60 for n in range(len(bs) - 1))
            if not far:
                hits.append((boxes, (min(x[0] for x in bs), min(x[1] for x in bs),
                                     max(x[2] for x in bs), max(x[3] for x in bs))))
    return hits


used = set()
titles = {}
for s in SETS:
    h = find(s, used)
    if h:
        used.update(h[0][0]); titles[s] = h[0][1]
r["checks"]["set_names"] = len(titles) == 3

# --- which circle is which set ---------------------------------------------
assign = None
if len(circles) == 3 and len(titles) == 3:
    def ctr(bx):
        return Point((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2)
    best = min(itertools.permutations(range(3)),
               key=lambda p: sum(ctr(titles[s]).distance(circles[p[i]].centroid) for i, s in enumerate(SETS)))
    assign = {s: circles[best[i]] for i, s in enumerate(SETS)}
    r["assignment"] = {s: [round(circles[best[i]].centroid.x), round(circles[best[i]].centroid.y)] for i, s in enumerate(SETS)}

# --- the drinks ---------------------------------------------------------------
placed, straddling, found = {}, [], True
for d, want in DRINKS.items():
    h = find(d, used)
    if not h:
        found = False; placed[d] = "missing"; continue
    verdicts = []
    for idx, bx in h:
        used.update(idx)
        if not assign:
            continue
        p = Point((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2)
        got = {s for s, c in assign.items() if c.contains(p)}
        verdicts.append("ok" if got == want else "in " + (" & ".join(sorted(got)) or "no circle"))
        # Clear of edges: no circle's outline runs through any of its words.
        # Word by word, because a two-line label's union box has empty corners.
        rects = [box(*words[n][1]) for n in idx]
        if any(c.boundary.intersects(q) for c in assign.values() for q in rects):
            straddling.append(d)
    bad = [v for v in verdicts if v != "ok"]
    placed[d] = (bad[0] if bad else "ok") + (f" ({len(h)} copies)" if len(h) > 1 else "")
r["placed"] = placed
r["straddling"] = sorted(set(straddling))
r["checks"]["drinks_found"] = found
r["checks"]["drinks_in_region"] = bool(assign) and found and all(v.startswith("ok") for v in placed.values())
r["checks"]["labels_clear_of_edges"] = bool(assign) and found and not straddling
problems = [f"{d} {v}" for d, v in placed.items() if not v.startswith("ok")]
problems += [f"{d} crosses a circle's edge" for d in r["straddling"]]
if problems:
    r["detail"] = "; ".join(problems)
finish(r, out)
