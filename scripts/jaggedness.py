"""How uneven each model is across tasks, from results.json.

A model's score on a task is the mean of passed/of over its runs. That score is
read as model level + task difficulty + how this model does on this task + noise.
The first two are fitted together over every model and task, and what is left
over for each cell is the model's surprise on that task. Jaggedness is the
spread of those surprises, beyond what run-to-run noise alone would give.

Columns:
  range   best minus worst surprise. Grows with the number of tasks.
  sd      spread of the surprises.
  noise   spread that run-to-run noise alone would give, from the pooled
          variance between runs of the same model on the same task.
  J       sd with the noise taken out, sqrt(max(0, sd^2 - noise^2)). The headline.
  dip     the model's worst surprise, with z = dip / its noise. Below about -2
          is unlikely to be noise.

Only runs graded with the task's current checks are counted, and tasks every
model scored the same on are left out, since they separate nobody.

    python3 scripts/jaggedness.py [--min-tasks 3] [--json]
"""
import argparse
import json
from collections import defaultdict
from math import sqrt
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent


def load():
    results = json.loads((ROOT / "results.json").read_text())["results"]
    current = {}
    for f in (ROOT / "tasks").glob("*/task.json"):
        task = json.loads(f.read_text())
        current[task["id"]] = task["checksVersion"]
    return results, current


def fit(cell):
    """Model level and task difficulty, fitted together by alternating means."""
    level, difficulty = defaultdict(float), defaultdict(float)
    by_task, by_model = defaultdict(list), defaultdict(list)
    for m, t in cell:
        by_task[t].append(m)
        by_model[m].append(t)
    for _ in range(200):
        for t, ms in by_task.items():
            difficulty[t] = mean(cell[m, t] - level[m] for m in ms)
        for m, ts in by_model.items():
            level[m] = mean(cell[m, t] - difficulty[t] for t in ts)
    return level, difficulty


def table(results, current, min_tasks):
    runs = defaultdict(list)
    cost = defaultdict(list)
    labels = {}
    skipped = 0
    for r in results:
        score = r["score"]
        if r.get("checksVersion") != current.get(r["task"]) or not score["of"]:
            skipped += 1
            continue
        runs[r["model"], r["task"]].append(score["passed"] / score["of"])
        cost[r["model"], r["task"]].append(r["cost"])
        labels[r["model"]] = r["label"]

    by_task = defaultdict(list)
    for (m, t), v in runs.items():
        by_task[t].append(mean(v))
    # A task needs two models that scored differently, or it separates nobody.
    kept = {t for t, v in by_task.items() if len(v) > 1 and max(v) > min(v)}
    runs = {k: v for k, v in runs.items() if k[1] in kept}

    cell = {k: mean(v) for k, v in runs.items()}
    level, difficulty = fit(cell)

    repeat = [v for v in runs.values() if len(v) > 1]
    noise_var = sum((x - mean(v)) ** 2 for v in repeat for x in v) / sum(len(v) - 1 for v in repeat)

    surprises = defaultdict(dict)
    for (m, t), s in cell.items():
        surprises[m][t] = s - level[m] - difficulty[t]

    rows, thin = [], 0
    for m, sur in surprises.items():
        k = len(sur)
        if k < min_tasks:
            thin += 1
            continue
        sd = sqrt(sum(x * x for x in sur.values()) / (k - 1))
        noise = sqrt(mean(noise_var / len(runs[m, t]) for t in sur))
        dip = min(sur, key=sur.get)
        rows.append({
            "model": m,
            "label": labels[m],
            "tasks": k,
            "runs": sum(len(runs[m, t]) for t in sur),
            "mean": mean(cell[m, t] for t in sur),
            "range": max(sur.values()) - min(sur.values()),
            "sd": sd,
            "noise": noise,
            "J": sqrt(max(0.0, sd * sd - noise * noise)),
            "dip": dip,
            "dip_value": sur[dip],
            "dip_z": sur[dip] / sqrt(noise_var / len(runs[m, dip])),
            "cost_per_run": mean(c for t in sur for c in cost[m, t]),
        })
    rows.sort(key=lambda row: (-row["J"], row["dip_z"]))
    return rows, {
        "skipped_runs": skipped,
        "models_below_min_tasks": thin,
        "run_sd": sqrt(noise_var),
        "difficulty": {t: difficulty[t] for t in sorted(kept)},
    }


def markdown(rows, info, min_tasks):
    out = [
        "| Model | Tasks | Runs | Mean | range | sd | noise | J | Worst dip (z) | $/run |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        out.append(
            f"| {r['label']} | {r['tasks']} | {r['runs']} | {r['mean']:.2f} | {r['range']:.2f} | {r['sd']:.2f} "
            f"| {r['noise']:.2f} | **{r['J']:.2f}** | {r['dip']} {r['dip_value']:+.2f} ({r['dip_z']:+.1f}) "
            f"| {r['cost_per_run']:.3f} |"
        )
    out.append("")
    out.append(
        f"{len(rows)} models with at least {min_tasks} compared tasks. "
        f"{info['models_below_min_tasks']} models left out for fewer. "
        f"{info['skipped_runs']} runs left out for being graded on old checks. "
        f"Run-to-run SD {info['run_sd']:.2f}."
    )
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--min-tasks", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    rows, info = table(*load(), args.min_tasks)
    if args.json:
        print(json.dumps({"rows": rows, **info}, indent=2))
    else:
        print(markdown(rows, info, args.min_tasks))


if __name__ == "__main__":
    main()
