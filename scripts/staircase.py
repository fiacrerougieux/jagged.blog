"""How often each model breaks the staircase, from results.json.

A check's difficulty is the share of other models that fail it: each other
model's fail rate on that check, averaged so a model with many runs counts
once. A smooth model fails checks in that order, hardest first, so its passes
make a staircase. A break is a pair of checks where the model failed the
easier one and passed the harder one.

  J        of every pair of checks where the model passed one and failed the
           other, the share where it failed the easier one. 0 is a perfect
           staircase. 0.5 is a model whose failures ignore difficulty.
  90%      the 5th to 95th percentile of J when each model's runs on each task
           are drawn again with replacement, 2000 times. Wide means few runs.
  p        how often J lands at least as far from 0.5 when the model's pass
           rates are shuffled across its checks, 2000 times. A model that
           ignores difficulty sits at 0.5 on average whatever its pass rate,
           so a small p says the order, or its lack, is not luck.
  top      the pair that adds most to the breaks: the easier check failed,
           the harder one passed.

On pass or fail data J is 1 minus the AUC of difficulty for telling the
checks a model passed from the ones it failed, and (1 - gamma) / 2 with
gamma the Goodman-Kruskal gamma. Two checks of equal difficulty count for
neither side. J is not given, shown as a dash, when a model passed only one
check or none, or failed only one or none: with one pass, J only says where
that pass sits on the ladder.

Only runs graded with the task's current checks are counted, a task counts for
a model only with at least two runs on it, since one run cannot show its noise,
and checks every model passes or every model fails are left out, since they
separate nobody.

    python3 scripts/staircase.py [--min-tasks 3] [--matrix] [--json]
"""
import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent


def load():
    results = json.loads((ROOT / "results.json").read_text())["results"]
    tasks = {}
    for f in (ROOT / "tasks").glob("*/task.json"):
        task = json.loads(f.read_text())
        tasks[task["id"]] = task
    return results, tasks


def rates(runs):
    """Pass rate on each check over these runs, from decided checks only."""
    passed, of = defaultdict(int), defaultdict(int)
    for checks in runs:
        for c, v in checks.items():
            if v is not None:
                of[c] += 1
                passed[c] += v
    return {c: passed[c] / of[c] for c in of}


def breaks(p, difficulty):
    """Of the passed-one-failed-the-other pairs, the share that are the wrong way round."""
    wrong = right = 0.0
    cs = list(p)
    for i in cs:
        for j in cs:
            if difficulty[i] < difficulty[j]:
                wrong += (1 - p[i]) * p[j]
                right += p[i] * (1 - p[j])
    return wrong / (wrong + right) if wrong + right else None


def decided(p):
    """Whether J can say anything: at least two checks passed and two failed."""
    return sum(v > 0 for v in p.values()) >= 2 and sum(v < 1 for v in p.values()) >= 2


def shuffled(p, difficulty, j, rng, draws):
    """Share of shuffles of p across the checks with J at least as far from 0.5."""
    cs, vals = list(p), list(p.values())
    far = n = 0
    for _ in range(draws):
        rng.shuffle(vals)
        v = breaks(dict(zip(cs, vals)), difficulty)
        if v is not None:
            n += 1
            far += abs(v - 0.5) >= abs(j - 0.5) - 1e-12
    return far / n


def top_break(p, difficulty):
    return max(((1 - p[i]) * p[j], i, j) for i in p for j in p if difficulty[i] < difficulty[j])


def table(results, tasks, min_tasks, draws=2000):
    runs = defaultdict(list)
    labels = {}
    for r in results:
        t = tasks.get(r["task"])
        if not t or r.get("checksVersion") != t["checksVersion"]:
            continue
        runs[r["model"], r["task"]].append({f"{r['task']}/{c}": v for c, v in r["checks"].items()})
        labels[r["model"]] = r["label"]
    runs = {k: v for k, v in runs.items() if len(v) >= 2}

    rate = {}
    for (m, t), rs in runs.items():
        for c, v in rates(rs).items():
            rate[m, c] = v
    by_check = defaultdict(dict)
    for (m, c), v in rate.items():
        by_check[c][m] = v
    kept = {c for c, ms in by_check.items() if len(ms) > 1 and max(ms.values()) > min(ms.values())}

    rows, rng = [], random.Random(1)
    for m in labels:
        mine = [t for (mm, t) in runs if mm == m]
        p = {c: v for (mm, c), v in rate.items() if mm == m and c in kept}
        if len({c.split("/")[0] for c in p}) < min_tasks:
            continue
        # Difficulty from the other models, so a model does not set its own bar.
        difficulty = {c: mean(1 - v for o, v in by_check[c].items() if o != m) for c in p if len(by_check[c]) > 1}
        p = {c: v for c, v in p.items() if c in difficulty}
        b = breaks(p, difficulty) if decided(p) else None
        boot = []
        for _ in range(draws if b is not None else 0):
            q = {}
            for t in mine:
                rs = runs[m, t]
                q.update(rates([rng.choice(rs) for _ in rs]))
            q = {c: v for c, v in q.items() if c in p}
            v = breaks(q, difficulty)
            if v is not None:
                boot.append(v)
        boot.sort()
        rows.append({
            "model": m,
            "label": labels[m],
            "tasks": len({c.split("/")[0] for c in p}),
            "checks": len(p),
            "runs": sum(len(runs[m, t]) for t in mine),
            "breaks": b,
            "low": boot[int(0.05 * len(boot))] if boot else None,
            "high": boot[int(0.95 * len(boot)) - 1] if boot else None,
            "p": shuffled(p, difficulty, b, rng, draws) if b is not None else None,
            "top": top_break(p, difficulty)[1:] if b is not None else None,
            "pass": p,
            "difficulty": difficulty,
        })
    rows.sort(key=lambda r: (r["breaks"] is None, -(r["breaks"] or 0)))
    return rows


def markdown(rows, matrix):
    out = ["| Model | Tasks | Checks | Runs | J | 90% | p | Top break |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["breaks"] is None:
            out.append(f"| {r['label']} | {r['tasks']} | {r['checks']} | {r['runs']} | - | | | |")
            continue
        top = f"failed {r['top'][0]}, passed {r['top'][1]}"
        out.append(f"| {r['label']} | {r['tasks']} | {r['checks']} | {r['runs']} | **{r['breaks']:.2f}** | {r['low']:.2f} to {r['high']:.2f} | {r['p']:.2f} | {top} |")
    if matrix:
        for r in rows:
            out += ["", f"{r['label']}, easiest check first: difficulty, then pass rate"]
            for c in sorted(r["pass"], key=r["difficulty"].get):
                out.append(f"  {r['difficulty'][c]:.2f}  {r['pass'][c]:.2f}  {c}")
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--min-tasks", type=int, default=3)
    parser.add_argument("--matrix", action="store_true", help="each model's checks, easiest first")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    rows = table(*load(), args.min_tasks)
    print(json.dumps(rows, indent=2) if args.json else markdown(rows, args.matrix))


if __name__ == "__main__":
    main()
