#!/usr/bin/env python3
"""An espresso boiler thermostat, decided from its netlist and its own trace.

Written 2026-09-22, after five results had been scored by eye on the two
checks that read the circuit. It re-runs the netlist, reads back the
temperature it writes with wrdata, and decides all five checks:

  analogue    the node that temperature is read from has a capacitor on it
              (the thermal mass), a resistor to a fixed ambient (a node held
              by a DC source, or ground), and something else feeding it (the
              heater). The loss has to matter: resistance times capacitance,
              the cooling time constant, is under a day
  hysteresis  once in band the heater cycles slowly with a real swing, so the
              switch turns on low and off high. A single-threshold switch on
              a one-node boiler sits at the set point and chatters, with a
              swing near zero and cycles a timestep long. The known gap: a
              single threshold behind a second thermal node could overshoot
              into a sawtooth that passes this. So it also asks for a switch
              that remembers, a SW or CSW model with vh > 0 or a behavioural
              source that reads its own output, and says which it found.
  cold        the trace starts within 15 to 30 C and the transient uses uic
              or an .ic, so the start is not a DC operating point
  band        once it first reaches 92 it never leaves 92 to 96 (0.25 C slack
              for the timestep)
  wrdata      a wrdata line in .control, and the file actually appears
"""
import glob, os, re, shutil, subprocess, sys, tempfile
import numpy as np
from _grade import finish

LO, HI, SLACK = 92.0, 96.0, 0.25
MIN_SWING, MIN_PERIOD = 1.0, 2.0        # C, and seconds per heater cycle

src, out = sys.argv[1], sys.argv[2]
r = {"checks": {}}
T = tempfile.mkdtemp()
shutil.copy(src, os.path.join(T, "circuit.cir"))
net = open(src, errors="replace").read()

# --- parse ------------------------------------------------------------------
lines, ctl, inctl = [], [], False
for i, raw in enumerate(net.splitlines()):
    l = raw.strip()
    low = l.lower()
    if low.startswith(".control"): inctl = True; continue
    if low.startswith(".endc"): inctl = False; continue
    if i == 0: continue                       # ngspice reads line one as the title
    if not l or l[0] in "*;": continue
    l = re.split(r"\s[;$]\s|\s\$", l)[0].strip()
    tgt = ctl if inctl else lines
    if l.startswith("+") and tgt: tgt[-1] += " " + l[1:]; continue
    tgt.append(l)
elements = [l for l in lines if not l.startswith(".")]
params = {}
for l in lines:
    if l.lower().startswith(".param"):
        for k, v in re.findall(r"(\w+)\s*=\s*\{?([^\s{}]+)\}?", l[6:]):
            params[k.lower()] = v.lower()
dot = [l.lower() for l in lines if l.startswith(".")]

def nodes_of(l):
    toks = re.sub(r"[(),]", " ", l).split()
    k = toks[0][0].lower()
    if k in "rcliv": return [x.lower() for x in toks[1:3]]
    if k in "befgh": return [x.lower() for x in toks[1:3]]
    if k in "sw": return [x.lower() for x in toks[1:3]]
    if k in "dq": return [x.lower() for x in toks[1:3]]
    return [x.lower() for x in toks[1:3]]

GND = {"0", "gnd"}

# --- wrdata and the temperature node -----------------------------------------
wr = [l for l in ctl if l.lower().startswith("wrdata")] + [l for l in lines if l.lower().startswith(".wrdata")]
r["checks"]["wrdata"] = bool(wr)
alias = {}
for l in ctl:
    m = re.match(r"^let\s+(\w+)\s*=\s*(.+)$", l, re.I)
    if m: alias[m.group(1).lower()] = m.group(2).strip()
node = None
if wr:
    args = wr[0].split()[2:]
    for a in args:
        e = alias.get(a.lower(), a)
        m = re.search(r"v\(\s*([\w.]+)\s*\)", e, re.I)
        if m: node = m.group(1).lower(); break
        if re.fullmatch(r"[\w.]+", e): node = e.lower(); break
r["temperature_node"] = node

# --- analogue ------------------------------------------------------------------
fixed = set(GND)                           # nodes a DC source holds to ground
for l in elements:
    if l[0].lower() == "v":
        a, b = nodes_of(l)
        if (a in GND) != (b in GND) and not re.search(r"\b(pulse|sin|pwl|exp)\s*\(", l, re.I):
            fixed.add(b if a in GND else a)
on = [l for l in elements if node and node in nodes_of(l)]
mass = [l for l in on if l[0].lower() == "c" and (set(nodes_of(l)) - {node}) <= fixed]
loss = [l for l in on if l[0].lower() == "r" and (set(nodes_of(l)) - {node}) <= fixed]

def value(l):
    """An element's value, from a number or a {param} that .param defines."""
    tok = re.sub(r"(?i)\bic\s*=.*$", "", l).split()[3] if len(l.split()) > 3 else ""
    tok = tok.strip("{}").lower()
    tok = params.get(tok, tok)
    m = re.match(r"^([-+\d.e]+)(meg|[tgkmunpf])?", tok)
    if not m: return None
    mult = {"t": 1e12, "g": 1e9, "meg": 1e6, "k": 1e3, "m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15}
    try: return float(m.group(1)) * mult.get(m.group(2) or "", 1)
    except ValueError: return None
tau = None
if mass and loss:
    cs = [value(l) for l in mass]; rs = [value(l) for l in loss]
    if None not in cs and None not in rs:
        rpar = 1 / sum(1 / x for x in rs)
        tau = rpar * sum(cs)
        r["loss_time_constant_s"] = round(tau, 1)
        if tau > 86400: loss = []
heat = [l for l in on if l not in mass and l not in loss]
r["mass"], r["loss"], r["heater"] = mass[:2], loss[:2], heat[:3]

# --- hysteresis in the circuit -------------------------------------------------
models = {}
for l in dot:
    m = re.match(r"^\.model\s+(\S+)\s+(\w+)\s*\(?(.*)$", l)
    if m: models[m.group(1)] = (m.group(2), m.group(3))
memory = []
for name, (kind, params) in models.items():
    m = re.search(r"\bvh\s*=\s*\{?\s*([-+\d.e]+)", params)
    if kind in ("sw", "csw") and m and float(m.group(1)) > 0:
        memory.append(f"{kind} model {name} with vh={m.group(1)}")
    elif kind in ("sw", "csw") and re.search(r"\bvh\s*=\s*\{", params):
        memory.append(f"{kind} model {name} with a parameter vh")
for l in elements:
    if l[0].lower() in "be":
        out_nodes = set(nodes_of(l)) - GND
        body = l.split("=", 1)[-1].lower()
        if any(re.search(rf"v\(\s*{re.escape(n)}\s*\)", body) for n in out_nodes):
            memory.append(f"behavioural source reading its own output: {l.split()[0]}")
r["memory"] = memory

uic = any("uic" in l for l in dot if l.startswith(".tran")) or any(
    re.match(r"^tran\b.*\buic\b", l, re.I) for l in ctl) or any(l.startswith(".ic") for l in dot) or bool(
    re.search(r"\bic\s*=", "\n".join(l for l in elements if l[0].lower() == "c" and node in nodes_of(l)), re.I))

# --- run it ------------------------------------------------------------------
try:
    subprocess.run(["ngspice", "-b", "circuit.cir"], cwd=T, capture_output=True, timeout=180)
except subprocess.TimeoutExpired:
    pass
want = wr[0].split()[1] if wr and len(wr[0].split()) > 1 else None
files = [os.path.join(T, want)] if want and os.path.exists(os.path.join(T, want)) else []
if not files and want and os.path.exists(os.path.join(T, want + ".data")):
    files = [os.path.join(T, want + ".data")]
rows = []
for f in files:
    for line in open(f, errors="replace"):
        try:
            rows.append([float(v) for v in line.split()])
        except ValueError:
            continue
r["checks"]["wrdata"] = bool(wr) and len(rows) > 10
if not r["checks"]["wrdata"]:
    for k in ("analogue", "hysteresis", "cold", "band"): r["checks"][k] = False
    r["error"] = "no wrdata file with a trace in it" if wr else "no wrdata line in .control"
    finish(r, out); sys.exit()

a = np.array([row[:2] for row in rows if len(row) >= 2])
order = np.argsort(a[:, 0], kind="stable")
t, v = a[order, 0], a[order, 1]
r["sim_end_s"] = round(float(t.max()), 1)
r["start_c"] = round(float(v[0]), 2)

r["checks"]["analogue"] = bool(mass and loss and heat)
r["checks"]["cold"] = bool(15 <= v[0] <= 30 and uic)

hit = np.where(v >= LO)[0]
if len(hit):
    after = v[hit[0]:]
    r["band_min"], r["band_max"] = round(float(after.min()), 2), round(float(after.max()), 2)
    r["checks"]["band"] = bool(after.min() >= LO - SLACK and after.max() <= HI + SLACK and t.max() >= 1150)
else:
    r["checks"]["band"] = False

# The settled cycle: turning points of the trace once in band, the heater
# switching on at each trough and off at each peak.
swing, period = 0.0, 0.0
if len(hit) and t[-1] - t[hit[0]] > 60:
    k = t >= t[hit[0]] + 10
    tt, vv = t[k], v[k]
    g = np.arange(tt[0], tt[-1], 0.05)
    y = np.interp(g, tt, vv)
    d = np.sign(np.diff(y))
    nz = np.where(d != 0)[0]
    d = d[nz]
    turns = nz[np.where(d[:-1] != d[1:])[0] + 1]
    peaks = [i for i in turns if y[i] >= y[max(i - 1, 0)]]
    troughs = [i for i in turns if y[i] < y[max(i - 1, 0)]]
    if len(peaks) >= 2 and len(troughs) >= 2:
        swing = float(np.median(y[peaks]) - np.median(y[troughs]))
        period = float((g[peaks[-1]] - g[peaks[0]]) / (len(peaks) - 1))
        r["turn_off_c"], r["turn_on_c"] = round(float(np.median(y[peaks])), 2), round(float(np.median(y[troughs])), 2)
    else:
        swing = float(y.max() - y.min())
r["swing_c"], r["period_s"] = round(swing, 3), round(period, 2)
r["checks"]["hysteresis"] = bool(swing >= MIN_SWING and period >= MIN_PERIOD and memory)

bits = [f"starts {r['start_c']} C"]
if "turn_on_c" in r: bits.append(f"heater on at {r['turn_on_c']}, off at {r['turn_off_c']}, every {r['period_s']} s")
else: bits.append(f"settled swing {r['swing_c']} C")
if "band_min" in r: bits.append(f"in band {r['band_min']} to {r['band_max']}")
if not memory: bits.append("no switch with memory found")
if not (mass and loss and heat): bits.append("temperature node lacks " + ", ".join(
    n for n, x in (("a mass", mass), ("a loss to ambient", loss), ("a heater", heat)) if not x))
r["detail"] = "; ".join(bits)
if not all(r["checks"].values()):
    r["detail"] = "failed " + ", ".join(k for k, x in r["checks"].items() if not x) + ": " + r["detail"]
finish(r, out)
