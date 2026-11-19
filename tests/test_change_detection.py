from pyspark.sql import functions as F

def test_null_safe_change_detection(spark):

    old_df = spark.createDataFrame(
        [
            (1, None),
            (2, "Old description"),
            (3, "Same description")
        ],
        "id LONG, description STRING"
    )

    new_df = spark.createDataFrame(
        [
            (1, None),
            (2, "New description"),
            (3, "Same description")
        ],
        "id LONG, description STRING"
    )

    changes_df = (
        old_df.alias("old")
        .join(new_df.alias("new"), on = "id")
        .filter(
            ~F.col("old.description").eqNullSafe(
                F.col("new.description")
            )
        )
        .select("id")
    )

    changes_ids = sorted(row.id for row in changes_df.collect())

    assert changes_ids == [2]