"""Job task: record Gold's Delta versions before a run, or restore them (ticket 06).

Usage (job tasks):
    python gold_versions.py record  --catalog prod --gold-schema gold --ops-schema ops --run-id 123
    python gold_versions.py restore --catalog prod --gold-schema gold --ops-schema ops --run-id 123
"""

import argparse
import json
import sys

from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp

from analytics_platform.rollback import restore_statements, versions_for_run

VERSIONS_SCHEMA = "run_id string, table_name string, version bigint"


def gold_tables(spark: SparkSession, catalog: str, gold_schema: str) -> list[str]:
    if not spark.catalog.databaseExists(f"{catalog}.{gold_schema}"):
        return []
    rows = spark.sql(f"SHOW TABLES IN {catalog}.{gold_schema}").collect()
    return sorted(f"{catalog}.{gold_schema}.{row.tableName}" for row in rows if not row.isTemporary)


def current_version(spark: SparkSession, table: str) -> int:
    return int(spark.sql(f"DESCRIBE HISTORY {table} LIMIT 1").collect()[0]["version"])


def record(spark: SparkSession, catalog: str, gold_schema: str, ops_schema: str, run_id: str) -> int:
    """Append one row per Gold table to <catalog>.<ops_schema>.gold_versions. Returns how many.
    The job runs this just before dbt, so the rows say "this is Gold as it was before run <run_id>".
    """
    versions_table = f"{catalog}.{ops_schema}.gold_versions"
    spark.sql(
        f"CREATE TABLE IF NOT EXISTS {versions_table} "
        "(run_id STRING, table_name STRING, version BIGINT, recorded_at TIMESTAMP)"
    )
    tables = gold_tables(spark, catalog, gold_schema)
    current_gold_version = {table: current_version(spark, table) for table in tables}
    # empty on first run
    if not current_gold_version:
        return 0
    rows = [(run_id, table, version) for table, version in current_gold_version.items()]
    df = spark.createDataFrame(rows, VERSIONS_SCHEMA)
    df = df.withColumn("recorded_at", current_timestamp())
    df.write.mode("append").saveAsTable(versions_table)
    return len(rows)
    

def restore(spark: SparkSession, catalog: str, ops_schema: str, run_id: str) -> list[str]:
    """RESTORE each Gold table to the version recorded before run_id. Returns the statements it ran."""
    versions_df = spark.table(f"{catalog}.{ops_schema}.gold_versions").collect()
    versions = [row.asDict() for row in versions_df]
    versions_before_run = versions_for_run(versions, run_id)
    statements = restore_statements(versions_before_run)
    if not statements:
        raise ValueError(f"no Gold versions were recorded before run {run_id}")
    for statement in statements:
        spark.sql(statement)
    return statements
    

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["record", "restore"])
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--gold-schema", required=True)
    parser.add_argument("--ops-schema", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)

    spark = SparkSession.builder.getOrCreate()
    if args.command == "record":
        tables = record(spark, args.catalog, args.gold_schema, args.ops_schema, args.run_id)
        print(json.dumps({"event": "gold_versions_recorded", "run_id": args.run_id, "tables": tables}))
    else:
        statements = restore(spark, args.catalog, args.ops_schema, args.run_id)
        print(json.dumps({"event": "gold_restored", "run_id": args.run_id, "statements": statements}))
    return 0


if __name__ == "__main__":
    exit_code = main(sys.argv[1:])
    if exit_code != 0:
        sys.exit(exit_code)
