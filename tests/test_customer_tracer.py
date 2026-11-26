"""Ticket 04's offline checks: the tracer job's shape, and where dbt builds each model.

`dbt parse` resolves every model's schema through generate_schema_name without a
warehouse connection, so these run anywhere, CI included.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
DBT = ROOT / "dbt"


def tracer_job():
    resources = yaml.safe_load((ROOT / "resources" / "customer_tracer_job.yml").read_text())["resources"]
    return {task["task_key"]: task for task in resources["jobs"]["customer_tracer"]["tasks"]}


def manifest(target, dev_user="tom"):
    subprocess.run(
        ["dbt", "parse", "--target", target, "--vars", f"{{dev_user: {dev_user}}}", "--quiet"],
        cwd=DBT,
        check=True,
        env={**os.environ, "DBT_PROFILES_DIR": str(DBT)},
    )
    return json.loads((DBT / "target" / "manifest.json").read_text())


def schema_of(manifest_json, model):
    return manifest_json["nodes"][f"model.analytics_platform.{model}"]["schema"]


def test_tasks_run_generate_then_bronze_then_dbt():
    tasks = tracer_job()
    assert tasks["bronze_customers"]["depends_on"] == [{"task_key": "generate_customer_drop"}]
    assert tasks["dbt"]["depends_on"] == [{"task_key": "bronze_customers"}]


def test_dbt_task_builds_the_project_for_the_deployed_target():
    dbt_task = tracer_job()["dbt"]["dbt_task"]
    assert dbt_task["project_directory"] == "../dbt"
    assert dbt_task["warehouse_id"] == "${var.warehouse_id}"
    build = [command for command in dbt_task["commands"] if command.startswith("dbt build")]
    assert len(build) == 1
    assert "--target ${bundle.target}" in build[0]


@pytest.mark.parametrize(("model", "layer"), [("stg_customers", "silver"), ("dim_customer", "gold")])
def test_dev_builds_in_your_own_schemas(model, layer):
    assert schema_of(manifest("dev"), model) == f"dbt_tom_{layer}"


@pytest.mark.parametrize("target", ["staging", "prod"])
def test_staging_and_prod_build_in_the_shared_layer_schemas(target):
    built = manifest(target)
    assert schema_of(built, "stg_customers") == "silver"
    assert schema_of(built, "dim_customer") == "gold"


def test_dbt_reads_the_bronze_table_the_job_writes():
    source = manifest("dev")["sources"]["source.analytics_platform.bronze.customers"]
    assert (source["database"], source["schema"], source["name"]) == ("dev", "dbt_tom_bronze", "customers")
