#!/usr/bin/env python3
"""A cup of coffee with a spoon stirring in it, written in HTML and CSS only.

The brief: no JavaScript, no SVG, no images, and the spoon goes round in a
loop. Two things can be read from the file without looking at it.

  - html_css_only: the brief is kept. A <script>, an <svg>, an <img> or a
    url(...) means the model reached for a picture or code instead of CSS, and
    whatever the render shows, it is not the thing that was asked for.
  - loop: the motion is CSS. There is an @keyframes rule, an element names it,
    the iteration count is infinite, and the rule actually moves something:
    at least one stop changes a transform, a translation, a rotation or an
    offset. A keyframes block that only fades a colour is not a stirring loop.

The rest is the eye's, because a single still cannot settle them: whether the
cup reads as seen from above, whether the spoon passes behind the far rim on
the back half of its circuit, and whether the handle stays attached to the
bowl. Those are the case's lookFor lines.

Written 2026-10-19, before any model saw the prompt.
"""
import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _grade import finish

src, out = sys.argv[1], sys.argv[2]
try:
    html = open(src, encoding="utf-8", errors="replace").read()
except OSError as e:
    finish({"error": f"could not read {src}: {e}", "checks": {}}, out)
    sys.exit(0)

problems = []

# ── the brief: HTML and CSS, nothing else ───────────────────────────────────
forbidden = [
    (r"<script\b", "a <script>"),
    (r"<svg\b", "an <svg>"),
    (r"<img\b", "an <img>"),
    (r"<canvas\b", "a <canvas>"),
    (r"<iframe\b", "an <iframe>"),
    (r"url\(\s*['\"]?(?!#)", "an external url(...)"),
    (r"javascript:", "a javascript: URL"),
]
found = [why for pat, why in forbidden if re.search(pat, html, re.I)]
html_css_only = not found
if found:
    problems.append("not HTML and CSS only: uses " + ", ".join(found))

# Comments go first, so a rule quoted inside one is not read as a rule.
css = re.sub(r"/\*.*?\*/", " ", html, flags=re.S)

MOVES = re.compile(
    r"\b(transform|translate|rotate|left|top|right|bottom|offset-path|offset-distance)\s*:\s*([^;}]+)",
    re.I,
)

# Every @keyframes name and its body, with the closing brace matched.
keyframes = {}
for m in re.finditer(r"@keyframes\s+([\w-]+)\s*\{", css, re.I):
    depth, j = 1, m.end()
    while j < len(css) and depth:
        if css[j] == "{":
            depth += 1
        elif css[j] == "}":
            depth -= 1
        j += 1
    keyframes[m.group(1)] = css[m.end():j - 1]

# A rule moves something if one of those properties takes two values, or if it
# has a single `to`/`100%` stop that is not the identity: `to { rotate(360deg) }`
# starts from wherever the element already was, so it moves without a `from`.
IDENTITY = re.compile(r"^(none|initial|inherit|rotate\(0(?:deg|rad|turn)?\)|translate(?:3d|x|y|z)?\([\s0,.%]*\)|scale(?:3d|x|y)?\(1[\s,1]*\)|matrix\(1,\s*0,\s*0,\s*1,\s*0,\s*0\))$", re.I)

moves = {}
for name, body in keyframes.items():
    vals = {}
    for prop, value in MOVES.findall(body):
        vals.setdefault(prop.lower(), set()).add(value.strip().lower())
    moved = {p: v for p, v in vals.items() if len(v) > 1}
    if not moved and re.search(r"(?:^|[^\w-])(?:to|100%)\s*\{", body):
        for prop, v in vals.items():
            if any(not IDENTITY.match(x) for x in v):
                moved[prop] = v
    moves[name] = moved

infinite = re.search(r"animation(?:-iteration-count)?\s*:\s*[^;}]*\binfinite\b", css, re.I) is not None
named = [n for n in moves if re.search(r"animation(?:-name)?\s*:[^;}]*\b" + re.escape(n) + r"\b", css, re.I)]
running = [n for n in named if moves[n]]
loop = bool(running) and infinite

if not keyframes:
    problems.append("no @keyframes rule, so nothing can move")
elif not named:
    problems.append("no element names a @keyframes rule in an animation")
elif not running:
    problems.append("the @keyframes rule changes nothing that moves")
elif not infinite:
    problems.append("the animation is not set to repeat forever")

detail = []
if keyframes:
    detail.append(f"{len(keyframes)} @keyframes: " + ", ".join(sorted(keyframes)))
if running:
    moved = sorted({p for n in running for p in moves[n]})
    detail.append(f"{running[0]} changes {', '.join(moved)}")
if infinite:
    detail.append("repeats forever")

r = {
    "checks": {"html_css_only": html_css_only, "loop": loop},
    "detail": "; ".join(problems) or "; ".join(detail),
}
finish(r, out)
