#!/usr/bin/env python3
"""Exploded assembly diagrams, graded from the SVG and its rendering.

Which object it is comes from EXPLODED_MEMBER, set by the small wrapper each
case names (exploded-v60.py and so on). What each part is called, the order
of the stack and which parts must fit which are in exploded-truth.json, next
to this file, so the model never sees them.

How a part is found:

  1. Labels. A leader is an open line with no fill, one end near some words
     and the other end away from them. The words nearest its start are the
     label; the part it names is read from them with the names listed in
     exploded-truth.json. A caption under the label is not read, so
     "Plunger: grip, shaft and rubber seal" labels the plunger and not the
     seal. A label can name two parts ("crank & knob").
  2. Shapes. The SVG is rendered with every word, leader and dashed line
     taken out, and on a transparent page, so soft shadows fall below the
     cut. Thin lines left over (rules, hatching) are worn away. What remains
     falls into separate shapes, since an exploded diagram draws its parts
     apart.
  3. Each label's leader ends on, or within a few pixels of, one shape:
     that shape is the part.

Where a part is: the middle of its shape. Its width and centre line are
read row by row from the longest unbroken run of ink in each row, so a
handle or a spout off to one side does not move them.

  parts   every listed part is named by a label that says what it is. A name
          that only says where it sits ("top plate") names nothing, and a
          caption under another part's label is not read. A part whose only label
          points at blank paper is left to the eye. Whether each named part
          is drawn as its own piece is also for the eye.
  order   the parts on the stack, top to bottom, in the listed order
  fit     each listed pair within its ratio of widths. Widths are outside
          widths, the only ones the drawing gives; the ratios in the truth
          file are written for that. Fits that are not widths are left to
          the eye and reported as null.
  axis    every part on the stack centred within 4% of the drawing's width
          of the stack's median centre
  labels  fails when a leader naming a part ends on blank paper. Whether
          every other leader ends on the part its label names needs to know
          what each shape is, which only the eye can tell, so a drawing with
          no such leader is left to the eye.

Everything it read is written out (labels, shapes, positions, widths), so a
wrong verdict can be traced to the step that went wrong.
"""
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import deque

import numpy as np
from PIL import Image

from _grade import finish

HERE = os.path.dirname(os.path.abspath(__file__))
SVG = "{http://www.w3.org/2000/svg}"
WIDTH = 1000        # rendering width in pixels
AXIS_TOL = 0.04     # of the drawing's width
SNAP = 0.03         # of the drawing's width, from a leader's end to its shape


# ── SVG geometry ────────────────────────────────────────────────────────────

def mat_mul(a, b):
    return (a[0] * b[0] + a[2] * b[1], a[1] * b[0] + a[3] * b[1],
            a[0] * b[2] + a[2] * b[3], a[1] * b[2] + a[3] * b[3],
            a[0] * b[4] + a[2] * b[5] + a[4], a[1] * b[4] + a[3] * b[5] + a[5])


def apply(m, x, y):
    return m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]


NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"


def parse_transform(s):
    m = (1, 0, 0, 1, 0, 0)
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", s or ""):
        v = [float(a) for a in re.findall(NUM, args)]
        if name == "translate":
            t = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale":
            t = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate":
            a = math.radians(v[0])
            c, s_ = math.cos(a), math.sin(a)
            t = (c, s_, -s_, c, 0, 0)
            if len(v) == 3:
                t = mat_mul(mat_mul((1, 0, 0, 1, v[1], v[2]), t), (1, 0, 0, 1, -v[1], -v[2]))
        elif name == "matrix" and len(v) == 6:
            t = tuple(v)
        else:
            continue
        m = mat_mul(m, t)
    return m


def path_points(d):
    """The points a path passes through, as subpaths: [(points, closed)]."""
    toks = re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|" + NUM, d or "")
    subs, pts, closed = [], [], False
    x = y = sx = sy = 0.0
    cmd, i = None, 0
    counts = dict(M=2, L=2, H=1, V=1, C=6, S=4, Q=4, T=2, A=7, Z=0)
    while i < len(toks):
        if re.match(r"[A-Za-z]", toks[i]):
            cmd = toks[i]
            i += 1
            if cmd in "Zz":
                closed = True
                x, y = sx, sy
                pts.append((x, y))
                continue
        if cmd is None:
            break
        n = counts[cmd.upper()]
        args = [float(t) for t in toks[i:i + n]]
        if len(args) < n:
            break
        i += n
        rel = cmd.islower()
        c = cmd.upper()
        if c == "M":
            if pts:
                subs.append((pts, closed))
            pts, closed = [], False
            x, y = (x + args[0], y + args[1]) if rel else (args[0], args[1])
            sx, sy = x, y
            pts.append((x, y))
            cmd = "l" if rel else "L"
            continue
        if c == "H":
            x = x + args[0] if rel else args[0]
        elif c == "V":
            y = y + args[0] if rel else args[0]
        else:
            ex, ey = args[-2], args[-1]
            if c in "CSQ":
                for k in range(0, n - 2, 2):
                    pts.append((x + args[k], y + args[k + 1]) if rel else (args[k], args[k + 1]))
            x, y = (x + ex, y + ey) if rel else (ex, ey)
        pts.append((x, y))
    if pts:
        subs.append((pts, closed))
    return subs


def css_rules(root):
    rules = {}
    for st in root.iter(SVG + "style"):
        for sel, body in re.findall(r"([^{}]+)\{([^}]*)\}", st.text or ""):
            for one in sel.split(","):
                one = one.strip()
                if one.startswith("."):
                    rules.setdefault(one[1:], {}).update(
                        {k.strip(): v.strip() for k, v in (p.split(":", 1) for p in body.split(";") if ":" in p)})
    return rules


def style_of(el, rules, inherited):
    s = dict(inherited)
    for c in (el.get("class") or "").split():
        s.update(rules.get(c, {}))
    for k in ("fill", "stroke", "stroke-width", "stroke-dasharray", "font-size", "font", "text-anchor", "letter-spacing", "display", "opacity"):
        if el.get(k) is not None:
            s[k] = el.get(k)
    for p in (el.get("style") or "").split(";"):
        if ":" in p:
            k, v = p.split(":", 1)
            s[k.strip()] = v.strip()
    return s


def font_size(s):
    v = s.get("font-size")
    if not v and s.get("font"):
        m = re.search(r"(" + NUM + r")px", s["font"])
        v = m and m.group(1)
    try:
        return float(re.findall(NUM, v)[0]) if v else 16.0
    except IndexError:
        return 16.0


def walk(root, rules):
    """Every drawable element with its transform and computed style."""
    out = []

    def go(el, m, st):
        tag = el.tag.replace(SVG, "")
        if tag in ("defs", "style", "title", "desc", "metadata", "clipPath", "mask", "pattern", "symbol",
                   "linearGradient", "radialGradient", "filter", "marker"):
            return
        m2 = mat_mul(m, parse_transform(el.get("transform")))
        st2 = {k: v for k, v in style_of(el, rules, st).items() if k not in ("opacity",)}
        out.append((el, tag, m2, st2))
        for c in el:
            go(c, m2, st2)
    go(root, (1, 0, 0, 1, 0, 0), {})
    return out


def text_of(el):
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


FONTS = ["/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
         "/System/Library/Fonts/Supplemental/Arial.ttf"]
_font = None


def text_width(t, fs):
    """Width of some words in Arial, or Liberation Sans, which has the same
    widths; a rough guess if neither is installed."""
    global _font
    if _font is None:
        from PIL import ImageFont
        _font = next((ImageFont.truetype(f, 100) for f in FONTS if os.path.exists(f)), False)
    return _font.getlength(t) * fs / 100 if _font else len(t) * fs * 0.6


def text_box(el, m, st):
    """A rough box for some words, from their position, size and length."""
    t = text_of(el)
    x = float((re.findall(NUM, el.get("x") or "0") or ["0"])[0])
    y = float((re.findall(NUM, el.get("y") or "0") or ["0"])[0])
    for sp in el.iter(SVG + "tspan"):
        if sp.get("x") is not None and not el.get("x"):
            x = float(re.findall(NUM, sp.get("x"))[0])
        if sp.get("y") is not None and not el.get("y"):
            y = float(re.findall(NUM, sp.get("y"))[0])
    fs = font_size(st)
    ls = st.get("letter-spacing")
    ls = float(re.findall(NUM, ls)[0]) if ls and re.findall(NUM, ls) else 0
    w = text_width(t, fs) + len(t) * ls
    anchor = st.get("text-anchor", "start")
    x0 = x - w if anchor == "end" else x - w / 2 if anchor == "middle" else x
    corners = [apply(m, a, b) for a in (x0, x0 + w) for b in (y - fs * 0.8, y + fs * 0.2)]
    xs, ys = [c[0] for c in corners], [c[1] for c in corners]
    return (min(xs), min(ys), max(xs), max(ys)), fs


def box_dist(b, p):
    dx = max(b[0] - p[0], 0, p[0] - b[2])
    dy = max(b[1] - p[1], 0, p[1] - b[3])
    return math.hypot(dx, dy)


# ── Reading the drawing ─────────────────────────────────────────────────────

def read_svg(path):
    tree = ET.parse(path)
    root = tree.getroot()
    vb = [float(v) for v in re.findall(NUM, root.get("viewBox") or "")]
    if len(vb) != 4:
        w = float(re.findall(NUM, root.get("width") or "1000")[0])
        h = float(re.findall(NUM, root.get("height") or "1000")[0])
        vb = [0, 0, w, h]
    rules = css_rules(root)
    els = walk(root, rules)
    texts, lines = [], []
    for el, tag, m, st in els:
        if tag == "text":
            t = text_of(el)
            if re.search(r"[A-Za-z]", t):
                box, fs = text_box(el, m, st)
                texts.append({"el": el, "text": t, "box": box, "size": fs})
        elif tag in ("line", "polyline", "path"):
            if st.get("display") == "none":
                continue
            if tag == "line":
                f = lambda k: float(re.findall(NUM, el.get(k) or "0")[0])
                subs = [([(f("x1"), f("y1")), (f("x2"), f("y2"))], False)]
            elif tag == "polyline":
                v = [float(a) for a in re.findall(NUM, el.get("points") or "")]
                subs = [(list(zip(v[0::2], v[1::2])), False)]
            else:
                subs = path_points(el.get("d"))
            fill = (st.get("fill") or ("none" if tag == "line" else "black")).strip()
            if len(subs) != 1 or subs[0][1]:
                continue
            # A fill only matters if the line encloses something: a line
            # element never does, and nor does a path that goes straight.
            pts0 = subs[0][0]
            area = abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts0, pts0[1:] + pts0[:1]))) / 2
            if tag != "line" and fill not in ("none", "transparent") and area > 1:
                continue
            sw = re.findall(NUM, st.get("stroke-width") or "1")
            if sw and float(sw[0]) * math.hypot(m[0], m[1]) > 3.5:
                continue
            pts = [apply(m, *p) for p in subs[0][0]]
            if len(pts) < 2 or len(pts) > 8:
                continue
            lines.append({"el": el, "pts": pts, "dashed": bool(st.get("stroke-dasharray")) and st.get("stroke-dasharray") != "none"})
    return tree, root, vb, rules, els, texts, lines


def block(texts, t0):
    """Some words and the lines stacked with them: a label and its caption."""
    out = [t0]
    for _ in range(3):
        for t in texts:
            if t in out or t["size"] > 1.6 * t0["size"]:
                continue
            for u in out:
                big = max(t["size"], u["size"])
                overlap = min(t["box"][2], u["box"][2]) - max(t["box"][0], u["box"][0])
                gap = max(t["box"][1] - u["box"][3], u["box"][1] - t["box"][3])
                # stacked lines, or words on the same line just apart (a
                # letter in a bubble, then the name)
                side = max(t["box"][0] - u["box"][2], u["box"][0] - t["box"][2])
                if (overlap > 0 and gap < 1.5 * big) or (gap < 0 and side < 2.5 * big):
                    out.append(t)
                    break
    return out


def find_leaders(texts, lines, vb, blank, on_ink):
    """Open lines with one end on blank paper near some words and the other
    end on the drawing, or close to it, or at least away from any words. The words nearest the start, and the
    lines stacked with them, are the label. Being on blank paper and on the
    drawing is read from a rendering with every word, open line and numbered
    bubble taken out, so a line drawn on a part (a pleat, a rib) is not a
    leader. A line longer than half the page, a rule, is not one either."""
    near = 0.08 * vb[2]
    leaders = []
    for ln in lines:
        a, b = ln["pts"][0], ln["pts"][-1]
        if math.dist(a, b) < 0.02 * vb[2] or not texts:
            continue
        xs, ys = [p[0] for p in ln["pts"]], [p[1] for p in ln["pts"]]
        if max(max(xs) - min(xs), max(ys) - min(ys)) > 0.45 * vb[2]:
            continue
        ends = []
        for start, end in ((a, b), (b, a)):
            t0 = min(texts, key=lambda t: box_dist(t["box"], start))
            # The far end is on the drawing, or at least not among words: a
            # leader that stops short of its part is still a leader.
            far = min(box_dist(t["box"], end) for t in texts)
            if box_dist(t0["box"], start) <= near and blank(start) and (on_ink(end) or far > near):
                ends.append((box_dist(t0["box"], start), start, end, t0))
        if not ends:
            continue
        d, start, end, t0 = min(ends, key=lambda e: e[0])
        leaders.append({"el": ln["el"], "start": start, "end": end, "label": block(texts, t0),
                        "t0": id(t0["el"]), "rank": (not on_ink(end), d)})
    # One leader to a label: the one that reaches the drawing, then the one
    # starting nearest the words. A second line leaving the same words is an
    # arrow or a rule, not another leader.
    best = {}
    for l in leaders:
        if l["t0"] not in best or l["rank"] < best[l["t0"]]["rank"]:
            best[l["t0"]] = l
    return list(best.values())


def box_dist_min(texts, p):
    return min((box_dist(t["box"], p) for t in texts), default=1e9)


GENERIC = {"plate", "plates", "disc", "disk", "piece", "part", "assembly", "unit", "insert", "element", "component", "set", "filter", "ring"}


def name_parts(text, names):
    """The parts some words name. Words in brackets, and words after "with",
    "for" and the like, are left out when what comes before names a part.
    Each phrase names one part: the one named last, since English puts the
    head noun last ("lid knob" is a knob, "filter cap" is a cap), the more
    specific name winning a tie ("outer conical burr" is the outer burr).
    Phrases are split at "&", "and", "+", "/", "," and "·", so "crank &
    knob" names both."""
    def head(phrase):
        s = " " + phrase + " "
        # The name has to reach the last word, the head noun ("hopper lid"
        # is a lid, not the hopper), unless that word only says what kind
        # of thing it is ("cross plate", "funnel filter").
        words = list(re.finditer(r"[a-z0-9]+", s))
        reach = words[-1].start() if words and words[-1].group() not in GENERIC else 0
        best = None
        for i, (part, rx) in enumerate(names):
            for m in re.finditer(rx, s):
                if m.end() <= reach:
                    continue
                if best is None or m.end() > best[0] or (m.end() == best[0] and i < best[1]):
                    best = (m.end(), i, part)
        return best and best[2]
    found = []
    for phrase in re.split(r"\s*(?:&|\band\b|\+|/|,|·|•)\s*", text.lower()):
        short = re.split(r"\s+(?:with|for|on|of|in|into|to|at|from|under|over|inside)\s+", re.sub(r"\(.*?\)|\(.*$", " ", phrase))[0]
        part = head(short) or head(phrase)
        if part and part not in found:
            found.append(part)
    return found


def render_shapes(tree, root, vb, els, leaders, texts, also=()):
    """Render with the words and leaders taken out; return the label image."""
    drop = {id(t["el"]) for t in texts} | {id(l["el"]) for l in leaders} | {id(e) for e in also}
    parent = {c: p for p in root.iter() for c in p}
    for el, tag, m, st in els:
        if tag == "text":
            drop.add(id(el))
        dash = st.get("stroke-dasharray")
        if tag in ("line", "path", "polyline") and dash and dash != "none" and (st.get("fill") in ("none", None) or tag == "line"):
            drop.add(id(el))
        # A long straight thin line is an axis line or a rule, and would
        # join the parts it runs past into one shape.
        if tag in ("line", "path", "polyline"):
            if tag == "line":
                g = lambda k: float((re.findall(NUM, el.get(k) or "0") or ["0"])[0])
                pts = [apply(m, g("x1"), g("y1")), apply(m, g("x2"), g("y2"))]
            elif tag == "polyline":
                v = [float(a) for a in re.findall(NUM, el.get("points") or "")]
                pts = [apply(m, *q) for q in zip(v[0::2], v[1::2])]
            else:
                subs = path_points(el.get("d"))
                pts = [apply(m, *q) for q in subs[0][0]] if len(subs) == 1 and not subs[0][1] else []
            sw = re.findall(NUM, st.get("stroke-width") or "1")
            if len(pts) >= 2 and sw and float(sw[0]) <= 3:
                a, b = pts[0], pts[-1]
                L = math.dist(a, b)
                straight = L > 0 and all(abs((b[0] - a[0]) * (q[1] - a[1]) - (b[1] - a[1]) * (q[0] - a[0])) / L < 1.5 for q in pts)
                if straight and L > 0.25 * min(vb[2], vb[3]):
                    drop.add(id(el))
        if tag in ("rect", "path", "polygon") and el is not root:
            # A page or a panel behind everything: anything over a third of
            # the page on both sides.
            if tag == "rect":
                g = lambda k, d="0": float((re.findall(NUM, el.get(k) or d) or [d])[0])
                w, h = g("width"), g("height")
                if el.get("width", "").endswith("%"):
                    w = vb[2] * w / 100
                if el.get("height", "").endswith("%"):
                    h = vb[3] * h / 100
                p1, p2 = apply(m, g("x"), g("y")), apply(m, g("x") + w, g("y") + h)
                if abs(p2[0] - p1[0]) > vb[2] / 3 and abs(p2[1] - p1[1]) > vb[3] / 3:
                    drop.add(id(el))
            elif tag == "path":
                pts = [apply(m, *p) for sub in path_points(el.get("d")) for p in sub[0]]
                if pts:
                    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                    if max(xs) - min(xs) > vb[2] * 0.9 and max(ys) - min(ys) > vb[3] * 0.9:
                        drop.add(id(el))
        if tag == "circle":
            r = float((re.findall(NUM, el.get("r") or "0") or ["0"])[0])
            c = apply(m, float((re.findall(NUM, el.get("cx") or "0") or ["0"])[0]), float((re.findall(NUM, el.get("cy") or "0") or ["0"])[0]))
            if r <= 6 and any(math.dist(c, l["end"]) <= r + 3 for l in leaders):
                drop.add(id(el))
            # A numbered bubble at a label's start.
            if any(math.dist(c, l["start"]) <= r + 4 for l in leaders) and r <= 20:
                drop.add(id(el))
    for el in list(root.iter()):
        if id(el) in drop and el in parent:
            parent[el].remove(el)
    with tempfile.TemporaryDirectory() as t:
        s, p = os.path.join(t, "s.svg"), os.path.join(t, "s.png")
        tree.write(s)
        r = subprocess.run(["rsvg-convert", "-w", str(WIDTH), "-b", "transparent", s, "-o", p], capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return None, None, r.stderr.strip()[:200]
        img = np.asarray(Image.open(p).convert("RGBA"))
    scale = img.shape[1] / vb[2]
    ink = img[:, :, 3] > 70
    # Wear away hairlines, then grow back.
    ink = dilate(erode(ink, 1), 1) & ink
    # Then close gaps of a few pixels, so a coil or a mesh drawn as many
    # thin strokes comes out as one shape.
    ink = erode(dilate(ink, 3), 3)
    labels, n = components(ink)
    if os.environ.get("EXPLODED_DEBUG"):
        rng = np.random.default_rng(1)
        pal = np.vstack([[255, 255, 255], rng.integers(30, 220, (n, 3))]).astype(np.uint8)
        Image.fromarray(pal[labels]).save(os.environ["EXPLODED_DEBUG"])
    return labels, n, scale


def erode(a, k):
    for _ in range(k):
        b = a.copy()
        b[1:, :] &= a[:-1, :]
        b[:-1, :] &= a[1:, :]
        b[:, 1:] &= a[:, :-1]
        b[:, :-1] &= a[:, 1:]
        a = b
    return a


def dilate(a, k):
    for _ in range(k):
        b = a.copy()
        b[1:, :] |= a[:-1, :]
        b[:-1, :] |= a[1:, :]
        b[:, 1:] |= a[:, :-1]
        b[:, :-1] |= a[:, 1:]
        a = b
    return a


def components(ink):
    h, w = ink.shape
    lab = np.zeros((h, w), dtype=np.int32)
    n = 0
    ys, xs = np.nonzero(ink)
    for y0, x0 in zip(ys, xs):
        if lab[y0, x0]:
            continue
        n += 1
        lab[y0, x0] = n
        q = deque([(y0, x0)])
        while q:
            y, x = q.popleft()
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1), (y + 1, x + 1), (y - 1, x - 1), (y + 1, x - 1), (y - 1, x + 1)):
                if 0 <= yy < h and 0 <= xx < w and ink[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = n
                    q.append((yy, xx))
    return lab, n


def shape_at(lab, p, scale):
    x, y = int(round(p[0] * scale)), int(round(p[1] * scale))
    snap = int(SNAP * lab.shape[1])
    h, w = lab.shape
    best, bd = 0, 1e9
    for yy in range(max(0, y - snap), min(h, y + snap + 1)):
        for xx in range(max(0, x - snap), min(w, x + snap + 1)):
            if lab[yy, xx]:
                d = math.hypot(xx - x, yy - y)
                if d < bd:
                    best, bd = lab[yy, xx], d
    return int(best)


def fill_holes(mask):
    """The shape with anything it encloses filled in, so a ring drawn as an
    outline measures as wide as it is."""
    ys, xs = np.nonzero(mask)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    sub = mask[y0:y1, x0:x1]
    out, _ = components(np.pad(~sub, 1, constant_values=True))
    edge = set(np.unique(np.concatenate([out[0], out[-1], out[:, 0], out[:, -1]]))) - {0}
    inside = (out > 0) & ~np.isin(out, list(edge))
    filled = mask.copy()
    filled[y0:y1, x0:x1] |= inside[1:-1, 1:-1]
    return filled


def measure(mask, scale, prior=None):
    """Middle, centre line and width of one shape, in SVG units.

    The centre line is the one the shape is most nearly mirrored about, so
    a handle or a spout on one side does not pull it over. The width of a
    row is twice its reach on the shorter side of that line, so a handle
    does not widen it either. Anything the shape encloses is filled first, so a ring
    drawn as an outline measures as wide as it is."""
    ys, xs = np.nonzero(mask)
    y0, x0 = ys.min(), xs.min()
    # The mirror line is found on the shape as drawn, where a handle's loop
    # is a thin outline that counts for little; the widths on the shape
    # filled in.
    raw = mask[y0:ys.max() + 1, x0:xs.max() + 1].astype(np.float64)
    mask = fill_holes(mask)
    sub = mask[y0:ys.max() + 1, x0:xs.max() + 1]
    n = sub.shape[1]
    f = np.fft.rfft(raw, 2 * n, axis=1)
    score = np.fft.irfft(f * f, 2 * n, axis=1).sum(axis=0)[:2 * n - 1]
    centre = np.argmax(score) / 2
    if prior is not None:
        # A part with a handle is nearly as well mirrored about its body as
        # about body and handle together: of the lines it is mirrored about
        # at least 60% as well as the best, take the one nearest the stack's.
        peaks = [i for i in range(1, len(score) - 1)
                 if score[i] >= score[i - 1] and score[i] >= score[i + 1] and score[i] >= 0.6 * score.max()]
        want = (prior * scale - x0) * 2
        if peaks:
            centre = min(peaks, key=lambda i: abs(i - want)) / 2
    widths = []
    for row in sub:
        cols = np.nonzero(row)[0]
        if not len(cols) or cols[0] > centre or cols[-1] < centre:
            continue
        widths.append(2 * min(centre - cols[0], cols[-1] - centre) + 1)
    g = lambda v: round(float(v) / scale, 1)
    # The width most rows share, among rows at least half the widest, so a
    # spout or a lip across a few rows does not count, and neither does
    # the taper at the top and bottom of a disc seen at an angle.
    width = 0.0
    if widths:
        top = max(widths)
        wide = [w for w in widths if w >= top / 2]
        step = max(1.0, 0.02 * top)
        bins = {}
        for w in wide:
            bins.setdefault(int(w // step), []).append(w)
        k = max(bins, key=lambda b: (len(bins[b]) + len(bins.get(b - 1, [])) + len(bins.get(b + 1, [])), b))
        width = max(bins[k])
    return {
        "top": g(ys.min()), "bottom": g(ys.max()), "left": g(xs.min()), "right": g(xs.max()),
        "middle": g((ys.min() + ys.max()) / 2),
        "centre": g(x0 + centre),
        "width": g(width),
    }


def split_sideways(mask, x_on, x_off):
    """Cut a part off the side of a stack part (a handle off a portafilter)
    at the narrowest column between their leader ends. Returns the stack
    part's piece."""
    cols = mask.sum(axis=0)
    lo, hi = int(min(x_on, x_off)) + 1, int(max(x_on, x_off))
    if hi <= lo:
        return mask
    c = lo + int(np.argmin(cols[lo:hi]))
    m = mask.copy()
    if x_off > x_on:
        m[:, c:] = False
    else:
        m[:, :c] = False
    return m


def split(mask, ys):
    """Cut one shape into pieces at its narrowest row between each pair of
    leader ends, top to bottom. Returns one mask per leader end."""
    rows = mask.sum(axis=1)
    cuts = []
    for a, b in zip(ys, ys[1:]):
        lo, hi = int(min(a, b)) + 1, int(max(a, b))
        if hi <= lo:
            cuts.append(None)
            continue
        seg = rows[lo:hi]
        # the narrowest row that still has ink, or the first empty one
        cuts.append(lo + int(np.argmin(seg)))
    pieces, top = [], 0
    for c in cuts + [mask.shape[0]]:
        if c is None:
            pieces.append(None)
            continue
        m = np.zeros_like(mask)
        m[top:c] = mask[top:c]
        pieces.append(m)
        top = c
    return pieces


# ── Grading ─────────────────────────────────────────────────────────────────

def grade(src, member, truth):
    r = {"member": member, "checks": {}}
    names = [(p, rx) for p, rx in truth["names"]]
    parts = truth["parts"]
    try:
        tree, root, vb, rules, els, texts, lines = read_svg(src)
    except (ET.ParseError, OSError, ValueError) as e:
        r["error"] = f"could not read the SVG: {e}"
        return r
    # First pass: every word and open line out, to see where blank paper is.
    # Numbered bubbles are taken out too, since a leader may start at one.
    bubbles = [el for el, tag, m, st in els if tag == "circle" and float((re.findall(NUM, el.get("r") or "0") or ["0"])[0]) <= 0.02 * vb[2]]
    # Only lines with an end near some words could be leaders; the rest are
    # drawing and stay in.
    near = 0.08 * vb[2]
    maybe = [l["el"] for l in lines if texts and min(box_dist(t["box"], p) for t in texts for p in (l["pts"][0], l["pts"][-1])) <= near]
    lab0, _, sc0 = render_shapes(tree, root, vb, els, [], texts, maybe + bubbles)
    if lab0 is None:
        r["error"] = f"could not render: {sc0}"
        return r
    def blank(p):
        x, y = int(round(p[0] * sc0)), int(round(p[1] * sc0))
        h, w = lab0.shape
        y0, y1, x0, x1 = max(0, y - 2), min(h, y + 3), max(0, x - 2), min(w, x + 3)
        return not lab0[y0:y1, x0:x1].any()
    on_ink = lambda p: bool(shape_at(lab0, p, sc0))
    tree, root, vb, rules, els, texts, lines = read_svg(src)
    leaders = find_leaders(texts, lines, vb, blank, on_ink)
    lab, n, scale = render_shapes(tree, root, vb, els, leaders, texts)
    if lab is None:
        r["error"] = f"could not render: {scale}"
        return r

    # Each leader: its label, the parts named, the shape it ends on.
    read = []
    for l in leaders:
        # The largest line of the label, the nearest of equals; a caption
        # under it is not read.
        label = min(l["label"], key=lambda t: (-round(t["size"], 1), box_dist(t["box"], l["start"])))
        named = name_parts(re.sub(r"^\s*\d+\s*[/.)·:-]?\s*", "", label["text"]), names)
        shape = shape_at(lab, l["end"], scale)
        read.append({"label": label["text"], "size": label["size"], "names": named, "shape": shape,
                     "end": [round(l["end"][0]), round(l["end"][1])]})
    r["leaders"] = [{k: v for k, v in x.items() if k != "size"} for x in read]
    r["leaders_on_nothing"] = [x["label"] for x in read if not x["shape"]]

    # Each part: the largest label naming it whose leader ends on a shape.
    claim, at = {}, {}
    # A part named twice is placed by the larger label.
    for x in sorted(read, key=lambda x: -x["size"]):
        for p in x["names"]:
            if x["shape"] and p not in claim:
                claim[p] = x["shape"]
                at[p] = (x["end"][0] * scale, x["end"][1] * scale)

    # Which way the stack runs: down the page, or across it if the leader
    # ends on the stack spread further sideways. Across, everything below
    # is read on the picture turned on its side.
    pts = [at[p] for p in truth["stack"] if p in at]
    across = len(pts) >= 2 and (max(q[0] for q in pts) - min(q[0] for q in pts)) > (max(q[1] for q in pts) - min(q[1] for q in pts))
    if across:
        lab = lab.T
        at = {p: (y, x) for p, (x, y) in at.items()}
    r["stack_runs"] = "across the page" if across else "down the page"

    # Parts on the stack drawn touching come out as one shape: cut it at its
    # narrowest row between their leader ends. Parts allowed to share a shape
    # (a part set into another) keep the whole of it.
    masks, joined = {}, []
    by_shape = {}
    for p, k in claim.items():
        by_shape.setdefault(k, []).append(p)
    for k, ps in by_shape.items():
        whole = lab == k
        on = sorted([p for p in ps if p in truth["stack"]], key=lambda p: at[p][1])
        if len(on) > 1:
            joined.append(" and ".join(on))
            for p, m in zip(on, split(whole, [at[p][1] for p in on])):
                masks[p] = m if m is not None and m.any() else None
        for p in ps:
            masks.setdefault(p, whole)
        # A part beside the stack, drawn joined to a part on it.
        for p in ps:
            if p in truth.get("beside", []):
                for q in on:
                    if masks.get(q) is not None:
                        masks[q] = split_sideways(masks[q], at[q][0], at[p][0])
    r["drawn_touching"] = joined
    shapes = {p: measure(m, scale) for p, m in masks.items() if m is not None}
    # Measure again with the stack's centre line in mind (see measure).
    on_stack = sorted(shapes[p]["centre"] for p in truth["stack"] if p in shapes)
    if on_stack:
        prior = on_stack[len(on_stack) // 2]
        shapes = {p: measure(m, scale, prior) for p, m in masks.items() if m is not None}
    r["shapes"] = shapes

    if not any(x["names"] for x in read):
        r["error"] = None
        r["undecided_why"] = "no leader from a label naming a part was found, so the drawing is left to the eye (a numbered parts list, or labels set beside the parts without lines)"
        r["checks"] = {c: None for c in ("parts", "order", "fit", "axis", "labels")}
        return r

    # parts, and labels as far as they can be measured
    unlabelled = [p for p in parts if not any(p in x["names"] for x in read)]
    pointless = sorted({p for x in read if not x["shape"] for p in x["names"]} - set(claim))
    r["missing"] = unlabelled
    r["labels_on_nothing"] = pointless
    # A part whose only label points at nothing may or may not be drawn.
    r["checks"]["parts"] = False if unlabelled else (None if pointless else True)

    # order, top to bottom
    stack = [p for p in truth["stack"] if p in shapes]
    def misplaced(seq):
        return [f"{b} above {a}" for i, a in enumerate(seq) for b in seq[i + 1:]
                if shapes[a]["middle"] >= shapes[b]["middle"]]
    wrong = misplaced(stack)
    # Across the page there is no up: either end may come first.
    if across and wrong and not misplaced(stack[::-1]):
        wrong = []
    r["out_of_order"] = wrong
    unplaced = [p for p in truth["stack"] if p not in shapes]
    if unplaced:
        r["order_read_without"] = unplaced
    # With a part left out, what is drawn can still be out of order, but the
    # order cannot pass: the same rule as french-press-order.py.
    if wrong:
        r["checks"]["order"] = False
    else:
        r["checks"]["order"] = True if len(stack) >= 2 and not unplaced else None

    # fit
    fits, results = [], []
    for f in truth.get("fits", []):
        a, b = f["a"], f["b"]
        if "min" not in f:
            fits.append({"a": a, "b": b, "rule": f["ratio"], "measured": None})
        elif a in shapes and b in shapes:
            ratio = shapes[a]["width"] / shapes[b]["width"]
            ok = bool(f["min"] <= ratio <= f["max"])
            fits.append({"a": a, "b": b, "ratio": round(ratio, 2), "allowed": [f["min"], f["max"]], "pass": ok})
            results.append(ok)
        else:
            fits.append({"a": a, "b": b, "ratio": None, "why": "not both drawn"})
    r["fits"] = fits
    # One pair out fails it, but a pass needs every measurable pair measured:
    # on 2026-10-08 a seal the grader could not find left the fit passed on
    # the filter alone, and the eye had failed that seal as too wide.
    unmeasured = any(x.get("why") == "not both drawn" for x in fits)
    if results and not all(results):
        r["checks"]["fit"] = False
    elif results and not unmeasured:
        r["checks"]["fit"] = True
    elif truth.get("fits"):
        r["checks"]["fit"] = None

    # axis
    on = [p for p in truth.get("axis", truth["stack"]) if p in shapes]
    if len(on) >= 2:
        cs = sorted(shapes[p]["centre"] for p in on)
        mid = cs[len(cs) // 2]
        r["off_axis"] = {p: round(shapes[p]["centre"] - mid, 1) for p in on
                         if abs(shapes[p]["centre"] - mid) > AXIS_TOL * (vb[3] if across else vb[2])}
        r["checks"]["axis"] = not r["off_axis"]
    else:
        r["checks"]["axis"] = None

    # anything the member adds
    for extra in truth.get("same_shape", []):
        a, b = extra["a"], extra["b"]
        r["checks"][extra["check"]] = bool(a in claim and b in claim and claim[a] == claim[b])
    # A leader naming a part and ending on blank paper fails; whether the
    # rest end on the part they name is for the eye.
    r["checks"]["labels"] = False if any(x["names"] and not x["shape"] for x in read) else None
    return r


def main():
    src, out = sys.argv[1], sys.argv[2]
    member = os.environ.get("EXPLODED_MEMBER")
    members = json.load(open(os.path.join(HERE, "exploded-truth.json")))["members"]
    # Held-back members live in a gitignored file; see harness/cases/private.
    private = os.path.join(HERE, "private", "exploded-truth.json")
    if os.path.exists(private):
        members.update(json.load(open(private))["members"])
    truth = members[member]
    r = grade(src, member, truth)
    # finish() counts a check as passed only when it is true; a null check is
    # one the grader leaves to the eye, so it is left out of the verdict.
    decided = {k: v for k, v in r["checks"].items() if v is not None}
    r["undecided"] = [k for k, v in r["checks"].items() if v is None]
    r["checks"] = decided
    r.pop("error", None) if r.get("error") is None else None
    if r["undecided"] and not r.get("error"):
        failed = [k for k, v in decided.items() if not v]
        r["detail"] = (("failed: " + ", ".join(failed)) if failed else "passed what it measured") + "; left to the eye: " + ", ".join(r["undecided"])
    finish(r, out)


if __name__ == "__main__":
    main()
