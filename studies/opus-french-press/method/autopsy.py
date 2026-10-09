#!/usr/bin/env python3
"""Autopsy: a published French press is put in front of a model, which is asked
to name everything wrong with it, most serious first.

Which press it was given is read from the input file in /work, by its hash,
and looked up in autopsy-truth.json, which holds the defects written down when
that result was published. Written 2026-10-05, before any model saw the prompt.

  recall        every written-down defect is named somewhere in the answer.
                Not graded on a control, which has none.
  no_invented   nothing the answer calls wrong is something the published
                result was checked and found right on: a part said to be
                missing that is drawn, a stack said to be in the wrong order
                that passed order, plates said to be the wrong size that
                passed diameter, and so on. On a control this is the false
                positive check.

Each item of the answer is a numbered or bulleted line, or a paragraph. Each
item's sentences are matched against the kinds of defect below. The order the
items name the defects in is written down as `ranking`, for judging severity
by eye. Items that match no kind are written down as `other` for the eye too:
they may be real defects nobody wrote down, or noise. Whether the model said
nothing was wrong is written down as `says_ok`. On the SVG and prose arms,
whether it turned the input into a picture anyway is written down as
`made_picture`, as a compliance note and not a check.
"""
import glob, hashlib, json, os, re, sys
from _grade import finish
from _reply import said, sentences, tool_calls

src, out = sys.argv[1], sys.argv[2]
r = {"checks": {}}
TRUTH = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "autopsy-truth.json")))["specimens"]


# --- which press, and on which arm --------------------------------------------
def work_dir(path):
    d = os.path.dirname(os.path.abspath(path))
    for _ in range(4):
        if glob.glob(os.path.join(d, "press.*")):
            return d
        d = os.path.dirname(d)
    return None


ARMS = {"png": "png", "svg": "svg", "txt": "prose"}
work = work_dir(src)
spec = arm = None
for f in sorted(glob.glob(os.path.join(work, "press.*")) if work else []):
    h = hashlib.sha256(open(f, "rb").read()).hexdigest()[:16]
    for sid, s in TRUTH.items():
        a = ARMS.get(f.rsplit(".", 1)[-1])
        if a and s["inputs"].get(a) == h:
            spec, arm = sid, a
if not spec:
    r["error"] = "could not tell which press this run was given"
    finish(r, out); sys.exit()
S = TRUTH[spec]
r["specimen"], r["arm"] = spec, arm

answer = open(src, errors="replace").read() if os.path.exists(src) else said(src)
r["answered_in"] = "file" if os.path.exists(src) else "reply"


# --- the answer, item by item ---------------------------------------------------
def items(text):
    """Numbered or bulleted lines start an item, a blank line ends one."""
    out, cur = [], []
    for line in text.splitlines():
        if re.match(r"^\s*(?:\d+[.)]|[-*•])\s+", line) or not line.strip():
            if cur:
                out.append(" ".join(cur))
            cur = [line.strip()] if line.strip() else []
        else:
            cur.append(line.strip())
    if cur:
        out.append(" ".join(cur))
    return [i for i in out if re.search(r"[a-z]", i, re.I)]


PARTS = {
    "knob": r"knob|finial",
    "rod": r"\brod\b|plunger (?:stem|shaft)|\bshaft\b|\bstem\b",
    "lid": r"\blid\b|\bcover\b",
    "spiral": r"spiral|spring|coil",
    "mesh": r"mesh|screen",
    "cross": r"cross[- ]?plate|crossplate|cross[- ]?piece|bottom (?:filter )?plate|lower (?:filter )?plate|retaining plate",
    "carafe": r"carafe|beaker|\bjug\b|\bvessel\b",
}
F = r"(?:spiral|spring|coil|mesh|screen|cross|filter|plate|disc|disk|stack)"
GLASS = r"(?:glass|carafe|beaker|jug|vessel|wall|walls|sides|mouth|opening|rim|neck)"
NOT = r"(?:won'?t|wouldn'?t|would not|will not|cannot|can'?t|could not|couldn'?t|doesn'?t|does not|don'?t|do not|never|fails? to)"
KINDS = {
    "order:filter-inverted": [
        rf"(?=.*{F}).*(?:upside[- ]down|inverted|reversed|backwards|flipped|swapped|wrong (?:way up|way round|order|sequence)|out of order|misordered|order is (?:wrong|incorrect|reversed)|incorrect(?:ly)? (?:order|ordered|sequence|stacked))",
        r"cross[- ]?plate\b[^.]{0,40}\b(?:on top of|above|over)\b[^.]{0,20}\b(?:mesh|screen|spiral|spring)",
        r"cross[- ]?plate\b[^.]{0,30}\b(?:at the top|on top|uppermost|topmost)\b(?! of the (?:carafe|glass|beaker))",
        r"(?:mesh|screen)\b[^.]{0,40}\b(?:below|under|beneath|underneath)\b[^.]{0,20}\b(?:cross|bottom plate|lower plate)",
        r"(?:mesh|screen)\b[^.]{0,30}\b(?:at the bottom|on the bottom|bottom of the (?:filter|stack)|lowest)",
        r"(?:spiral|spring)\b[^.]{0,40}\b(?:below|under|beneath|underneath)\b[^.]{0,20}\b(?:mesh|screen)",
        r"(?:mesh|screen)\b[^.]{0,40}\b(?:above|on top of|over)\b[^.]{0,20}\b(?:spiral|spring)",
        rf"(?=.*{F}).*\b(?:should|must|needs? to|ought to)\b (?:be|sit|go|come)\b[^.]{{0,40}}\b(?:above|below|under|beneath|on top|at the (?:top|bottom)|between|in the middle)",
    ],
    "order:lid-below-filter": [
        rf"\blid\b[^.]{{0,50}}\b(?:below|under|beneath|underneath|after|lower than)\b[^.]{{0,30}}{F}",
        rf"{F}[^.]{{0,50}}\b(?:above|over|on top of|before)\b[^.]{{0,20}}\blid\b",
        r"\blid\b[^.]{0,40}\b(?:should|must|needs? to)\b[^.]{0,30}\b(?:above|over|on top|before|higher)",
        r"\blid\b[^.]{0,30}(?:wrong (?:place|position)|misplaced|too low|out of (?:place|order)|between the (?:filter|mesh|plate|stack|spring|screen)\w* and the (?:carafe|glass|beaker))",
    ],
    "size:plates-too-wide": [
        rf"(?=.*{GLASS}){F}\w*[^.]{{0,60}}(?:wider|larger|bigger|too (?:wide|big|large)|oversized|{NOT} fit)",
        rf"{GLASS}[^.]{{0,40}}(?:narrower|smaller|too (?:narrow|small))[^.]{{0,40}}{F}",
    ],
    "size:plates-too-narrow": [
        rf"(?=.*{GLASS}){F}\w*[^.]{{0,60}}(?:narrower|smaller|too (?:small|narrow)|undersized|half the width|not wide enough|{NOT} (?:seal|reach|touch|press against|contact|meet|fill))",
        rf"{GLASS}[^.]{{0,40}}(?:wider|larger|bigger)[^.]{{0,40}}{F}",
        r"\bgaps?\b[^.]{0,30}\b(?:around|at|between)\b[^.]{0,20}\b(?:edge|edges|sides|rim|wall|walls|glass)",
    ],
    "size:frame-too-small": [
        rf"\bframe\b[^.]{{0,60}}(?:smaller|too (?:small|narrow|short)|narrower|shorter|{NOT} (?:fit|hold|contain|take))",
        rf"(?:carafe|glass|beaker)[^.]{{0,60}}(?:wider|larger|bigger|taller|too (?:big|wide|large|tall)|{NOT} fit)[^.]{{0,40}}\bframe\b",
    ],
    "overlap:cross-plate-rim": [
        r"(?:cross|bottom plate|lower plate|filter|plate)[^.]{0,60}(?:behind|overlap\w*|hidden|obscured|tucked|clipp\w*|intersect\w*|collid\w*|inside the (?:rim|mouth)|into the (?:rim|mouth)|touch\w* the rim|merges?)",
        r"(?:rim|carafe|glass)[^.]{0,40}(?:overlap\w*|covers?|hides?|obscures?|cuts? (?:into|through)|intersect\w*)[^.]{0,40}(?:cross|plate|filter)",
        r"(?:cross|plate|filter)[^.]{0,40}(?:too close|no gap|no space|not separated|not exploded)[^.]{0,30}(?:carafe|glass|rim)?",
    ],
    "axis:off": [
        r"off[- ](?:axis|centre|center|centred|centered)|not (?:centred|centered|aligned|coaxial|concentric)|misaligned|out of line|shifted (?:to the )?(?:left|right|sideways)",
        # Added 2026-10-09 for the Opus press whose frame stands beside the glass.
        r"\b(?:frame|holder|handle|base|cage)\b[^.]{0,50}\b(?:beside|next to|alongside|to the (?:side|right|left) of|off to the (?:side|right|left))\b",
        r"\b(?:glass|beaker|carafe)\b[^.]{0,40}\b(?:not (?:above|over|in line with|inside)|beside)\b[^.]{0,20}\b(?:frame|holder|base|cage)\b",
    ],
    "labels:wrong": [
        r"(?:label|leader|callout|caption)\w*[^.]{0,60}(?:wrong|incorrect|mislead\w*|{NOT} (?:match|point)|points? (?:to|at) (?:the )?(?:wrong|nothing|empty)|misplaced)".replace("{NOT}", NOT),
        r"mislabel\w*|misnam\w*|misidentif\w*",
        r"(?:called|labelled|labeled|named) [^.]{0,40}(?:but|though|yet|which is not|isn'?t)",
        r"(?:called|labelled|labeled|named|name)\b[^.]{0,60}(?:mix\w* up|confus\w*|two (?:different )?parts|conflat\w*)",
    ],
}
MISSING = r"(?:missing|lacks?|lacking|without|omits?|omitted|absent|no)\W+(?:\w+\W+){{0,2}}(?:{p})|(?:{p})\w*\W+(?:\w+\W+){{0,3}}(?:is|are) (?:missing|absent|omitted|left out|not (?:shown|drawn|included))"
for p, rx in PARTS.items():
    KINDS[f"missing:{p}"] = [MISSING.format(p=rx)]
CHECK_OF = {"order": "order", "size:plates": "diameter", "axis": "axis", "labels": "labels"}


# A sentence saying something is right is not a claim that it is wrong, unless
# it turns with a "but": "the stack is not upside down" and "the cross plate
# is correctly at the bottom" name no defect.
FINE = re.compile(
    r"\b(?:not|isn'?t|aren'?t|never|nothing)\b[^.]{0,15}\b(?:upside|inverted|reversed|missing|wrong|off)"
    r"|\b(?:correct(?:ly)?|right way|properly|as it should|accurate(?:ly)?)\b", re.I)
TURN = re.compile(r"\b(?:but|however|although|though|except|yet)\b", re.I)


def kinds_in(item):
    found = []
    for s in sentences(item):
        if FINE.search(s) and not TURN.search(s):
            continue
        for k, rxs in KINDS.items():
            if k not in found and any(re.search(rx, s, re.I) for rx in rxs):
                found.append(k)
    return found


def invented(k):
    """A kind of defect this press was checked and found right on."""
    if k.startswith("missing:"):
        return k.split(":")[1] in S["drawn"]
    check = next((c for pre, c in CHECK_OF.items() if k.startswith(pre)), None)
    return check in S["passed"]


truth = [d["kind"] for d in S["defects"]]
also = [d["kind"] for d in S.get("also", [])]
ranking, other, made_up = [], [], []
for it in items(answer):
    ks = kinds_in(it)
    hit = [k for k in ks if k in truth or k in also]
    bad = [k for k in ks if k not in truth and k not in also and invented(k)]
    if bad and not hit:
        made_up.append({"item": it[:240], "kinds": bad})
    for k in hit:
        if k not in ranking:
            ranking.append(k)
    if not ks:
        other.append(it[:240])

found = [k for k in truth if k in ranking]
r["found"] = found
r["missed"] = [d["what"] for d in S["defects"] if d["kind"] not in found]
r["ranking"] = ranking
r["invented"] = made_up[:8]
r["other"] = other[:8]
r["says_ok"] = bool(re.search(
    r"nothing (?:is |seems |looks )?(?:seriously |obviously |really )?wrong|no (?:errors|problems|defects|issues|mistakes)\b|(?:can'?t|cannot|could not|couldn'?t) find anything wrong|I (?:see|found|find) nothing wrong",
    answer, re.I))

if truth:
    r["checks"]["recall"] = len(found) == len(truth)
r["checks"]["no_invented"] = not made_up

if arm in ("svg", "prose"):
    PICTURE = re.compile(r"rsvg|cairosvg|inkscape|magick|\bconvert\b|chrom|librsvg|svg2png|PIL|matplotlib")
    r["made_picture"] = any(
        (name == "bash" and PICTURE.search(str(a.get("command", "")))) or (name == "read" and str(a.get("path", "")).lower().endswith((".png", ".jpg")) and "/frames/" not in str(a.get("path", "")))
        for name, a in tool_calls(src)
    )

problems = []
if truth and r["missed"]:
    problems.append(f"named {len(found)} of {len(truth)}, missed " + "; ".join(r["missed"]))
if made_up:
    problems.append(f"{len(made_up)} invented")
if problems:
    r["detail"] = "; ".join(problems)
finish(r, out)
