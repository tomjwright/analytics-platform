"""Seam: record Gold's Delta versions, break Gold, restore it, on a local Spark session.

Skips without Java, like the Bronze tests. Run it in WSL (or CI).
"""

import uuid

import pytest

from analytics_platform.gold_versions import gold_tables, record, restore

CATALOG = "spark_catalog"


@pytest.fixture
def schemas(spark):
    suffix = uuid.uuid4().hex[:8]
    gold, ops = f"gold_{suffix}", f"ops_{suffix}"
    for schema in (gold, ops):
        spark.sql(f"CREATE SCHEMA {CATALOG}.{schema}")
    yield gold, ops
    for schema in (gold, ops):
        spark.sql(f"DROP SCHEMA {CATALOG}.{schema} CASCADE")


def build_dim_customer(spark, gold, cities):
    # Like dbt's table materialisation, every build replaces the table, so each is a new Delta version.
    df = spark.createDataFrame(
        [(f"u{i}", city) for i, city in enumerate(cities)], "customer_unique_id string, city string"
    )
    df.write.format("delta").mode("overwrite").saveAsTable(f"{CATALOG}.{gold}.dim_customer")


def cities(spark, gold):
    return sorted(r.city for r in spark.table(f"{CATALOG}.{gold}.dim_customer").collect())


def test_a_missing_gold_schema_has_no_tables(spark):
    assert gold_tables(spark, CATALOG, "no_such_schema") == []


def test_record_writes_one_row_per_gold_table(spark, schemas):
    gold, ops = schemas
    build_dim_customer(spark, gold, ["salvador"])
    assert record(spark, CATALOG, gold, ops, run_id="111") == 1
    row = spark.table(f"{CATALOG}.{ops}.gold_versions").collect()[0]
    assert (row.run_id, row.table_name, row.version) == ("111", f"{CATALOG}.{gold}.dim_customer", 0)
    assert row.recorded_at is not None


def test_the_first_ever_run_records_nothing_and_does_not_fail(spark, schemas):
    gold, ops = schemas
    assert record(spark, CATALOG, gold, ops, run_id="111") == 0
    assert spark.table(f"{CATALOG}.{ops}.gold_versions").count() == 0


def test_restore_puts_gold_back_to_before_the_bad_run(spark, schemas):
    gold, ops = schemas
    build_dim_customer(spark, gold, ["salvador", "recife"])
    record(spark, CATALOG, gold, ops, run_id="bad_run")  # the job records, then dbt builds...
    build_dim_customer(spark, gold, ["SALVADOR"])  # ...a bad model that drops and corrupts rows

    statements = restore(spark, CATALOG, ops, run_id="bad_run")

    assert statements == [f"RESTORE TABLE {CATALOG}.{gold}.dim_customer TO VERSION AS OF 0"]
    assert cities(spark, gold) == ["recife", "salvador"]


def test_restoring_a_run_with_nothing_recorded_fails_loudly(spark, schemas):
    gold, ops = schemas
    record(spark, CATALOG, gold, ops, run_id="111")
    with pytest.raises(ValueError, match="no Gold versions were recorded before run 999"):
        restore(spark, CATALOG, ops, run_id="999")
