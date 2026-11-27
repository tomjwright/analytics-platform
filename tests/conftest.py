"""Shared fixtures. Spark needs Java 17+, so the Spark tests skip when `java` isn't on the PATH."""

import shutil

import pytest


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
