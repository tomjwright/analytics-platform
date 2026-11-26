"""Ticket 05's offline checks: slim CI, staging-to-prod promotion and PR cleanup.

They read the workflow, bundle and dbt files, and `dbt parse` the ci target, so they run
anywhere without credentials.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
DBT = ROOT / "dbt"
WORKFLOWS = ROOT / ".github" / "workflows"
ARTIFACTS = "/Volumes/staging/ops/artifacts"


def workflow(name):
    return yaml.safe_load((WORKFLOWS / name).read_text())


def job(name, job_key):
    return workflow(name)["jobs"][job_key]


def runs(job_def):
    return "\n".join(step.get("run", "") for step in job_def["steps"])


def ci_manifest(pr_number="7"):
    env = {**os.environ, "DBT_PROFILES_DIR": str(DBT), "DBT_PR_NUMBER": pr_number}
    subprocess.run(["dbt", "parse", "--target", "ci", "--quiet"], cwd=DBT, check=True, env=env)
    return json.loads((DBT / "target" / "manifest.json").read_text())


def bundle_resources():
    merged: dict = {}
    for path in sorted((ROOT / "resources").glob("*.yml")):
        for kind, items in (yaml.safe_load(path.read_text()).get("resources") or {}).items():
            merged.setdefault(kind, {}).update(items)
    return merged


# dbt


@pytest.mark.parametrize(("model", "layer"), [("stg_customers", "silver"), ("dim_customer", "gold")])
def test_ci_builds_in_this_prs_schemas_in_staging(model, layer):
    node = ci_manifest()["nodes"][f"model.analytics_platform.{model}"]
    assert (node["database"], node["schema"]) == ("staging", f"ci_pr_7_{layer}")


def test_ci_reads_stagings_bronze_table():
    source = ci_manifest()["sources"]["source.analytics_platform.bronze.customers"]
    assert (source["database"], source["schema"]) == ("staging", "bronze")


def test_ci_logs_in_as_the_staging_principal_not_with_a_token():
    ci = yaml.safe_load((DBT / "profiles.yml").read_text())["analytics_platform"]["outputs"]["ci"]
    assert ci["auth_type"] == "oauth"
    assert "DATABRICKS_CLIENT_ID" in ci["client_id"]
    assert "DATABRICKS_CLIENT_SECRET" in ci["client_secret"]
    assert "token" not in ci


# Bundle


def test_the_bundle_creates_the_artifacts_volume_in_ops():
    resources = bundle_resources()
    ops = [key for key, schema in resources.get("schemas", {}).items() if schema["name"].endswith("ops")]
    assert len(ops) == 1
    volumes = [v for v in resources["volumes"].values() if v["name"] == "artifacts"]
    assert len(volumes) == 1
    assert volumes[0]["schema_name"] == f"${{resources.schemas.{ops[0]}.name}}"


# Workflows


def test_slim_ci_runs_on_every_pr_as_the_staging_principal():
    dbt_ci = job("pr.yml", "dbt_ci")
    assert dbt_ci["environment"] == "staging"
    assert "github.event.pull_request.number" in dbt_ci["env"]["DBT_PR_NUMBER"]
    commands = runs(dbt_ci)
    assert f"{ARTIFACTS}/manifest.json" in commands
    assert "analytics_platform.cicd build" in commands


def test_slim_ci_skips_forks_which_get_no_secrets():
    assert "github.event.pull_request.head.repo.full_name" in job("pr.yml", "dbt_ci")["if"]


def test_staging_runs_the_tracer_then_publishes_its_manifest():
    commands = runs(job("deploy.yml", "staging"))
    assert "bundle run customer_tracer --target staging" in commands
    assert "dbt parse --target staging" in commands
    assert f"{ARTIFACTS}/manifest.json" in commands
    assert "--overwrite" in commands
    # Only a manifest whose models really ran in staging is safe to defer to.
    assert commands.index("bundle run customer_tracer") < commands.index("dbt parse")


def test_prod_waits_for_staging_then_runs_the_tracer_and_tags_the_release():
    prod = job("deploy.yml", "prod")
    assert prod["needs"] == "staging"
    assert prod["environment"] == "prod"
    assert prod["permissions"] == {"contents": "write"}
    commands = runs(prod)
    assert "bundle run customer_tracer --target prod" in commands
    assert "analytics_platform.cicd tag" in commands


def test_prod_deploys_the_commit_staging_tested():
    for job_key in ("staging", "prod"):
        for step in job("deploy.yml", job_key)["steps"]:
            assert "ref" not in step.get("with", {}), f"{job_key} checks out a different commit"


def test_closing_a_pr_drops_its_schemas():
    cleanup = workflow("pr-cleanup.yml")
    assert cleanup[True]["pull_request"]["types"] == ["closed"]
    drop = job("pr-cleanup.yml", "drop_pr_schemas")
    assert drop["environment"] == "staging"
    commands = runs(drop)
    assert "analytics_platform.cicd drop-list" in commands
    assert "schemas delete" in commands
    assert "--force" in commands
