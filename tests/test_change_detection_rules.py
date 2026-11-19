"""Tests for the production change detection function, not a duplicate implementation.

Uses the existing tests/conftest.py SparkSession fixture.
"""
import pytest
from src.change_detection import detect_repository_changes

SCHEMA = (
    "id LONG, name STRING, full_name STRING, description STRING, "
    "language STRING, archived BOOLEAN, default_branch STRING, "
    "stargazers_count LONG, forks_count LONG"
)


def repo(
        repo_id, *, 
        description="Same", 
        language="Python", 
        stars=10, 
        forks=2,
        name=None, 
        full_name=None, 
        archived=False, 
        default_branch="main"
    ):
    name = name if name is not None else f"repo-{repo_id}"
    full_name = full_name if full_name is not None else f"org/repo-{repo_id}"
    return (
            repo_id, 
            name, 
            full_name, 
            description, 
            language, 
            archived,
            default_branch, 
            stars, 
            forks
            )


def frame(spark, rows):
    return spark.createDataFrame(rows, SCHEMA)


def statuses(df):
    return {row["id"]: row["change_type"] for row in df.select("id", "change_type").collect()}


def test_initial_snapshot_is_all_new(spark):
    current = frame(spark, [repo(1), repo(2)])
    assert statuses(detect_repository_changes(current, None)) == {1: "NEW", 2: "NEW"}


def test_new_repository(spark):
    old = frame(spark, [repo(1)])
    current = frame(spark, [repo(1), repo(2)])
    assert statuses(detect_repository_changes(current, old)) == {1: "UNCHANGED", 2: "NEW"}


def test_unchanged_repository(spark):
    old = frame(spark, [repo(1)])
    current = frame(spark, [repo(1)])
    assert statuses(detect_repository_changes(current, old)) == {1: "UNCHANGED"}


@pytest.mark.parametrize("field,new_value", [
    ("name", "renamed"),
    ("full_name", "org/renamed"),
    ("description", "Updated description"),
    ("language", "Scala"),
    ("archived", True),
    ("default_branch", "develop"),
    ]
)
def test_tracked_field_change_is_updated(spark, field, new_value):
    old = frame(spark, [repo(1)])
    current = frame(spark, [repo(1, **{field: new_value})])
    assert statuses(detect_repository_changes(current, old)) == {1: "UPDATED"}


def test_equal_null_descriptions_are_unchanged(spark):
    old = frame(spark, [repo(1, description=None)])
    current = frame(spark, [repo(1, description=None)])
    assert statuses(detect_repository_changes(current, old)) == {1: "UNCHANGED"}


def test_null_to_value_is_updated(spark):
    old = frame(spark, [repo(1, description=None)])
    current = frame(spark, [repo(1, description="Now present")])
    assert statuses(detect_repository_changes(current, old)) == {1: "UPDATED"}


def test_stars_and_forks_do_not_trigger_update(spark):
    old = frame(spark, [repo(1, stars=10, forks=2)])
    current = frame(spark, [repo(1, stars=100, forks=20)])
    assert statuses(detect_repository_changes(current, old)) == {1: "UNCHANGED"}


def test_only_new_and_updated_rows_are_selected(spark):
    from pyspark.sql import functions as F
    old = frame(spark, [repo(1), repo(2)])
    current = frame(spark, [repo(1), repo(2, description="changed"), repo(3)])
    changes = detect_repository_changes(current, old)
    changed = changes.filter(F.col("change_type").isin("NEW", "UPDATED"))
    assert statuses(changed) == {2: "UPDATED", 3: "NEW"}
