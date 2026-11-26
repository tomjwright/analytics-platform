"""Ticket 05's CI/CD helpers: slim CI arguments, PR schema cleanup and the prod tag."""

import io
import json
import subprocess
from datetime import date

from analytics_platform.cicd import DBT_DIR, build_args, main, pr_schemas, prod_tag


def test_the_first_run_has_no_manifest_so_it_builds_everything(tmp_path):
    assert build_args(tmp_path) == ["build", "--target", "ci"]


def test_with_a_manifest_it_builds_only_changed_models_and_defers_the_rest(tmp_path):
    (tmp_path / "manifest.json").write_text("{}")
    assert build_args(tmp_path) == [
        "build",
        "--target",
        "ci",
        "--select",
        "state:modified+",
        "--defer",
        "--state",
        str(tmp_path),
    ]


def test_closing_a_pr_drops_only_its_own_schemas():
    names = ["silver", "ci_pr_1_silver", "ci_pr_12_silver", "dbt_tom_silver", "ci_pr_1_gold", "ci_pr_10_gold"]
    assert pr_schemas(names, 1) == ["ci_pr_1_gold", "ci_pr_1_silver"]


def test_a_pr_with_no_schemas_drops_nothing():
    assert pr_schemas(["bronze", "silver"], 7) == []


def test_the_prod_tag_has_the_date_and_a_short_sha():
    assert prod_tag(date(2026, 11, 26), "3e59ab6c0ffee1234567890abcdef1234567890a") == "prod-2026-11-26-3e59ab6"


def test_main_build_runs_dbt_in_the_project_with_its_profile(tmp_path, monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert main(["build", str(tmp_path)]) == 0
    [(args, kwargs)] = calls
    assert args == ["dbt", "build", "--target", "ci"]
    assert kwargs["cwd"] == DBT_DIR
    assert kwargs["env"]["DBT_PROFILES_DIR"] == str(DBT_DIR)
    assert "PATH" in kwargs["env"]


def test_main_build_fails_when_dbt_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs: subprocess.CompletedProcess(args, 1))
    assert main(["build", str(tmp_path)]) == 1


def test_main_drop_list_prints_the_prs_schemas(monkeypatch, capsys):
    listing = [{"name": "ci_pr_3_silver"}, {"name": "silver"}, {"name": "ci_pr_3_gold"}]
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(listing)))
    assert main(["drop-list", "3"]) == 0
    assert capsys.readouterr().out.splitlines() == ["ci_pr_3_gold", "ci_pr_3_silver"]


def test_main_tag_prints_the_tag(capsys):
    assert main(["tag", "3e59ab6c0ffee", "2026-11-26"]) == 0
    assert capsys.readouterr().out.strip() == "prod-2026-11-26-3e59ab6"
