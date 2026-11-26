"""Ticket 01's definition of done: each test checks one gate is configured."""

import re
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def workflow_files():
    return sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))


def all_workflow_text():
    return "\n".join(path.read_text() for path in workflow_files())


def pyproject():
    return tomllib.loads((ROOT / "pyproject.toml").read_text())


def test_pr_workflow_exists_and_runs_on_pull_requests():
    workflow = yaml.safe_load((WORKFLOWS / "pr.yml").read_text())
    # PyYAML reads the bare key `on` as the boolean True.
    assert "pull_request" in workflow[True]


def test_every_workflow_defaults_to_read_only_permissions():
    for path in workflow_files():
        workflow = yaml.safe_load(path.read_text())
        assert workflow.get("permissions") == {"contents": "read"}, path.name


def test_every_action_is_pinned_to_a_full_commit_sha():
    for path in workflow_files():
        for ref in re.findall(r"uses:\s*(\S+)", path.read_text()):
            if ref.startswith("./"):
                continue
            assert re.search(r"@[0-9a-f]{40}$", ref), f"{path.name}: {ref}"


def test_workflows_run_every_gate():
    text = all_workflow_text()
    gates = [
        "ruff",
        "mypy",
        "sqlfluff",
        "pytest",
        "mutmut",
        "pip-audit",
        "licen",
        "gitleaks",
        "semgrep",
        "codeql",
        "actionlint",
        "zizmor",
        "analytics_platform.naming",
    ]
    missing = [gate for gate in gates if gate not in text.lower()]
    assert missing == []


def test_ruff_mypy_coverage_and_mutmut_are_configured():
    tool = pyproject().get("tool", {})
    assert "ruff" in tool
    assert tool.get("mypy", {}).get("strict") is True
    assert tool.get("coverage", {}).get("report", {}).get("fail_under", 0) >= 80
    assert "mutmut" in tool


def test_sqlfluff_uses_databricks_dialect_and_dbt_templater():
    config = (ROOT / ".sqlfluff").read_text()
    assert re.search(r"dialect\s*=\s*databricks", config)
    assert re.search(r"templater\s*=\s*dbt", config)


def test_agents_md_lists_the_checks():
    assert "## Checks" in (ROOT / "AGENTS.md").read_text()


def test_downloaded_olist_data_is_never_committed():
    assert "data/" in (ROOT / ".gitignore").read_text().splitlines()
