"""Helpers the CI/CD workflows call, kept in Python so they are unit-tested (ticket 05).

Usage (from the repo root):
    python -m analytics_platform.cicd build <state_dir>          # slim CI: dbt build into ci_pr_<n>_*
    python -m analytics_platform.cicd drop-list <pr_number>      # stdin: `databricks schemas list -o json`
    python -m analytics_platform.cicd tag <sha> <yyyy-mm-dd>     # prints prod-<date>-<short sha>
"""

import sys
from datetime import date
from pathlib import Path

DBT_DIR = Path(__file__).resolve().parents[2] / "dbt"


def build_args(state_dir: Path) -> list[str]:
    """dbt arguments for slim CI.

    TODO(ticket 05):
    - If state_dir holds a manifest.json (staging's last deploy), build only what changed plus
      everything downstream of it, and read unchanged parents from staging instead of rebuilding them.
    - If it doesn't (the very first run), build everything: there is nothing to compare against.
    - Always --target ci.
    Docs: https://docs.getdbt.com/reference/node-selection/syntax#about-node-selection (state:, --defer)
    """
    raise NotImplementedError


def pr_schemas(schema_names: list[str], pr_number: int) -> list[str]:
    """The schemas belonging to one PR, sorted, so closing PR 1 never drops PR 12's.

    TODO(ticket 05): keep the names that start with this PR's prefix. Careful: what does
    "ci_pr_1" match that it shouldn't?
    """
    raise NotImplementedError


def prod_tag(day: date, sha: str) -> str:
    """The git tag for a prod deploy, e.g. prod-2026-11-26-3e59ab6 (7-character short SHA).

    TODO(ticket 05)
    """
    raise NotImplementedError


def main(argv: list[str]) -> int:
    """Dispatch on argv[0]: build, drop-list or tag (see the module docstring).

    TODO(ticket 05):
    - build: run `dbt` with build_args(...) in DBT_DIR, with DBT_PROFILES_DIR set to DBT_DIR on top of
      the current environment (subprocess.run, check=False). Return dbt's exit code.
      Ruff's S603/S607 will flag the call. The arguments are fixed strings, not user input, so a
      `# noqa: S603, S607` with that reason is the honest fix.
    - drop-list: read the JSON list from stdin, print each of the PR's schema names on its own line.
    - tag: print the tag. The workflow passes today's UTC date, so this function stays pure.
    """
    raise NotImplementedError


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
