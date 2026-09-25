# jagged.blog evidence

The prompts, checkers and scored files behind [jagged.blog](https://jagged.blog).

- `tasks/` has each task's prompt, checks, checker and the known-bad files it fails.
- `results/` has each file a model wrote and the render I scored.
- `results.json` lists every run with its checks and cost.
- `env/Dockerfile` builds the image the checkers run in.

The method is on [the Three Shots page](https://jagged.blog/three-shots/).
