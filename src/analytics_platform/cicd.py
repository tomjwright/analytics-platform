"""Helpers the CI/CD workflows call, kept in Python so they are unit-tested (ticket 05).

Usage (from the repo root):
    python -m analytics_platform.cicd build <state_dir>          # slim CI: dbt build into ci_pr_<n>_*
    python -m analytics_platform.cicd drop-list <pr_number>      # stdin: `databricks schemas list -o json`
    python -m analytics_platform.cicd tag <sha> <yyyy-mm-dd>     # prints prod-<date>-<short sha>
    python -m analytics_platform.cicd check-tag <tag>            # exit 1 unless it's a prod-* tag (ticket 06)
"""

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

from analytics_platform.rollback import is_prod_tag

DBT_DIR = Path(__file__).resolve().parents[2] / "dbt"


def build_args(state_dir: Path) -> list[str]:
    """dbt arguments for slim CI: only what changed (plus downstream) when staging's manifest exists.

    With no manifest (the very first run) there is nothing to compare against, so build everything.
    """
    args = ["build", "--target", "ci"]
    if (state_dir / "manifest.json").exists():
        args += ["--select", "state:modified+", "--defer", "--state", str(state_dir)]
    return args


def pr_schemas(schema_names: list[str], pr_number: int) -> list[str]:
    """The schemas belonging to one PR, sorted. The trailing "_" stops PR 1 matching PR 12's."""
    return sorted(name for name in schema_names if name.startswith(f"ci_pr_{pr_number}_"))


def prod_tag(day: date, sha: str) -> str:
    """The git tag for a prod deploy, e.g. prod-2026-11-26-3e59ab6 (7-character short SHA)."""
    return f"prod-{day}-{sha[:7]}"


def main(argv: list[str]) -> int:
    command, *rest = argv
    if command == "build":
        env = {**os.environ, "DBT_PROFILES_DIR": str(DBT_DIR)}
        # Fixed arguments, not user input. The state path is resolved because dbt runs from DBT_DIR.
        result = subprocess.run(["dbt", *build_args(Path(rest[0]).resolve())], cwd=DBT_DIR, env=env, check=False)  # noqa: S603, S607
        return result.returncode
    if command == "drop-list":
        names = [row["name"] for row in json.load(sys.stdin)]
        for name in pr_schemas(names, int(rest[0])):
            print(name)
        return 0
    if command == "tag":
        sha, day = rest
        print(prod_tag(date.fromisoformat(day), sha))
        return 0
    if command == "check-tag":
        if is_prod_tag(rest[0]):
            return 0
        print(f"not a prod tag: {rest[0]!r}", file=sys.stderr)
        return 1
    print(f"unknown command: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
