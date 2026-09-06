"""Regenerate tests/golden/request_python_repl.json (plan.md S2.3).

    make golden

Run this only when materialisation is *meant* to change, and read the diff: the
request is what every policy sees, so a change here changes what the whole
policy set can express.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
for path in (REPO_ROOT, HERE, os.path.join(REPO_ROOT, "src")):
    if path not in sys.path:
        sys.path.insert(0, path)

from test_request import GOLDEN, snapshot          # noqa: E402


def main():
    os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
    with open(GOLDEN, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(snapshot(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(f"wrote {os.path.relpath(GOLDEN, REPO_ROOT).replace(os.sep, '/')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
