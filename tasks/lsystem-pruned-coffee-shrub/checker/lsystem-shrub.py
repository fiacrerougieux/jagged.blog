#!/usr/bin/env python3
"""Two ways a shrub can fake its flat side. Whether it looks pruned is for the eye.

Expands the L-system exactly as the renderer does.

Whether a side looks hedge-pruned stays a call by eye. A pruned side is flat
at the scale of the shrub and rough at the scale of a twig, and on 2026-09-28
no measure of the outline separated that from the sides of natural L-system
bushes, which are often as straight. So this prints how straight each side
is, and a run that passes here is still undecided until someone looks.

It fails two fakes:

- Half a shrub. The main stem is the path drawn outside every bracket. If no
  branch leaves it toward one side, that side is flat because nothing ever
  grew there, and a hedge trimmer never makes that. Branches cut back to
  stubs still count, since stubs are what pruning by the rules leaves.
  Added 2026-09-29 after the first four cheap models' runs, where it was the
  commonest way to get a flat side.
- A drawn line. Each side's outline is taken band by band over the body of
  the shrub (the bands at least half as wide as the widest), gaps between
  tiers of branches are filled from the bands beside them, and a line is
  fitted through it. Strokes off the main stem that lie within 8% of the
  width of that line and within 10 degrees of it are joined, and if the
  longest covers 40% of the side's height or more, the side was drawn.

The segment count and the share of the picture that is ink are printed for
the size check, which also stays a call by eye.
"""
import json
import math
import sys
from _grade import finish

src, out = sys.argv[1], sys.argv[2]
r = {"checks": {}}
try:
    spec = json.loads(open(src, errors="replace").read())
    s = str(spec["axiom"]); rules = {k: str(v) for k, v in spec["rules"].items()}
    angle = float(spec["angle"]); n = int(spec["iterations"]); heading = float(spec.get("start_heading", 90))
except Exception as e:
    r["error"] = f"not a readable L-system: {e}"
    finish(r, out); sys.exit()
for _ in range(n):
    s = "".join(rules.get(c, c) for c in s)
    if len(s) > 2_000_000:
        r["error"] = "the string grew past 2,000,000 symbols"
        finish(r, out); sys.exit()

x = y = 0.0; stack = []; segs = []; trunk = []
for c in s:
    if c in "FGf":
        nx = x + math.cos(math.radians(heading)); ny = y + math.sin(math.radians(heading))
        if c != "f":
            segs.append((x, y, nx, ny))
            if not stack:
                trunk.append((x, y, nx, ny))
        x, y = nx, ny
    elif c == "+":
        heading += angle
    elif c == "-":
        heading -= angle
    elif c == "[":
        stack.append((x, y, heading))
    elif c == "]" and stack:
        x, y, heading = stack.pop()
if not segs:
    r["error"] = "nothing drawn"
    finish(r, out); sys.exit()

r["segments"] = len(segs)
xs = [p for a in segs for p in (a[0], a[2])]; ys = [p for a in segs for p in (a[1], a[3])]
x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
W, H = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)

# Points along every segment, so a long segment counts in every band it crosses.
pts = [(ax + k / 4 * (bx - ax), ay + k / 4 * (by - ay)) for ax, ay, bx, by in segs for k in range(5)]

# Ink: the share of a 140 by 180 grid over the picture that a segment crosses.
ink = {(int((px - x0) / W * 139), int((py - y0) / H * 179)) for px, py in pts}
r["ink"] = round(len(ink) / (140 * 180), 3)

# The outline, band by band, over the body of the shrub.
BANDS = 30
rows = []
for b in range(BANDS):
    a, z = y0 + b * H / BANDS, y0 + (b + 1) * H / BANDS
    band = [px for px, py in pts if a <= py <= z]
    if band:
        rows.append(((a + z) / 2, min(band), max(band)))
widest = max(R - L for _, L, R in rows)
body = [row for row in rows if row[2] - row[1] >= 0.5 * widest]
if len(body) < 5:
    r["error"] = "too little body to find a side"
    finish(r, out); sys.exit()


def fitted(out_, ys_):
    """A line x = a + b*y through one side's outline, in outward units, after
    each band takes the outermost of itself and the two bands either side, so
    gaps between tiers of branches do not count. Returns a, b and how far the
    outline strays from the line, as a share of the width."""
    n = len(out_)
    fill = [max(out_[max(0, i - 2):i + 3]) for i in range(n)]
    my = sum(ys_) / n; mx = sum(fill) / n
    vy = sum((v - my) ** 2 for v in ys_) or 1e-9
    b = sum((v - my) * (u - mx) for v, u in zip(ys_, fill)) / vy
    a = mx - b * my
    return a, b, math.sqrt(sum((u - a - b * v) ** 2 for v, u in zip(ys_, fill)) / n) / W


by_ = [row[0] for row in body]
# Outward is -x on the left and +x on the right.
sides = {"left": fitted([-row[1] for row in body], by_), "right": fitted([row[2] for row in body], by_)}
r["straightness"] = {k: {"strays": round(v[2], 3), "leans": round(math.degrees(math.atan(abs(v[1]))), 1)} for k, v in sides.items()}
r["straighter_side"] = min(sides, key=lambda k: sides[k][2])
extent = body[-1][0] - body[0][0] + H / BANDS
r["side_height"] = round(extent, 1)


# The main stem is left out of the wall test: a straight trunk is a stem,
# and whether growth hangs off one side of it is tested on its own below.
in_trunk = set(trunk)
branches = [sg for sg in segs if sg not in in_trunk]


def longest_stroke(side):
    """The longest straight stroke lying along one side's fitted line."""
    a, b, _ = sides[side]
    sign = -1 if side == "left" else 1
    # Distance inward from the fitted line, as a share of the width.
    depth = lambda px, py: (a + b * py - sign * px) / W
    near = lambda px, py: -0.08 <= depth(px, py) <= 0.08
    ux, uy = sign * b / math.hypot(1, b), 1 / math.hypot(1, b)
    # Strokes near the line and within 10 degrees of it, grouped by the line
    # each one lies on (its direction, and where that line crosses the
    # horizontal through the origin), then joined where they touch.
    groups = {}
    for ax, ay, bx, by in branches:
        L = math.hypot(bx - ax, by - ay)
        if L and near(ax, ay) and near(bx, by) and abs((bx - ax) * ux + (by - ay) * uy) / L >= math.cos(math.radians(10)):
            if by < ay:
                ax, ay, bx, by = bx, by, ax, ay
            dx, dy = (bx - ax) / L, (by - ay) / L
            key = (round(math.degrees(math.atan2(dy, dx))), round((ax - ay * dx / dy) / W * 200))
            groups.setdefault(key, []).append((ay, by))
    longest = 0.0
    for spans in groups.values():
        run = None
        for lo, hi in sorted(spans):
            if run and lo <= run[1] + 1e-6:
                run[1] = max(run[1], hi)
            else:
                run = [lo, hi]
            longest = max(longest, run[1] - run[0])
    return longest


strokes = {k: longest_stroke(k) for k in sides}

# The main stem: the path drawn outside every bracket, taken as a line through
# its points. If there is none, the stem is where the turtle started.
tp = [(ax, ay) for ax, ay, _, _ in trunk] + [(bx, by) for _, _, bx, by in trunk]
if len(tp) >= 2 and max(p[1] for p in tp) - min(p[1] for p in tp) > 1e-6:
    my = sum(p[1] for p in tp) / len(tp); mx = sum(p[0] for p in tp) / len(tp)
    vy = sum((p[1] - my) ** 2 for p in tp)
    sb = sum((p[1] - my) * (p[0] - mx) for p in tp) / vy
    stem = lambda py: mx + sb * (py - my)
else:
    stem = lambda py: 0.0
# Branches leaving the stem, counted by which way they head, however short.
# A side cut back hard to stubs still has branches; a side with none is half
# a shrub, which a hedge trimmer never makes.
on_stem = {(round(ax, 4), round(ay, 4)) for ax, ay, _, _ in trunk} | {(round(bx, 4), round(by, 4)) for _, _, bx, by in trunk}
heads = {"left": 0, "right": 0}
for ax, ay, bx, by in branches:
    if (round(ax, 4), round(ay, 4)) in on_stem and abs(bx - ax) > 0.1:
        heads["left" if bx < ax else "right"] += 1
if not trunk:
    heads = {"left": 1, "right": 1}
r["branches_off_stem"] = heads
share = {k: v / max(1, sum(heads.values())) for k, v in heads.items()}
thin = min(share, key=share.get)
half = share[thin] < 0.1
r["longest_stroke_along"] = {k: round(v, 1) for k, v in strokes.items()}
walled = [k for k in sides if strokes[k] >= 0.4 * extent]
r["checks"]["no_drawn_edge"] = not walled
r["checks"]["grows_both_sides"] = not half
why = []
if half:
    why.append(f"half a shrub: {heads[thin]} of {sum(heads.values())} branches off the main stem head {thin}")
for k in walled:
    why.append(f"the {k} side is a drawn line: one straight stroke {strokes[k]:.1f} long on a side {extent:.1f} high")
if why:
    r["detail"] = "; ".join(why)
else:
    r["detail"] = "grows on both sides with no drawn edge, so whether it looks pruned is for the eye; the sides stray " + " and ".join(f"{k} {v[2]:.1%}" for k, v in sides.items()) + " of the width from straight"
finish(r, out)
