"""Ticket 02's definition of done for everything that can be checked offline.

The live parts (a real deploy, the approval and the permission error) are
proved in the PR itself.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def bundle():
    return yaml.safe_load((ROOT / "databricks.yml").read_text())


def deploy_workflow():
    return yaml.safe_load((ROOT / ".github" / "workflows" / "deploy.yml").read_text())


def hello_job():
    return yaml.safe_load((ROOT / "resources" / "hello_job.yml").read_text())["resources"]["jobs"]["hello"]


def test_every_environment_has_a_target_with_its_own_catalog():
    targets = bundle()["targets"]
    for name in ("dev", "staging", "prod"):
        assert targets[name]["variables"]["catalog"] == name


def test_staging_and_prod_deploy_in_production_mode_as_a_service_principal():
    targets = bundle()["targets"]
    for name in ("staging", "prod"):
        assert targets[name]["mode"] == "production"
        assert "service_principal_name" in targets[name]["run_as"]
        assert "/Users/" not in targets[name]["workspace"]["root_path"]


def test_staging_and_prod_run_as_different_principals():
    targets = bundle()["targets"]
    assert targets["staging"]["run_as"] != targets["prod"]["run_as"]


def test_hello_job_runs_the_hello_task_serverless_with_the_target_catalog():
    job = hello_job()
    (task,) = job["tasks"]
    assert task["spark_python_task"]["python_file"].endswith("hello.py")
    assert "${var.catalog}" in task["spark_python_task"]["parameters"]
    assert "environment_key" in task
    assert "new_cluster" not in task
    assert "job_cluster_key" not in task


def test_deploy_runs_on_merge_to_main():
    assert deploy_workflow()[True]["push"]["branches"] == ["main"]


def test_prod_waits_for_staging_and_uses_the_prod_environment():
    jobs = deploy_workflow()["jobs"]
    assert jobs["staging"]["environment"] == "staging"
    assert jobs["prod"]["environment"] == "prod"
    assert "staging" in jobs["prod"]["needs"]


def test_deploys_use_oauth_client_credentials_not_a_token():
    text = (ROOT / ".github" / "workflows" / "deploy.yml").read_text()
    assert "secrets.DATABRICKS_CLIENT_ID" in text
    assert "secrets.DATABRICKS_CLIENT_SECRET" in text
    assert "DATABRICKS_TOKEN" not in text


def test_each_target_is_validated_deployed_and_run():
    text = (ROOT / ".github" / "workflows" / "deploy.yml").read_text()
    for target in ("staging", "prod"):
        for command in ("validate", "deploy", "run customer_tracer"):
            assert f"bundle {command} --target {target}" in text, (command, target)


def test_bootstrap_doc_has_no_todos_left():
    doc = (ROOT / "docs" / "bootstrap.md").read_text()
    assert "TODO" not in doc
