"""Bronze ingest for Customer File Drops (ADR 0003).

Loads every new CSV under the landing volume's `customers/` folder into one Bronze
Delta table, using Auto Loader on Databricks and Spark's plain file stream in local
tests. Bronze keeps every row exactly as it arrived (duplicates and malformed rows
too) plus three ingest metadata columns; cleaning is Silver's job.

Usage (job task): python bronze.py --catalog dev --landing-schema landing --bronze-schema bronze
"""

import argparse
import json
import sys
from dataclasses import dataclass

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.types import StringType, StructField, StructType

# The File Drop's columns, all read as strings. Question for the interview log:
# why should Bronze never cast types?
CUSTOMER_SCHEMA = StructType(
    [
        StructField("customer_unique_id", StringType()),
        StructField("zip_code_prefix", StringType()),
        StructField("city", StringType()),
        StructField("state", StringType()),
        StructField("updated_at", StringType()),
    ]
)
METADATA_COLUMNS = ["_source_file", "_ingested_at", "_file_drop_date"]


@dataclass(frozen=True)
class BronzePaths:
    source: str  # the folder Auto Loader watches
    table: str  # catalog.schema.table
    checkpoint: str  # where the stream records which files it has loaded
    schema_location: str  # where Auto Loader records the schema it inferred


def bronze_paths(catalog: str, landing_schema: str, bronze_schema: str) -> BronzePaths:
    # TODO(ticket 04): build the four locations for the customers stream.
    # - The generator writes to /Volumes/<catalog>/<landing_schema>/files/customers/...
    # - The table lives in the Bronze schema of the same catalog.
    # - Checkpoint and schema location: one per table, per environment, and never inside
    #   the source folder (what would Auto Loader do with its own checkpoint files?).
    raise NotImplementedError


def read_drops(spark: SparkSession, source: str, schema_location: str, auto_loader: bool) -> DataFrame:
    # TODO(ticket 04): return a streaming DataFrame over the CSVs under source.
    # - Both paths: spark.readStream, with the CSV header option.
    # - auto_loader=True: format "cloudFiles", plus cloudFiles.format and cloudFiles.schemaLocation.
    #   Auto Loader reads CSV columns as strings unless you ask it to infer types.
    # - auto_loader=False (local tests): format "csv" with .schema(CUSTOMER_SCHEMA), because a
    #   plain file stream can't infer a schema.
    raise NotImplementedError


def with_ingest_metadata(df: DataFrame) -> DataFrame:
    # TODO(ticket 04): add the METADATA_COLUMNS.
    # - Every file-based DataFrame has a hidden `_metadata` struct; `_metadata.file_path` is the file's path.
    # - _ingested_at: when this load ran. _file_drop_date: the date in `ingest_date=YYYY-MM-DD`, as a date.
    raise NotImplementedError


def ingest(spark: SparkSession, paths: BronzePaths, auto_loader: bool = True) -> None:
    # TODO(ticket 04): stream read_drops -> with_ingest_metadata into paths.table, then wait for it.
    # - writeStream with a checkpointLocation, partitioned by _file_drop_date.
    # - trigger(availableNow=True): load every file not yet in the checkpoint, then stop.
    # - .toTable(...) starts the query; .awaitTermination() blocks until it finishes.
    raise NotImplementedError


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--landing-schema", required=True)
    parser.add_argument("--bronze-schema", required=True)
    args = parser.parse_args(argv)

    paths = bronze_paths(args.catalog, args.landing_schema, args.bronze_schema)
    spark = SparkSession.builder.getOrCreate()
    ingest(spark, paths)
    log = {"event": "bronze_ingest", "table": paths.table, "rows": spark.table(paths.table).count()}
    print(json.dumps(log))
    return 0


if __name__ == "__main__":
    exit_code = main(sys.argv[1:])
    if exit_code != 0:
        sys.exit(exit_code)
