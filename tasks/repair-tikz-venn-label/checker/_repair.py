#!/usr/bin/env python3
"""Shared grader for a repair case: the same file, one defect put right.

A repair run is handed a file that already exists, and is told what is wrong
with it. Two things a script can see, and the rest is the eye's:

  fixed      the check that failed on the file the model was handed now
             passes, so the defect it was told about is gone. Only emitted
             when the family's own grader decides that check.
  unchanged  every check that passed on the file it was handed still passes,
             read off the same grader run on both files. This is the half a
             make task cannot measure: a fix is only a fix if it leaves the
             rest of the drawing alone, and a run that redraws the picture is
             not the thing the prompt asked for.

Both files go through the family's own grader, so a repair is never scored by
a rule its family does not already use, and the checks are the same words the
board uses for the make.

Written 2026-10-19, before any model saw a repair prompt. The wrapper next to
this file sets the three names; nothing here knows which family it is grading.
"""
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _grade import finish  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

CHECKER = os.environ.get("REPAIR_CHECKER")          # the family's grader, in this folder
TARGET = os.environ.get("REPAIR_TARGET") or None    # the check the model was told to fix
INPUT = os.environ["REPAIR_INPUT"]                  # the file's name, as the model sees it in /work
INPUT_PATH = os.environ.get("REPAIR_INPUT_PATH")    # where it lives in the repo


def grade(path):
    """Run the family's grader on one file and return its checks."""
    out = tempfile.mktemp(suffix=".json")
    try:
        subprocess.run([sys.executable, os.path.join(HERE, CHECKER), path, out],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=240)
        with open(out) as f:
            return json.load(f).get("checks", {})
    except (OSError, ValueError):
        return {}
    finally:
        if os.path.exists(out):
            os.unlink(out)


def find_input(src):
    """The file the model was handed, before the model touched it.

    Not the copy in /work: a repair prompt says "edit that file in place", so
    the model overwrites it and grading against it compares the answer with
    itself. The run booked `order: was True` on the input for all nine seeds of
    2026-10-19-repair-exploded-v60 before this was fixed, and every run read as
    fixed: false for that reason alone.

    run.mjs mounts each input read-only at /given/<name> for grading, which is
    the copy that counts. Checked out here, the published artifact the case
    points at is the same file.
    """
    given = os.path.join("/given", INPUT)
    beside = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(src)))), INPUT)
    for p in (given, os.path.join(ROOT, INPUT_PATH) if INPUT_PATH else None, beside):
        if p and os.path.exists(p):
            return p
    return None


def main():
    src, out = sys.argv[1], sys.argv[2]
    before = find_input(src)
    if before is None:
        finish({"error": f"no input file {INPUT} to compare against", "checks": {}}, out)
        return
    was, now = grade(before), grade(src)
    if not was or not now:
        finish({"error": f"{CHECKER} could not grade one of the two files", "checks": {}}, out)
        return

    checks, notes = {}, []

    # The defect it was told about. Only a check the script decides goes here:
    # when the family leaves the target to the eye, the case says so and the
    # person grading reads it off the two renders.
    if TARGET:
        held = was.get(TARGET)
        fixed = held is False and now.get(TARGET) is True
        checks["fixed"] = fixed
        notes.append(f"{TARGET}: was {held} on the file it was handed, now {now.get(TARGET)}")

    # Everything else that was right, still right. Checks the script left
    # undecided on the input (None) are not a promise either way.
    kept, broke = [], []
    for name, held in was.items():
        if name == TARGET or held is not True:
            continue
        (kept if now.get(name) is True else broke).append(name)
    checks["unchanged"] = not broke
    notes.append("still passing: " + (", ".join(kept) if kept else "nothing else was passing")
                 + (f"; broken by the fix: {', '.join(broke)}" if broke else ""))

    finish({"checks": checks, "detail": "; ".join(notes), "input": os.path.basename(before)}, out)


if __name__ == "__main__":
    main()
