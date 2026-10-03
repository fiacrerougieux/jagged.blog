"""Which runs each model still needs on the core tasks, and roughly what they cost.

A run counts if it used the task's current prompt and current checks. The cost
estimate is the model's own mean on that task when it has one (exact), else the
task's median over every model (marked ~).

    python3 scripts/gaps.py [--n 3] [--tasks tikz-coffee-venn,svg-french-press,lsystem-pruned-coffee-shrub]
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parent.parent
CORE = "tikz-coffee-venn,svg-french-press,lsystem-pruned-coffee-shrub"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--n", type=int, default=3)
    parser.add_argument("--tasks", default=CORE)
    args = parser.parse_args()
    core = args.tasks.split(",")

    tasks = {t: json.loads((ROOT / "tasks" / t / "task.json").read_text()) for t in core}
    results = json.loads((ROOT / "results.json").read_text())["results"]

    have = defaultdict(lambda: defaultdict(int))
    own_cost = defaultdict(lambda: defaultdict(list))
    task_cost = defaultdict(list)
    labels = {}
    for r in results:
        labels[r["model"]] = r["label"]
        task = tasks.get(r["task"])
        if not task or r.get("promptVersion") != task["version"] or r.get("checksVersion") != task["checksVersion"]:
            continue
        have[r["model"]][r["task"]] += 1
        own_cost[r["model"]][r["task"]].append(r["cost"])
        task_cost[r["task"]].append(r["cost"])

    short = {t: tasks[t].get("short", t) for t in core}
    print("| Model | " + " | ".join(f"{short[t]} ({tasks[t]['version']}/{tasks[t]['checksVersion']})" for t in core) + " | Runs needed | Est. $ |")
    print("|---|" + "---|" * len(core) + "---|---|")
    total_runs, total_cost = 0, 0.0
    for m in sorted(labels, key=lambda m: labels[m].lower()):
        cells, need_m, cost_m, guessed = [], 0, 0.0, False
        for t in core:
            need = max(0, args.n - have[m][t])
            if need and own_cost[m][t]:
                cost_m += need * mean(own_cost[m][t])
            elif need:
                cost_m += need * median(task_cost[t])
                guessed = True
            need_m += need
            cells.append(f"{have[m][t]}/{args.n}" + (f" (+{need})" if need else ""))
        if not need_m:
            continue
        total_runs += need_m
        total_cost += cost_m
        print(f"| {labels[m]} | " + " | ".join(cells) + f" | {need_m} | {'~' if guessed else ''}{cost_m:.2f} |")
    print()
    print(f"{total_runs} runs, about ${total_cost:.2f}. Median $/run: "
          + ", ".join(f"{short[t]} {median(task_cost[t]):.3f}" for t in core) + ".")


if __name__ == "__main__":
    main()
