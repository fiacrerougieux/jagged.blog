#!/usr/bin/env python3
"""Exploded diagram of the French press. The checks are exploded.py's: only
the ground truth it reads from exploded-truth.json differs. Used by
svg-french-press-list-first from 2026-10-09; svg-french-press itself still has
no grader, so its published results are not touched."""
import os
import runpy

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["EXPLODED_MEMBER"] = "french-press"
runpy.run_path(os.path.join(HERE, "exploded.py"), run_name="__main__")
