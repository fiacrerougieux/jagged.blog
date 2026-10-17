#!/usr/bin/env python3
"""Twelve tips, exactly one polytomy of four, every root-to-tip path the same length."""
import io
import re
import sys
from _grade import finish

src, out = sys.argv[1], sys.argv[2]
text = open(src, errors="replace").read().strip()
r = {"checks": {}}
r["checks"]["ends_with_semicolon"] = text.endswith(";")
# 2026-10-10: Newick allows no blanks inside an unquoted label, and Biopython
# reads "Pink Bourbon" as just "Bourbon". The tree passed whenever the cut-down
# names happened not to collide, and failed as "not distinct" when they did.
bare = re.sub(r"\[[^\]]*\]", "", re.sub(r"'(?:[^']|'')*'", "''", text))
r["checks"]["no_blank_in_unquoted_name"] = not re.search(r"[^\s,():;]\s+[^\s,():;]", bare)
try:
    from Bio import Phylo
    tree = Phylo.read(io.StringIO(text), "newick")
except Exception as e:
    r["error"] = f"does not parse as Newick: {e}"
    finish(r, out); sys.exit()
tips = tree.get_terminals()
r["tips"] = len(tips)
r["checks"]["twelve_tips"] = len(tips) == 12
r["checks"]["tips_named_and_distinct"] = all(t.name for t in tips) and len({t.name for t in tips}) == len(tips)
# 2026-10-10: "twelve coffee cultivars", and T1..T12 passed. Half or more of the
# names looking like numbered placeholders fails; real lines like SL28 or T8667
# do not match.
PLACEHOLDER = re.compile(r"^(?:taxon|tip|leaf|cultivar|species|sp|otu|seq|t|a)?[_ ]?\d{1,2}$|^[A-La-l]$", re.I)
r["checks"]["names_not_placeholders"] = sum(bool(PLACEHOLDER.match(t.name or "")) for t in tips) < 6
d = [tree.distance(tree.root, t) for t in tips]
r["spread"] = max(d) - min(d) if d else None
r["checks"]["ultrametric"] = bool(d) and max(d) - min(d) < 1e-6 * max(1.0, max(d))
r["checks"]["branch_lengths_present"] = all(c.branch_length is not None for c in tree.find_clades() if c is not tree.root)
# 2026-10-10: a negative branch can square up a path that is too long, and
# passed as ultrametric.
r["checks"]["no_negative_branches"] = all((c.branch_length or 0) >= 0 for c in tree.find_clades())
multi = sorted(len(c.clades) for c in tree.get_nonterminals() if len(c.clades) > 2)
r["polytomies"] = multi
r["checks"]["exactly_one_polytomy_of_four"] = multi == [4]
# 2026-10-10: a node with one child is not a binary split, and passed.
r["checks"]["no_single_child_nodes"] = all(len(c.clades) >= 2 for c in tree.get_nonterminals())
finish(r, out)
