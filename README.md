# Open Source Analytics Lakehouse — Databricks

[![Databricks](https://img.shields.io/badge/Databricks-Serverless-orange)](https://www.databricks.com/)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org/)
[![Delta Lake](https://img.shields.io/badge/Delta%20Lake-Delta%20Tables-00ADD8)](https://delta.io/)
[![GitLab](https://img.shields.io/badge/GitLab-Version%20Control-FC6D26)](https://gitlab.com/)

## 🎯 Overview

An end-to-end **Data Engineering** project built with **Databricks, PySpark, Delta Lake and Unity Catalog**, following the **Medallion Architecture (Bronze → Silver → Gold)**.

The pipeline ingests public repository metadata from the [GitHub REST API](https://docs.github.com/en/rest/repos/repos#list-organization-repositories), captures full repository snapshots, detects changes between acquisitions and maintains repository history through a **manually implemented Slowly Changing Dimension Type 2 (SCD2)** using Delta Lake `MERGE`.

Repository activity metrics (**stars and forks**) are stored separately as historical snapshots, so metric fluctuations do not create unnecessary SCD2 versions.

**Current status:** The pipeline has been tested with two real snapshots of the `databricks` GitHub organization. Job orchestration, Terraform provisioning and Jenkins CI/CD are planned enhancements, not yet implemented.

## 📁 Project Structure

```text
open-source-analytics-lakehouse/
├── notebooks/
│   ├── 01_BronzeIngestion.ipynb
│   ├── 02_SilverLightStaging.ipynb
│   ├── 03_ChangeDetection.ipynb
│   ├── 04_SilverCleaning.ipynb
│   └── 05_GoldModeling.ipynb
├── databricks.yml
├── pyproject.toml
├── uv.lock
├── .gitignore
└── README.md
```

## 🏗️ Architecture

```text
GitHub REST API (public organization repositories)
                    |
                    v
01 — Bronze Ingestion
     Full API pagination; append-only snapshots
     snapshot_id + ingestion_ts + raw_json
                    |
           +--------+--------------------+
           |                             |
           v                             v
02 — Silver Light Staging       03 — Change Detection
     Latest snapshot only            Compare last two Bronze snapshots
                                    NEW / UPDATED / UNCHANGED
                                          |
                                          v
                                04 — Silver Cleaning
                                     Data quality checks
                                     Incremental NEW / UPDATED records
                                          |
                                          v
                                05 — Gold Repository Dimension
                                     Manual Delta MERGE / SCD Type 2

Bronze snapshots ----------------> 05 — Gold Repository Metrics
                                     Stars and forks by snapshot
                                     Window + lag() for metric deltas
```

The staging notebook prepares the latest snapshot; the change-detection notebook currently compares the two most recent **Bronze** snapshots directly.

## 📋 Delta Tables — Unity Catalog

All tables use the `github_analytics` schema in the selected catalog (`opensource_dev`, `opensource_staging` or `opensource_prod`). The current tested environment is **DEV**.

| Table (DEV) | Layer | Description |
|---|---|---|
| `opensource_dev.github_analytics.bronze_github_repositories` | Bronze | Append-only GitHub API snapshots, including `raw_json`, `snapshot_id` and `ingestion_ts` |
| `opensource_dev.github_analytics.silver_staging_github_repositories` | Silver | Latest snapshot; overwritten on each staging run |
| `opensource_dev.github_analytics.silver_changes_github_repositories` | Silver | `NEW` and `UPDATED` repositories from change detection |
| `opensource_dev.github_analytics.silver_github_repositories` | Silver | Cleaned, validated incremental changes |
| `opensource_dev.github_analytics.gold_github_repositories` | Gold | Repository dimension with SCD Type 2 history |
| `opensource_dev.github_analytics.gold_github_repository_metrics` | Gold | Historical star and fork counts per repository and snapshot |

## 🔍 Notebook Details

### 01 — Bronze Ingestion

- Calls the GitHub REST API for public repositories belonging to a configurable organization (default: `databricks`).
- Follows GitHub's `Link: rel="next"` pagination until every available page has been retrieved (up to 100 repositories per page).
- Uses a defined PySpark `StructType` rather than schema inference.
- Assigns a unique `snapshot_id` and a shared UTC `ingestion_ts` to each acquisition.
- Preserves the original API response in `raw_json`.
- Writes data to a managed Delta table in **append** mode, retaining earlier snapshots.

**Output:** `bronze_github_repositories`.

### 02 — Silver Light Staging

- Selects the most recent Bronze snapshot for the configured organization, using `ingestion_ts`.
- Retains relevant repository attributes and the original snapshot metadata.
- Excludes `raw_json` from the staging projection.
- Writes the current snapshot using **overwrite** mode.

**Output:** `silver_staging_github_repositories`.

### 03 — Change Detection

- Compares the two most recent Bronze snapshots using the repository `id`.
- Classifies records as `NEW`, `UPDATED` or `UNCHANGED`.
- Uses null-safe comparisons (`eqNullSafe`) on the tracked fields: `name`, `full_name`, `description`, `language`, `archived` and `default_branch`.
- Excludes stars and forks from descriptive SCD2 change detection.
- Writes only `NEW` and `UPDATED` records to the change table.
- Treats every repository as `NEW` when only the initial snapshot is available.

**Output:** `silver_changes_github_repositories`. This is snapshot-difference detection, **not** GitHub-native CDC.

### 04 — Silver Cleaning

- Normalizes selected text attributes with `trim()` while preserving meaningful `NULL` values.
- Validates mandatory fields and checks for duplicate repository IDs within a snapshot.
- Loads new and updated records incrementally with a `left_anti` join on `id` and `snapshot_id`.
- Preserves previously loaded Silver rows when a subsequent snapshot has no descriptive changes.

**Output:** `silver_github_repositories`.

### 05 — Gold Modeling

**Repository dimension — manual SCD Type 2**

- Creates a deterministic `repository_sk` using `SHA256(id + "_" + snapshot_id)`.
- Tracks `valid_from`, `valid_to` and `current` for each descriptive version.
- Compares incoming attributes to the current Gold version using null-safe conditions.
- Stages changed records twice: once with their merge key to close the old version, and once with a `NULL` merge key to insert the new version.
- Applies `whenMatchedUpdate()` and `whenNotMatchedInsert()` in a Delta Lake `MERGE`.
- Verifies mandatory fields, surrogate-key uniqueness, current-version uniqueness and valid temporal intervals.

**Repository metrics — snapshot history**

- Stores `stargazers_count` and `forks_count` from **Bronze**, independently of the SCD2 dimension.
- Uses the logical key `organization`, `id`, `snapshot_id` to avoid repeated inserts in sequential runs.
- Calculates changes between consecutive snapshots with Spark window functions and `lag()`.
- Checks mandatory fields, duplicate keys, negative metric counts and consistency between `snapshot_date` and `ingestion_ts`.

**Outputs:** `gold_github_repositories` and `gold_github_repository_metrics`.

## 🧪 Validation and Observed Results

The initial validation used two real GitHub API snapshots for the `databricks` organization:

| Ingestion date | Repository records |
|---|---:|
| 2026-11-14 | 253 |
| 2026-11-15 | 253 |

Observed results during testing:

- **Bronze:** 506 rows across two distinct snapshots.
- **Change Detection:** all 253 repositories in the second snapshot were `UNCHANGED` for the tracked descriptive fields.
- **Gold SCD2:** 253 current repository versions, with no multiple-current-version anomalies.
- **Example metric change:** `databricks/app-templates` increased from **221 to 222 stars**, while forks remained at **166**.
- **Metric history:** both snapshots are retained independently of descriptive SCD2 changes.

The no-change SCD2 path has been exercised. A real descriptive `UPDATED` event and the handling of repositories absent from a later snapshot remain to be tested/implemented.

## ⚙️ Setup and Execution

### Prerequisites

- Python **3.12** and [`uv`](https://docs.astral.sh/uv/).
- Access to a Databricks workspace with **Serverless compute** and **Unity Catalog**.
- Databricks authentication configured for the local development environment.
- The target catalog and `github_analytics` schema already created in Unity Catalog.

### Local development

Install the dependencies declared in `pyproject.toml`:

```powershell
uv sync
```

The project uses **Databricks Connect** to run PySpark from VS Code against remote Databricks compute. When running locally, initialize the session with:

```python
from databricks.connect import DatabricksSession
spark = DatabricksSession.builder.serverless().getOrCreate()
```

Notebook parameters include `environment` (`dev`, `staging`, `prod`) and `organization` (default: `databricks`). For local execution, the notebooks can read `LAKEHOUSE_ENV` and `GITHUB_ORGANIZATION` environment variables. The matching Unity Catalog catalogs must exist.

### Execution order

```text
01_BronzeIngestion
    → 02_SilverLightStaging
    → 03_ChangeDetection
    → 04_SilverCleaning
    → 05_GoldModeling
```

The current bundle file (`databricks.yml`) configures the **DEV target** for Databricks development and synchronization. It does not yet define an automated multi-task Job.

To validate the configuration:

```powershell
databricks bundle validate -t dev
```

## 🚧 Roadmap

- Test a real descriptive update and validate the full SCD2 version-closing/insertion path.
- Add explicit handling for removed or inaccessible repositories.
- Improve retry, API rate-limit handling, snapshot completeness and concurrent-run idempotency.
- Define Databricks Jobs with Declarative Automation Bundles.
- Add Terraform infrastructure provisioning and Jenkins CI/CD from GitLab.
- Extend end-to-end data quality reporting and analytical outputs.

## 🛠️ Tech Stack

**Databricks**, **PySpark**, **Delta Lake**, **Unity Catalog**, **Databricks Connect**, **Python**, **requests**, **GitHub REST API**, **uv** and **GitLab**.

## 👨‍💻 Author

**Raffaele Marro**  
Data Engineer | Databricks  
[LinkedIn](https://www.linkedin.com/in/raffaele-marro-6b1681282/)
