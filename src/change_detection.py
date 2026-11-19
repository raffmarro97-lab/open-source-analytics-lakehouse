"""Repository snapshot change detection shared by Databricks and pytest.

This function reproduces the existing 03_ChangeDetection.ipynb logic.
Only descriptive repository fields are tracked; metrics stay out of SCD2.
"""

from pyspark.sql import functions as F

TRACKED_COLUMNS = (
    "name",
    "full_name",
    "description",
    "language",
    "archived",
    "default_branch",
)


def detect_repository_changes(df_current, df_previous):
    """Return every current repository with NEW, UPDATED or UNCHANGED status.

    df_previous=None represents the first snapshot (all rows NEW).
    Only the caller decides whether to filter and persist NEW/UPDATED rows.
    """
    if df_previous is None:
        return df_current.withColumn("change_type", F.lit("NEW"))

    change_condition = F.lit(False)
    for column in TRACKED_COLUMNS:
        change_condition = change_condition | (
            ~F.col(f"current.{column}").eqNullSafe(
                F.col(f"previous.{column}")
            )
        )

    return (
        df_current.alias("current")
        .join(
            df_previous.alias("previous"),
            F.col("current.id") == F.col("previous.id"),
            "left",
        )
        .select(
            "current.*",
            F.when(F.col("previous.id").isNull(), F.lit("NEW"))
            .when(change_condition, F.lit("UPDATED"))
            .otherwise(F.lit("UNCHANGED"))
            .alias("change_type"),
        )
    )
