"""Shared plumbing for graders: every grader writes {pass, checks, detail} and prints one line."""
import json


def finish(result, out):
    checks = result.setdefault("checks", {})
    result["pass"] = bool(checks) and all(checks.values()) and not result.get("error")
    if not result.get("detail"):
        failed = [k for k, v in checks.items() if not v]
        result["detail"] = result.get("error") or ("all checks passed" if result["pass"] else "failed: " + ", ".join(failed))
    with open(out, "w") as f:
        json.dump(result, f, indent=2)
    print(("GRADE PASS: " if result["pass"] else "GRADE FAIL: ") + result["detail"])
