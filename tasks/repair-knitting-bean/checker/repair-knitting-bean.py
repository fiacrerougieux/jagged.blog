#!/usr/bin/env python3
"""Repair of a knitting chart: the bean knits too long.

The file is knitting-bean-cosy-deepseek-v4.1-flash-s2-r8, published on its own
board, where the beans are drawn 18 stitches by 10 rows on cells 1.40 times
wider than they are tall, so they knit 2.43 long against the 1.3 to 1.8 band.
Chart, cells and key all pass, so the repair is the motif and nothing else.

Written 2026-10-19, before any model saw the prompt.
"""
import os
import runpy

os.environ["REPAIR_CHECKER"] = "knitting-cosy.py"
os.environ["REPAIR_TARGET"] = "bean_knits_true"
os.environ["REPAIR_INPUT"] = "cosy.svg"
os.environ["REPAIR_INPUT_PATH"] = "public/artifacts/knitting-bean-cosy-deepseek-v4.1-flash-s2-r8/cosy.svg"
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_repair.py"), run_name="__main__")
