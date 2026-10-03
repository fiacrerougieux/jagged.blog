# jagged.blog evidence

The prompts, checkers and scored files behind [jagged.blog](https://jagged.blog).

- `tasks/` has each task's prompt, checks, checker and the known-bad files it fails.
- `results/` has each file a model wrote and the render I scored.
- `results.json` lists every run with its checks and cost.
- `scripts/jaggedness.py` builds the per-model table of how uneven each model is across tasks.
- `scripts/gaps.py` lists the runs each model still needs on the core tasks, with a cost estimate.
- `env/Dockerfile` builds the image the checkers run in.

The method is on [the Three Shots page](https://jagged.blog/three-shots/).
