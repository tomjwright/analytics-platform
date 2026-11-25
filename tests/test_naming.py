import pytest

from analytics_platform.naming import is_valid_branch_name, is_valid_pr_title, main


@pytest.mark.parametrize(
    "name",
    [
        "ci/2-repo-skeleton-gates",
        "feat/12-customer-dedup",
        "docs/branch-naming-convention",
        "perf/17-liquid-clustering",
    ],
)
def test_valid_branch_names(name):
    assert is_valid_branch_name(name)


@pytest.mark.parametrize(
    "name",
    [
        "main",
        "devin/1795587942-design-docs",
        "feature/2-ci",
        "ci/2-Repo-Skeleton",
        "ci/2_repo_skeleton",
        "ci/2-",
        "ci/",
        "ci/2-repo--gates",
        "ci/2-repo-gates/extra",
    ],
)
def test_invalid_branch_names(name):
    assert not is_valid_branch_name(name)


@pytest.mark.parametrize("title", ["ci: add the repo skeleton and CI gates", "fix: keep the newest Customer row"])
def test_valid_pr_titles(title):
    assert is_valid_pr_title(title)


@pytest.mark.parametrize(
    "title",
    ["Add the repo skeleton", "ci add gates", "ci:add gates", "feature: add gates", "ci: ", "CI: add gates"],
)
def test_invalid_pr_titles(title):
    assert not is_valid_pr_title(title)


def test_main_returns_0_when_both_are_valid():
    assert main(["ci/2-repo-skeleton-gates", "ci: add the repo skeleton"]) == 0


def test_main_returns_1_and_explains_when_branch_is_invalid(capsys):
    assert main(["devin/123-x", "ci: add the repo skeleton"]) == 1
    assert "branch" in capsys.readouterr().out.lower()


def test_main_returns_1_and_explains_when_title_is_invalid(capsys):
    assert main(["ci/2-repo-skeleton-gates", "Add the repo skeleton"]) == 1
    assert "title" in capsys.readouterr().out.lower()
