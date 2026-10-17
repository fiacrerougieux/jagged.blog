#!/usr/bin/env python3
"""A piano piece whose left hand crosses over the right hand for bars 9 to 12.

LilyPond runs the file with lilypond-probe.ly included first, which writes one
line per note and per text marking: the voice, the staff it sits on, the bar,
the pitch and the stem direction. A voice belongs to the hand whose staff it
starts on, so a left hand that moves up with \\change Staff stays the left hand,
unless the notes of the voice carry a hand's name: a left hand written into the
treble staff as its own voice and labelled "L.H." is the left hand.

  piano_staff         a treble staff and a bass staff, both with notes
  sixteen_bars        the last note is in bar 16
  left_hand_crosses   in each of bars 9 to 12 most left-hand notes are on the
                      treble staff and sit above the right hand on average,
                      and outside those bars most are back on the bass staff.
                      A left hand written high on the bass staff fails.
  right_hand_goes_on  the right hand plays in every bar, and strikes at least
                      twice in each of bars 9 to 12. A new figure counts, so
                      long as it keeps going.
  crossing_marked     words that name a hand or the crossing at bar 8 or 9,
                      and a release at bar 12 or 13: more words, or the end of
                      a dashed line that started with the first ones
  stems_split         in bars 9 to 12, wherever both hands share a staff, at
                      least three in four of their notes have stems pinned
                      apart: left hand up, right hand down. Hands that swap
                      staves share none, and pass.
"""
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from fractions import Fraction
from statistics import mean
from _grade import finish

src, out = sys.argv[1], sys.argv[2]
r = {"checks": {}}
HERE = os.path.dirname(os.path.abspath(__file__))
CROSS = range(9, 13)

with tempfile.TemporaryDirectory() as t:
    tsv = os.path.join(t, "probe.tsv")
    p = subprocess.run(
        ["lilypond", "-dno-print-pages", f"-dinclude-settings={HERE}/lilypond-probe.ly", "-o", os.path.join(t, "x"), os.path.abspath(src)],
        env={**os.environ, "PROBE_OUT": tsv}, capture_output=True, text=True, timeout=240)
    rows = [l.rstrip("\n").split("\t") for l in open(tsv, encoding="utf-8", errors="replace")] if os.path.exists(tsv) else []

notes, texts = [], []
for row in rows:
    kind, voice, staff, _sid, clef, bar, _pos, stem, when, what = row[:10]
    what = what.strip('"')
    e = {"voice": voice, "staff": staff, "clef": clef, "bar": int(bar), "stem": stem, "when": Fraction(when), "what": what}
    if kind == "note":
        e["pitch"] = int(what)
        notes.append(e)
    else:
        e["kind"] = kind
        texts.append(e)

if not notes:
    r["error"] = "LilyPond produced no notes" + (f": {p.stderr.strip().splitlines()[-1]}" if p.stderr.strip() else "")
    for c in ("piano_staff", "sixteen_bars", "left_hand_crosses", "right_hand_goes_on", "crossing_marked", "stems_split"):
        r["checks"][c] = False
    finish(r, out)
    sys.exit()

# Each staff's clef when its first note sounds, and each voice's first staff.
first_clef, first_staff = {}, {}
for n in sorted(notes, key=lambda n: n["when"]):
    first_clef.setdefault(n["staff"], n["clef"])
    first_staff.setdefault(n["voice"], n["staff"])
upper = [s for s, c in first_clef.items() if c == "clefs.G"]
lower = [s for s, c in first_clef.items() if c == "clefs.F"]
r["staves"] = {s: c for s, c in first_clef.items()}
r["checks"]["piano_staff"] = len(upper) == 1 and len(lower) == 1
up, low = (upper or [None])[0], (lower or [None])[0]
for n in notes:
    n["hand"] = "right" if first_staff[n["voice"]] == up else "left" if first_staff[n["voice"]] == low else None

# A hand named on a voice's own notes wins: the first of L.H. or R.H. (or
# m.s., m.g., m.d., left, right) in the first such words on that voice.
LEFT = re.compile(r"\b(l\.?\s?h\b|left|m\.?\s?[sg]\b)", re.I)
RIGHT = re.compile(r"\b(r\.?\s?h\b|right|m\.?\s?d\b)", re.I)
named = {}
for t in sorted(texts, key=lambda t: t["when"]):
    if t["kind"] not in ("text", "span") or t["voice"] in named:
        continue
    l, rr = LEFT.search(t["what"]), RIGHT.search(t["what"])
    if l or rr:
        named[t["voice"]] = "left" if l and (not rr or l.start() < rr.start()) else "right"
for n in notes:
    n["hand"] = named.get(n["voice"], n["hand"])
r["named_hands"] = len(named)

last = max(n["bar"] for n in notes)
r["last_bar"] = last
r["checks"]["sixteen_bars"] = last == 16

by = defaultdict(list)
for n in notes:
    by[n["hand"], n["bar"]].append(n)

# The crossing, bar by bar.
cross = {}
for b in CROSS:
    lh, rh = by["left", b], by["right", b]
    on_top = sum(n["staff"] == up for n in lh) / len(lh) if lh else 0
    above = bool(lh and rh) and mean(n["pitch"] for n in lh) > mean(n["pitch"] for n in rh)
    cross[b] = {"left_on_treble": round(on_top, 2), "left_above_right": above}
outside = [n for n in notes if n["hand"] == "left" and n["bar"] not in CROSS]
back = sum(n["staff"] == low for n in outside) / len(outside) if outside else 0
r["crossing"] = cross
r["left_on_bass_outside"] = round(back, 2)
r["checks"]["left_hand_crosses"] = all(c["left_on_treble"] >= 0.5 and c["left_above_right"] for c in cross.values()) and back >= 0.75

# The right hand's onsets per bar.
onsets = {b: len({n["when"] for n in by["right", b]}) for b in range(1, last + 1)}
r["right_onsets"] = onsets
r["checks"]["right_hand_goes_on"] = all(onsets.get(b, 0) > 0 for b in range(1, 17)) and all(onsets.get(b, 0) >= 2 for b in CROSS)

# Text that names a hand or the crossing: L.H., m.s., m.g., R.H., m.d.,
# left, right, hand, cross, over, under, loco.
HAND = re.compile(r"\b([lr]\.?\s?h\b|m\.?\s?[sgd]\b|left|right|hands?|cross|over|under|loco)", re.I)
marks = [(t["bar"], t["what"]) for t in texts if t["kind"] in ("text", "span", "mark") and HAND.search(t["what"])]
# A dashed line that names a hand marks its own end as the release.
for t in texts:
    if t["kind"] == "span" and HAND.search(t["what"]):
        end = next((u for u in texts if u["kind"] == "spanend" and u["voice"] == t["voice"] and u["when"] > t["when"]), None)
        if end:
            marks.append((end["bar"], "end of: " + t["what"]))
r["marks"] = marks
r["checks"]["crossing_marked"] = any(b in (8, 9) for b, _ in marks) and any(b in (12, 13) for b, _ in marks)

# Stems wherever both hands share a staff.
cross_notes = [n for n in notes if n["bar"] in CROSS and n["hand"] in ("left", "right")]
both = {(n["bar"], n["staff"]) for n in cross_notes if n["hand"] == "left"} & {(n["bar"], n["staff"]) for n in cross_notes if n["hand"] == "right"}
shared = [n for n in cross_notes if (n["bar"], n["staff"]) in both]
apart = sum((n["hand"] == "left" and n["stem"] == "1") or (n["hand"] == "right" and n["stem"] == "-1") for n in shared)
r["stems_apart"] = f"{apart} of {len(shared)}"
r["checks"]["stems_split"] = not shared or apart / len(shared) >= 0.75

finish(r, out)
