"""Seam 1: a File Drop in, a Bronze Delta table out, on a local Spark session.

Spark needs Java 17+, so the Spark tests skip when `java` isn't on the PATH. Run them in
WSL (or CI), where it is. The first run downloads the Delta jars, so allow a minute.
"""

import shutil
import uuid
from datetime import date
from pathlib import Path

import pytest

from analytics_platform.bronze import METADATA_COLUMNS, BronzePaths, bronze_paths, ingest
from analytics_platform.customer_drops import write_drop

DAY_1 = date(2017, 1, 1)
DAY_2 = date(2017, 1, 2)
ROW = {"customer_unique_id": "u1", "zip_code_prefix": "1001", "city": "sao paulo", "state": "SP"}
DROP_1 = [
    {**ROW, "updated_at": "2017-01-01"},
    {**ROW, "updated_at": "2017-01-01"},  # a duplicate
    {**ROW, "customer_unique_id": "", "updated_at": "2017-01-01"},  # malformed
]
DROP_2 = [{**ROW, "city": "campinas", "updated_at": "2017-01-02"}]


@pytest.fixture(scope="session")
def spark(tmp_path_factory):
    if shutil.which("java") is None:
        pytest.skip("Spark needs Java 17+; run the Spark tests in WSL or CI")
    from delta import configure_spark_with_delta_pip
    from pyspark.sql import SparkSession

    builder = (
        SparkSession.builder.master("local[1]")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.sql.warehouse.dir", str(tmp_path_factory.mktemp("warehouse")))
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.ui.enabled", "false")
    )
    session = configure_spark_with_delta_pip(builder).getOrCreate()
    yield session
    session.stop()


@pytest.fixture
def paths(tmp_path):
    return BronzePaths(
        source=str(tmp_path / "landing" / "customers"),
        table=f"bronze_customers_{uuid.uuid4().hex[:8]}",
        checkpoint=str(tmp_path / "_checkpoints" / "customers"),
        schema_location=str(tmp_path / "_schemas" / "customers"),
    )


def drop(paths, day, rows):
    write_drop(Path(paths.source).parent, day, rows)


def test_bronze_keeps_every_row_including_duplicates_and_malformed(spark, paths):
    drop(paths, DAY_1, DROP_1)
    ingest(spark, paths, auto_loader=False)
    assert spark.table(paths.table).count() == 3


def test_rows_carry_file_name_ingest_timestamp_and_file_drop_date(spark, paths):
    drop(paths, DAY_1, DROP_1)
    ingest(spark, paths, auto_loader=False)
    row = spark.table(paths.table).first()
    assert set(METADATA_COLUMNS) <= set(spark.table(paths.table).columns)
    assert row["_source_file"].endswith("ingest_date=2017-01-01/customers.csv")
    assert row["_ingested_at"] is not None
    assert row["_file_drop_date"] == DAY_1


def test_rerunning_on_the_same_file_drop_adds_no_rows(spark, paths):
    drop(paths, DAY_1, DROP_1)
    ingest(spark, paths, auto_loader=False)
    ingest(spark, paths, auto_loader=False)
    assert spark.table(paths.table).count() == 3


def test_a_new_file_drop_adds_only_its_own_rows(spark, paths):
    drop(paths, DAY_1, DROP_1)
    ingest(spark, paths, auto_loader=False)
    drop(paths, DAY_2, DROP_2)
    ingest(spark, paths, auto_loader=False)
    days = spark.table(paths.table).groupBy("_file_drop_date").count().collect()
    assert {row["_file_drop_date"]: row["count"] for row in days} == {DAY_1: 3, DAY_2: 1}


def test_bronze_is_partitioned_by_file_drop_date(spark, paths):
    drop(paths, DAY_1, DROP_1)
    ingest(spark, paths, auto_loader=False)
    detail = spark.sql(f"DESCRIBE DETAIL {paths.table}").first()
    assert detail["partitionColumns"] == ["_file_drop_date"]


def test_bronze_paths_read_the_landing_volume_and_write_the_bronze_schema():
    paths = bronze_paths("dev", "dbt_tom_landing", "dbt_tom_bronze")
    assert paths.source == "/Volumes/dev/dbt_tom_landing/files/customers"
    assert paths.table == "dev.dbt_tom_bronze.customers"


def test_checkpoints_are_per_environment_and_outside_the_source_folder():
    dev = bronze_paths("dev", "landing", "bronze")
    staging = bronze_paths("staging", "landing", "bronze")
    assert dev.checkpoint.startswith("/Volumes/dev/")
    assert staging.checkpoint.startswith("/Volumes/staging/")
    assert "customers" in dev.checkpoint
    assert not dev.checkpoint.startswith(dev.source)
    assert not dev.schema_location.startswith(dev.source)
