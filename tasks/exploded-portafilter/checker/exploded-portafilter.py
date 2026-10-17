#!/usr/bin/env python3
"""Exploded diagram of the portafilter. The checks are exploded.py's: only the ground
truth it reads from exploded-truth.json differs."""
import os
import runpy

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["EXPLODED_MEMBER"] = "portafilter"
runpy.run_path(os.path.join(HERE, "exploded.py"), run_name="__main__")
