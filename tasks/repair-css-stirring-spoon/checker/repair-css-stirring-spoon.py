#!/usr/bin/env python3
"""Repair of the stirring spoon: GLM's spoon lies across the mouth of the cup.

The file is css-stirring-spoon-glm-5.3-flashx-s1-r6, published on 2026-10-19,
where the spoon reads as resting on the cup rather than in the drink. Whether
the spoon now reads as inside is the eye's check (`inside`), so the script only
decides the half it can: the brief and the loop that were right on the input
are still right on the output.

Written 2026-10-19, before any model saw the prompt.
"""
import os
import runpy

os.environ["REPAIR_CHECKER"] = "css-stirring-loop.py"
os.environ["REPAIR_INPUT"] = "stir.html"
os.environ["REPAIR_INPUT_PATH"] = "public/artifacts/css-stirring-spoon-glm-5.3-flashx-s1-r6/stir.html"
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_repair.py"), run_name="__main__")
