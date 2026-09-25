#!/usr/bin/env python3
"""A triangle-wave oscillator, measured from its own trace.

Re-runs the netlist, reads the first vector it saved with wrdata, and measures
the second half of the run, after start-up: frequency, peak to peak, how
straight each ramp is and whether rise and fall match. It also reads the
netlist, because a PULSE or SIN source would pass every number above.
"""
import glob, os, re, shutil, subprocess, sys, tempfile
import numpy as np
from _grade import finish

F0, VPP = 1000.0, 2.0          # what the prompt asks for
TOL = 0.10                     # on frequency and on peak to peak
BEND = 0.03                    # worst ramp deviation from a straight line, as a share of Vpp
SYM = 1.25                     # longest over shortest of rise and fall time

src, out = sys.argv[1], sys.argv[2]
r = {"checks": {}}
T = tempfile.mkdtemp()
shutil.copy(src, os.path.join(T, "circuit.cir"))
net = open(src, errors="replace").read()

# --- the netlist: only DC may drive it ---------------------------------------
lines, inctl = [], False
for raw in net.splitlines():
    l = raw.strip()
    low = l.lower()
    if low.startswith(".control"): inctl = True; continue
    if low.startswith(".endc"): inctl = False; continue
    if inctl or not l or l[0] in "*;": continue
    if l.startswith("+") and lines: lines[-1] += " " + l[1:]; continue
    lines.append(l.split(";")[0])
banned = []
waveform = re.compile(r"\b(pulse|sin|pwl|exp|sffm|am|trnoise|trrandom)\s*\(", re.I)
models = {m.group(1).lower(): m.group(2).lower() for m in re.finditer(r"^\.model\s+(\S+)\s+(\w+)", "\n".join(lines), re.I | re.M)}
for l in lines:
    k = l[0].lower()
    if k in "vi" and waveform.search(l):
        banned.append(l)
    elif k in "befgh" and re.search(r"\btime\b", l, re.I):
        banned.append(l)
    elif k == "a":
        toks = l.split()
        if toks and models.get(toks[-1].lower()) in {"square", "triangle", "sine", "oneshot", "pwl", "filesource"}:
            banned.append(l)
r["time_sources"] = banned
r["checks"]["dc_sources_only"] = not banned

# --- run it ------------------------------------------------------------------
try:
    subprocess.run(["ngspice", "-b", "circuit.cir"], cwd=T, capture_output=True, timeout=120)
except subprocess.TimeoutExpired:
    pass
files = sorted(f for f in glob.glob(os.path.join(T, "*.txt")))
rows = []
for f in files:
    for line in open(f, errors="replace"):
        try:
            rows.append([float(v) for v in line.split()])
        except ValueError:
            continue
    if rows:
        r["trace"] = os.path.basename(f) + " col 1"
        break
r["checks"]["runs"] = len(rows) > 100
if not r["checks"]["runs"]:
    r["error"] = "ngspice wrote no waveform file"
    finish(r, out); sys.exit()

a = np.array([row[:2] for row in rows if len(row) >= 2])
t, v = a[:, 0], a[:, 1]
end = t.max()
r["sim_end_ms"] = round(end * 1e3, 2)
# Resample the second half on a uniform grid, 200 points per expected period.
g = np.arange(end / 2, end, 1 / (F0 * 200))
order = np.argsort(t)
y = np.interp(g, t[order], v[order])
mid = (y.max() + y.min()) / 2
s = y > mid
rise = np.where(~s[:-1] & s[1:])[0]
fall = np.where(s[:-1] & ~s[1:])[0]
cycles = len(rise) - 1
r["cycles_measured"] = int(max(cycles, 0))
r["checks"]["oscillates"] = bool(cycles >= 4 and (y.max() - y.min()) > 0.1)

ok_f = ok_pp = ok_lin = ok_sym = False
if r["checks"]["oscillates"]:
    f = cycles / (g[rise[-1]] - g[rise[0]])
    r["frequency_hz"] = round(float(f), 1)
    ok_f = abs(f - F0) <= TOL * F0
    # Extremes: the peak between each rise and the next fall, the trough between
    # each fall and the next rise.
    ext = []
    for i in rise:
        j = fall[fall > i]
        if len(j): ext.append((int(i + np.argmax(y[i:j[0] + 1])), "peak"))
    for i in fall:
        j = rise[rise > i]
        if len(j): ext.append((int(i + np.argmin(y[i:j[0] + 1])), "trough"))
    ext.sort()
    pp = [abs(y[b] - y[a_]) for (a_, _), (b, _) in zip(ext, ext[1:])]
    vpp = float(np.median(pp)) if pp else 0.0
    r["vpp"] = round(vpp, 3)
    ok_pp = abs(vpp - VPP) <= TOL * VPP
    bends, ups, downs = [], [], []
    for (i, kind), (j, _) in zip(ext, ext[1:]):
        n = j - i
        if n < 10: continue
        k0, k1 = i + n // 10, j - n // 10       # the middle 80% of the ramp
        x, z = g[k0:k1], y[k0:k1]
        fit = np.polyval(np.polyfit(x, z, 1), x)
        bends.append(float(np.max(np.abs(z - fit))) / max(vpp, 1e-9))
        (downs if kind == "peak" else ups).append(g[j] - g[i])
    if bends:
        r["worst_bend"] = round(max(bends), 4)
        ok_lin = max(bends) <= BEND
    if ups and downs:
        ratio = max(np.median(ups), np.median(downs)) / min(np.median(ups), np.median(downs))
        r["rise_fall_ratio"] = round(float(ratio), 3)
        ok_sym = ratio <= SYM
r["checks"]["frequency_1khz"] = bool(ok_f)
r["checks"]["vpp_2v"] = bool(ok_pp)
r["checks"]["straight_ramps"] = bool(ok_lin)
r["checks"]["symmetric"] = bool(ok_sym)
r["detail"] = (f"{r.get('frequency_hz', '-')} Hz, {r.get('vpp', '-')} Vpp, worst bend {r.get('worst_bend', '-')}, "
               f"rise/fall {r.get('rise_fall_ratio', '-')}" + (f"; time-driven source: {banned[0]}" if banned else ""))
finish(r, out)
