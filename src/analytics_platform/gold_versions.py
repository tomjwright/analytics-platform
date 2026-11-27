"""Job task: record Gold's Delta versions before a run, or restore them (ticket 06).

Usage (job tasks):
    python gold_versions.py record  --catalog prod --gold-schema gold --ops-schema ops --run-id 123
    python gold_versions.py restore --catalog prod --gold-schema gold --ops-schema ops --run-id 123
"""

import argparse
import json
import sys

from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp  # noqa: F401  TODO(ticket 06): drop the noqa once record uses it

from analytics_platform.rollback import restore_statements, versions_for_run  # noqa: F401  TODO(ticket 06): ditto, in restore

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

    TODO(ticket 06):
    - CREATE TABLE IF NOT EXISTS the versions table: run_id STRING, table_name STRING, version BIGINT,
      recorded_at TIMESTAMP.
    - One (run_id, table, version) tuple per table from gold_tables(...), using current_version(...).
    - If there are any: spark.createDataFrame(rows, VERSIONS_SCHEMA), add recorded_at with
      current_timestamp(), and append it with .write.mode("append").saveAsTable(...).
    - The very first run has no Gold yet: record nothing and don't fail. Why might Delta's own
      DESCRIBE HISTORY not be enough on its own, without this table? (Hint: which run made which version?)
    """
    raise NotImplementedError


def restore(spark: SparkSession, catalog: str, ops_schema: str, run_id: str) -> list[str]:
    """RESTORE each Gold table to the version recorded before run_id. Returns the statements it ran.

    TODO(ticket 06):
    - Read the versions table, turn each Row into a dict (row.asDict()).
    - versions_for_run(...) then restore_statements(...), from rollback.py.
    - No statements means a wrong run id: raise ValueError("no Gold versions were recorded before run <id>").
      A silent no-op here would let you think you'd recovered when you hadn't.
    - Run each statement with spark.sql.
    """
    raise NotImplementedError


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
