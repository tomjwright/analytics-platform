"""Ticket 06's offline checks: staging gates prod, the rollback workflow, and the Gold version tasks.

They read the workflow, bundle and docs files, so they run anywhere without credentials.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def workflow(name):
    return yaml.safe_load((WORKFLOWS / name).read_text())


def runs(job_def):
    return "\n".join(step.get("run", "") for step in job_def["steps"])


def bundle_job(name):
    for path in sorted((ROOT / "resources").glob("*.yml")):
        jobs = (yaml.safe_load(path.read_text()).get("resources") or {}).get("jobs") or {}
        if name in jobs:
            return jobs[name]
    raise AssertionError(f"no bundle job called {name}")


def task(job_def, key):
    return next(t for t in job_def["tasks"] if t["task_key"] == key)


# A failing staging run blocks prod


def test_a_failing_staging_step_fails_the_staging_job():
    staging = workflow("deploy.yml")["jobs"]["staging"]
    assert "continue-on-error" not in staging
    assert all("continue-on-error" not in step for step in staging["steps"])


def test_prod_only_runs_after_staging_succeeds():
    prod = workflow("deploy.yml")["jobs"]["prod"]
    assert prod["needs"] == "staging"
    # `if: always()` or `failure()` would let prod run after staging failed.
    assert "if" not in prod


# The rollback workflow


def test_rollback_is_started_by_hand_with_a_tag():
    inputs = workflow("rollback.yml")[True]["workflow_dispatch"]["inputs"]
    assert inputs["tag"]["required"] is True
    assert inputs["restore_run_id"]["required"] is False


def test_rollback_waits_for_the_prod_approval_and_never_overlaps_a_deploy():
    rollback = workflow("rollback.yml")
    assert rollback["jobs"]["rollback"]["environment"] == "prod"
    assert rollback["concurrency"]["group"] == workflow("deploy.yml")["concurrency"]["group"]
    assert rollback["concurrency"]["cancel-in-progress"] is False


def test_rollback_has_read_only_repo_access():
    rollback = workflow("rollback.yml")
    assert rollback["permissions"] == {"contents": "read"}
    assert "permissions" not in rollback["jobs"]["rollback"]


def test_rollback_checks_the_tag_before_checking_it_out():
    steps = workflow("rollback.yml")["jobs"]["rollback"]["steps"]
    check = next(i for i, s in enumerate(steps) if "cicd check-tag" in s.get("run", ""))
    checkout = next(i for i, s in enumerate(steps) if s.get("with", {}).get("ref") == "${{ inputs.tag }}")
    deploy = next(i for i, s in enumerate(steps) if "bundle deploy --target prod" in s.get("run", ""))
    assert check < checkout < deploy


def test_rollback_never_pastes_inputs_into_a_shell_command():
    # ${{ inputs.x }} inside run: is a script injection. Pass inputs through env: instead.
    assert "${{ inputs" not in runs(workflow("rollback.yml")["jobs"]["rollback"])


def test_rollback_restores_gold_only_when_given_a_run_id():
    steps = workflow("rollback.yml")["jobs"]["rollback"]["steps"]
    restore = next(s for s in steps if "bundle run restore_gold --target prod" in s.get("run", ""))
    assert restore["if"] == "inputs.restore_run_id != ''"
    assert "$RESTORE_RUN_ID" in restore["run"]


# Gold versions in ops


def test_gold_versions_are_recorded_after_bronze_and_before_dbt():
    tracer = bundle_job("customer_tracer")
    record = task(tracer, "record_gold_versions")
    assert record["depends_on"] == [{"task_key": "bronze_customers"}]
    assert task(tracer, "dbt")["depends_on"] == [{"task_key": "record_gold_versions"}]
    params = record["spark_python_task"]["parameters"]
    assert record["spark_python_task"]["python_file"] == "../src/analytics_platform/gold_versions.py"
    assert params[0] == "record"
    assert params[params.index("--run-id") + 1] == "{{job.run_id}}"
    assert params[params.index("--ops-schema") + 1] == "${resources.schemas.ops.name}"
    assert params[params.index("--gold-schema") + 1] == "${var.gold_schema}"


def test_restore_gold_is_a_job_that_takes_the_run_to_restore():
    restore = bundle_job("restore_gold")
    assert [p["name"] for p in restore["parameters"]] == ["run_id"]
    params = task(restore, "restore_gold")["spark_python_task"]["parameters"]
    assert params[0] == "restore"
    assert params[params.index("--run-id") + 1] == "{{job.parameters.run_id}}"


def test_dev_points_gold_schema_at_its_own_gold():
    bundle = yaml.safe_load((ROOT / "databricks.yml").read_text())
    assert bundle["variables"]["gold_schema"]["default"] == "gold"
    assert bundle["targets"]["dev"]["variables"]["gold_schema"] == "dbt_${workspace.current_user.short_name}_gold"


# The drill


def test_the_drill_postmortem_is_written():
    text = (ROOT / "docs" / "postmortems" / "rollback-drill.md").read_text()
    for heading in ("## Summary", "## Timeline", "## Impact", "## Root cause", "## Recovery", "## Actions"):
        assert heading in text, heading
    assert "TODO" not in text
