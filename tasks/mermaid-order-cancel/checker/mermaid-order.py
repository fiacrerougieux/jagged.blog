#!/usr/bin/env python3
"""Run a Mermaid order state machine against fixed traces.

Parses the stateDiagram into a transition table, flattening composite states
(a transition out of a composite applies to every state inside it unless the
inner state has its own), then feeds it event sequences and asks what the
machine does. Nothing here looks at the picture; Mermaid only has to accept it.
"""
import re, subprocess, sys
from collections import defaultdict
from _grade import finish

EVENTS = {"pay", "queue", "start", "finish", "collect", "cancel", "refund"}
HAPPY = ["pay", "queue", "start", "finish", "collect"]
END = "__END__"

src, out = sys.argv[1], sys.argv[2]
r = {"checks": {}}
text = open(src, errors="replace").read()

try:
    p = subprocess.run(["node", "/renderers/snap.mjs", "mermaid", src, "/tmp/order.png"],
                       capture_output=True, text=True, timeout=120)
    r["checks"]["renders"] = p.returncode == 0
except Exception:
    r["checks"]["renders"] = False

# --- parse ---------------------------------------------------------------------
parent, kids, edges = {}, defaultdict(set), []   # edges: (scope, a, b, label)
stack, in_note = ["__TOP__"], False
for raw in text.splitlines():
    l = re.sub(r"%%.*", "", raw).strip()
    if in_note:
        in_note = not l.lower().startswith("end note"); continue
    if not l or re.match(r"^(stateDiagram|direction|classDef|class |style |accTitle|accDescr|---|title)", l):
        continue
    if l.lower().startswith("note "):
        in_note = ":" not in l; continue
    if l == "}":
        if len(stack) > 1: stack.pop()
        continue
    if l == "--":
        continue
    m = re.match(r'^state\s+(?:"[^"]*"\s+as\s+)?([\w.]+)(?:\s*<<\w+>>)?\s*(\{)?\s*$', l)
    if m:
        name = m.group(1)
        parent.setdefault(name, stack[-1]); kids[stack[-1]].add(name)
        if m.group(2): stack.append(name)
        continue
    m = re.match(r"^(\[\*\]|[\w.]+)(?::::\w+)?\s*-->\s*(\[\*\]|[\w.]+)(?::::\w+)?\s*(?::\s*(.*))?$", l)
    if m:
        a, b, lab = m.group(1), m.group(2), (m.group(3) or "").strip()
        scope = stack[-1]
        for s in (a, b):
            if s != "[*]" and s not in parent:
                parent[s] = scope; kids[scope].add(s)
        edges.append((scope, a, b, lab))

composites = {s for s in kids if s != "__TOP__" and kids[s]}
leaves = {s for s in parent if s not in composites}

def ancestors(s):
    while s in parent:
        s = parent[s]; yield s

# Labels: every edge not touching [*] carries exactly one allowed event.
bad_labels = [f"{a} --> {b} : {lab}" for _, a, b, lab in edges
              if a != "[*]" and b != "[*]" and lab.lower() not in EVENTS]
r["bad_labels"] = bad_labels[:6]
r["checks"]["labels"] = not bad_labels

initial = {sc: b for sc, a, b, lab in edges if a == "[*]"}
own = defaultdict(list)            # state -> [(label, target token, scope)]
for sc, a, b, lab in edges:
    if a != "[*]":
        own[a].append((lab.lower(), b, sc))

def resolve(tok, scope, seen=()):
    """A transition target, down to leaves: composites enter at their initial,
    [*] on the right exits the scope through its unlabelled completion edges."""
    if tok == "[*]":
        if scope == "__TOP__" or (scope, "exit") in seen:
            return {END}
        outs = [(b, sc) for lab, b, sc in own.get(scope, []) if lab == ""]
        if not outs:
            return {END}
        return set().union(*(resolve(b, sc, seen + ((scope, "exit"),)) for b, sc in outs))
    if tok in composites:
        if tok not in initial or tok in seen:
            return {tok}
        return resolve(initial[tok], tok, seen + (tok,))
    return {tok}

def moves(s, ev):
    """Targets for event ev from leaf s; the innermost state that handles ev wins."""
    for st in (s, *ancestors(s)):
        hits = [(b, sc) for lab, b, sc in own.get(st, []) if lab == ev]
        if hits:
            return set().union(*(resolve(b, sc) for b, sc in hits))
    return set()

def closure(states):
    """Follow unlabelled edges out of leaves (they break the labelling rule, but
    the machine can still be traced)."""
    todo, seen = list(states), set(states)
    while todo:
        s = todo.pop()
        for t in moves(s, ""):
            if t not in seen:
                seen.add(t); todo.append(t)
    return seen

def is_end(s):
    return s == END or not any(moves(s, e) for e in EVENTS | {""})

nondet = [f"{s} on {e}" for s in leaves for e in EVENTS if len(moves(s, e)) > 1]
r["nondeterministic"] = nondet[:6]
r["checks"]["deterministic"] = not nondet

# The prompt never asks for [*]. Without one, the start is the only top-level
# state nothing points into, if there is exactly one.
if "__TOP__" not in initial:
    targets = {b for _, a, b, _ in edges if a != "[*]"}
    sources = sorted(s for s in kids["__TOP__"] if s not in targets)
    if len(sources) == 1:
        initial["__TOP__"] = sources[0]
start = closure(resolve(initial["__TOP__"], "__TOP__")) if "__TOP__" in initial else set()

def run(trace):
    cur = start
    for i, ev in enumerate(trace):
        nxt = set()
        for s in cur:
            nxt |= moves(s, ev)
        if not nxt:
            return None, f"{ev} not accepted after {' '.join(trace[:i]) or 'placing'}"
        cur = closure(nxt)
    return cur, ""

def reach(states, skip=()):
    """Everything reachable, and the events used on the way, ignoring events in skip."""
    seen, todo, used = set(states), list(states), set()
    while todo:
        s = todo.pop()
        for e in EVENTS | {""}:
            if e in skip:
                continue
            for t in moves(s, e):
                used.add(e)
                if t not in seen:
                    seen.add(t); todo.append(t)
    return seen, used

why = []
cur, err = run(HAPPY)
ok = cur is not None and any(is_end(s) for s in cur)
if not ok: why.append(err or "pay queue start finish collect does not end")
r["checks"]["happy_path"] = ok

cur, err = run(["cancel"])
if cur is None:
    ok = False; why.append(err)
else:
    seen, used = reach(cur)
    ok = "refund" not in used and any(is_end(s) for s in seen)
    if not ok: why.append("an unpaid cancel can reach refund" if "refund" in used else "an unpaid cancel never ends")
r["checks"]["cancel_unpaid_no_refund"] = ok

def must_refund(trace, name):
    cur, err = run(trace)
    if cur is None:
        why.append(err); return False
    if any(is_end(s) for s in cur):
        why.append(f"cancel {name} ends straight away with no refund"); return False
    noref, _ = reach(cur, skip={"refund"})
    if any(is_end(s) for s in noref):
        why.append(f"cancel {name} can end without refund"); return False
    allr, _ = reach(cur)
    if not any(is_end(s) for s in allr):
        why.append(f"cancel {name} never ends"); return False
    return True

r["checks"]["cancel_queued_refunds"] = must_refund(["pay", "queue", "cancel"], "while queued")
r["checks"]["cancel_brewing_refunds"] = must_refund(["pay", "queue", "start", "cancel"], "while brewing")
r["checks"]["cancel_paid_or_ready_refunds"] = (must_refund(["pay", "cancel"], "after paying")
                                               & must_refund(["pay", "queue", "start", "finish", "cancel"], "when ready"))
cur, _ = run(HAPPY + ["cancel"])
r["checks"]["no_cancel_after_collect"] = cur is None
if cur is not None: why.append("a collected order can still be cancelled")
if bad_labels: why.append(f"{len(bad_labels)} transitions without a single allowed event, e.g. {bad_labels[0]}")
if nondet: why.append("nondeterministic: " + ", ".join(nondet[:3]))
if why: r["detail"] = "; ".join(why)
finish(r, out)
