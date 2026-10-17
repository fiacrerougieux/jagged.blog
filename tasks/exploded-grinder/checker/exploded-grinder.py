#!/usr/bin/env python3
"""Exploded diagram of the grinder. The checks are exploded.py's: only the ground
truth it reads from exploded-truth.json differs."""
import os
import runpy

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["EXPLODED_MEMBER"] = "grinder"
runpy.run_path(os.path.join(HERE, "exploded.py"), run_name="__main__")
