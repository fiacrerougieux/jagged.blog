#!/usr/bin/env python3
"""Repair of a V60 exploded diagram: the paper filter is drawn under the cone.

The file is exploded-v60-claude-haiku-5.5-s1-r3, published on 2026-10-08, where
the dripper sits above the paper filter instead of round it. `order` decides it
and exploded-v60.py is the grader, so nothing new is measured here beyond
whether the fix broke the parts, the axis or the fit it already had.

Written 2026-10-19, before any model saw the prompt.
"""
import os
import runpy

os.environ["REPAIR_CHECKER"] = "exploded-v60.py"
os.environ["REPAIR_TARGET"] = "order"
os.environ["REPAIR_INPUT"] = "v60.svg"
os.environ["REPAIR_INPUT_PATH"] = "public/artifacts/exploded-v60-claude-haiku-5.5-s1-r3/v60.svg"
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_repair.py"), run_name="__main__")
