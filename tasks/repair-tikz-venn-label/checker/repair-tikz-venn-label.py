#!/usr/bin/env python3
"""Repair of a Venn diagram: one drink put on a circle's edge.

The file is tikz-coffee-venn-kimi-k3-s1-r3, published on its own board, where
`labels_clear_of_edges` fails on "milkshake" and every other check passes. It is
the one failing Venn whose straddle is a single word, so the repair is one move
rather than six.

Written 2026-10-19, before any model saw the prompt.
"""
import os
import runpy

os.environ["REPAIR_CHECKER"] = "tikz-venn.py"
os.environ["REPAIR_TARGET"] = "labels_clear_of_edges"
os.environ["REPAIR_INPUT"] = "venn.tex"
os.environ["REPAIR_INPUT_PATH"] = "public/artifacts/tikz-coffee-venn-kimi-k3-s1-r3/venn.tex"
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_repair.py"), run_name="__main__")
