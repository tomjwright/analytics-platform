import re
import sys

TYPES = ("feat", "fix", "docs", "ci", "refactor", "test", "chore", "perf")
SLUG = r"[a-z0-9]+(-[a-z0-9]+)*"
BRANCH = re.compile(rf"^({'|'.join(TYPES)})/{SLUG}$")
TITLE = re.compile(rf"^({'|'.join(TYPES)}): \S.*$")


def is_valid_branch_name(name: str) -> bool:
    return BRANCH.match(name) is not None


def is_valid_pr_title(title: str) -> bool:
    return TITLE.match(title) is not None


def main(argv: list[str]) -> int:
    branch, title = argv
    ok = True
    if not is_valid_branch_name(branch):
        print(f"Invalid branch name: {branch}")
        ok = False
    if not is_valid_pr_title(title):
        print(f"Invalid PR title: {title}")
        ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
