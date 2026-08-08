"""Run independently structured Behave roots in a shared Python environment."""

from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", nargs="+")
    parser.add_argument("--format", default="progress")
    arguments = parser.parse_args()

    for root in arguments.roots:
        completed = subprocess.run(
            [sys.executable, "-m", "behave", root, "--format", arguments.format],
            check=False,
        )
        if completed.returncode != 0:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
