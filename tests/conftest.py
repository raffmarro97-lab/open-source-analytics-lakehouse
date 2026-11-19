import pytest
from pyspark.sql import SparkSession

@pytest.fixture(scope = "session")
def spark():
    spark = (
        SparkSession.builder
        .master("local[2]")
        .appName("github-analytics-unit-tests")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    yield spark

    spark.stop()