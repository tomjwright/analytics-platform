"""Checks branch names and PR titles against home Standards 1 and 3.

Branch: <type>/<issue>-<short-slug>, or <type>/<short-slug> with no issue.
PR title: <type>: <summary>
"""

import sys

TYPES = ("feat", "fix", "docs", "ci", "refactor", "test", "chore", "perf")


def is_valid_branch_name(name: str) -> bool:
    # TODO(ticket 01): make tests/test_naming.py pass.
    raise NotImplementedError


def is_valid_pr_title(title: str) -> bool:
    # TODO(ticket 01): make tests/test_naming.py pass.
    raise NotImplementedError


def main(argv: list[str]) -> int:
    """Usage: python -m analytics_platform.naming <branch> <pr-title>

    Prints what is wrong and returns 1 if either is invalid, else returns 0.
    """
    # TODO(ticket 01): make tests/test_naming.py pass.
    raise NotImplementedError


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
