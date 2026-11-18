# Open Source Analytics Lakehouse — Databricks

[![Databricks](https://img.shields.io/badge/Databricks-Serverless-orange)](https://www.databricks.com/)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org/)
[![Delta Lake](https://img.shields.io/badge/Delta%20Lake-Delta%20Tables-00ADD8)](https://delta.io/)
[![GitLab](https://img.shields.io/badge/GitLab-Version%20Control-FC6D26)](https://gitlab.com/)

## 🎯 Overview

An end-to-end **Data Engineering** project built with **Databricks, PySpark, Delta Lake and Unity Catalog**, following the **Medallion Architecture (Bronze → Silver → Gold)**.

The pipeline ingests public repository metadata from the [GitHub REST API](https://docs.github.com/en/rest/repos/repos#list-organization-repositories), captures append-only snapshots, detects descriptive changes between acquisitions and maintains repository history through a **manually implemented Slowly Changing Dimension Type 2 (SCD2)** using Delta Lake `MERGE`.

Repository metrics (**stars and forks**) are historized independently of descriptive attributes, so changes in metric counts do not create unnecessary SCD2 dimension versions.

The pipeline is **orchestrated as a five-task Databricks Job** and deployed using **Databricks Declarative Automation Bundles (DABs)**. Separate **DEV, STAGING and PROD** targets use distinct Unity Catalog catalogs and workspace deployment paths.

**Project status — 18 November 2026:** DEV end-to-end execution and snapshot consistency checks passed; STAGING was initialized and validated; the PROD bundle target and Job were deployed. A controlled synthetic `UPDATED` scenario confirmed SCD2 version closing and insertion, and a repeated-input comparison detected no further changes. **GitLab CI/CD is planned but not yet implemented.** The initial PROD data run has not been documented in these results.

## 📁 Project Structure

```text
open-source-analytics-lakehouse/
├── notebooks/
│   ├── 01_BronzeIngestion.ipynb
│   ├── 02_SilverLightStaging.ipynb
│   ├── 03_ChangeDetection.ipynb
│   ├── 04_SilverCleaning.ipynb
│   └── 05_GoldModeling.ipynb
├── resources/
│   └── github_analytics.job.yml
├── databricks.yml
├── pyproject.toml
├── uv.lock
├── .gitignore
└── README.md
```

The bundle includes `resources/*.yml`, where `github_analytics.job.yml` defines the multi-task Job. The SCD2 simulation was executed in a separate Databricks test notebook, not as an additional production pipeline task.

## 🏗️ Architecture

```text
GitHub REST API — public organization repositories
                       |
                       v
             01 — Bronze Ingestion
             API pagination; append-only Delta snapshots
             snapshot_id + ingestion_ts + raw_json
                       |
             +---------+--------------------------+
             |                                    |
             v                                    v
  02 — Silver Light Staging           03 — Change Detection
  Latest snapshot only                 Compare latest two Bronze snapshots
  Overwrite on each run                NEW / UPDATED / UNCHANGED
                                                 |
                                                 v
                                     04 — Silver Cleaning
                                     Validations + incremental loading
                                                 |
                                                 v
                                     05 — Gold Repository Dimension
                                     Manual SCD Type 2 Delta MERGE

  Bronze snapshots -----------------> 05 — Gold Repository Metrics
                                      Stars / forks by snapshot
                                      Window + lag() for trend analysis
```

**Execution order:** `bronze_ingestion` → `silver_staging` → `change_detection` → `silver_cleaning` → `gold_modeling`.

> **Implementation detail:** The Job runs sequentially, but `03_ChangeDetection` compares the latest two **Bronze** snapshots directly; it does not read Silver Staging. Gold Metrics also reads Bronze directly.
>
> This is **snapshot-difference detection**, not GitHub-native change-data capture (CDC). The current implementation detects `NEW` and `UPDATED` repositories; it does not yet process repositories missing from a later snapshot as `DELETED`.

## 📋 Delta Tables — Unity Catalog

Each environment uses the same schema, `github_analytics`, in a separate catalog.

| Environment | Unity Catalog catalog | Role |
|---|---|---|
| DEV | `opensource_dev` | Development and functional testing |
| STAGING | `opensource_staging` | Pre-production validation |
| PROD | `opensource_prod` | Production target |

The following six tables are created under `<catalog>.github_analytics`:

| Table | Layer | Purpose |
|---|---|---|
| `bronze_github_repositories` | Bronze | Append-only API snapshots with raw JSON and ingestion metadata |
| `silver_staging_github_repositories` | Silver | Most recent snapshot; overwritten each run |
| `silver_changes_github_repositories` | Silver | Latest detected `NEW` / `UPDATED` records |
| `silver_github_repositories` | Silver | Cleaned and validated incremental records |
| `gold_github_repositories` | Gold | SCD2 repository dimension and version history |
| `gold_github_repository_metrics` | Gold | Stars and forks for each repository and snapshot |

The environments currently share **one Databricks workspace**, with logical separation through catalogs, bundle paths and Jobs; they are not isolated by separate workspaces.

## 🔍 Notebook Details

### 01 — Bronze Ingestion

- Retrieves public repositories for a configurable GitHub organization (default: `databricks`).
- Follows the API `Link: rel="next"` pagination, requesting up to 100 repositories per page.
- Uses an explicit PySpark `StructType` schema.
- Assigns a unique `snapshot_id` and UTC `ingestion_ts` to each acquisition.
- Preserves source responses in `raw_json`.
- Appends each snapshot to a managed Delta table.

**Output:** `bronze_github_repositories`.

### 02 — Silver Light Staging

- Selects the most recent Bronze snapshot for the requested organization.
- Projects relevant repository attributes and ingestion metadata, excluding `raw_json`.
- Overwrites the staging table with the current snapshot.

**Output:** `silver_staging_github_repositories`.

### 03 — Change Detection

- Compares the latest two Bronze snapshots by repository `id`.
- Uses null-safe comparison (`eqNullSafe`) for `name`, `full_name`, `description`, `language`, `archived` and `default_branch`.
- Classifies records as `NEW`, `UPDATED` or `UNCHANGED`, writing only `NEW` and `UPDATED`.
- Treats the first available snapshot as an initial load of `NEW` records.
- Excludes stars and forks from descriptive change detection.

**Output:** `silver_changes_github_repositories`.

### 04 — Silver Cleaning

- Normalizes selected text fields while preserving meaningful `NULL` values.
- Checks mandatory attributes and duplicate IDs within a snapshot.
- Loads new and updated rows incrementally, avoiding repeated `(id, snapshot_id)` combinations.
- Retains prior Silver records when no descriptive changes are detected.

**Output:** `silver_github_repositories`.

### 05 — Gold Modeling

**Repository dimension — manual SCD Type 2**

- Generates deterministic `repository_sk` values using `SHA256(id + "_" + snapshot_id)`.
- Tracks `valid_from`, `valid_to` and `current` for each version.
- Compares source attributes against the current Gold version using null-safe comparisons.
- Uses an SCD2 staging pattern: `merge_id = id` to match/close the previous version and `merge_id = NULL` to insert the new version.
- Applies `whenMatchedUpdate()` and `whenNotMatchedInsert()` with Delta Lake `MERGE` using **`target.id = source.merge_id`**.
- Checks required fields, duplicate surrogate keys, multiple active versions and invalid temporal intervals.

**Repository metrics — snapshot history**

- Stores `stargazers_count` and `forks_count` for each Bronze snapshot.
- Uses `(organization, id, snapshot_id)` to exclude already-loaded observations.
- Computes sequential star/fork changes through Spark windows and `lag()`.
- Checks for missing keys, duplicates, negative metrics and timestamp/date inconsistencies.

**Outputs:** `gold_github_repositories`, `gold_github_repository_metrics`.

## 🔁 Orchestration with Databricks Asset Bundles

`databricks.yml` includes the resources defined in `resources/*.yml` and configures the three deployment targets.

`resources/github_analytics.job.yml` defines the `github_analytics_pipeline` Job, with:

- Five sequential notebook tasks and explicit `depends_on` relationships.
- Job-level parameters: `environment` (defaults to `${bundle.target}`) and `organization` (defaults to `databricks`).
- `max_concurrent_runs: 1` to prevent overlapping Job runs.
- Serverless notebook execution in the tested workspace.

| Target | Deployment location (within workspace) | Catalog |
|---|---|---|
| `dev` | `ProjectOpenSourceAnalytics/dev` | `opensource_dev` |
| `staging` | `ProjectOpenSourceAnalytics/staging` | `opensource_staging` |
| `prod` | `ProjectOpenSourceAnalytics/prod` | `opensource_prod` |

DEV uses bundle development mode. PROD is configured with production mode and explicit run identity/permissions. Deployment targets separate code locations and Jobs; the notebooks select their data catalog based on the `environment` parameter.

### Prerequisites

- Python **3.12** and [`uv`](https://docs.astral.sh/uv/).
- A Databricks workspace with Serverless compute and Unity Catalog access.
- Databricks CLI and local authentication (optionally through a named CLI profile).
- Existing environment catalogs and a `github_analytics` schema in each target catalog.
- Permissions to deploy Jobs and write to each catalog.

### Local development with Databricks Connect

Install dependencies from `pyproject.toml`:

```powershell
uv sync
```

When running PySpark locally from VS Code, initialize a remote Spark session:

```python
from databricks.connect import DatabricksSession
spark = DatabricksSession.builder.serverless().getOrCreate()
```

Notebook parameters can be supplied as Job parameters in Databricks or as environment variables for local execution:

- `environment`: `dev`, `staging`, `prod` — locally via `LAKEHOUSE_ENV`.
- `organization`: default `databricks` — locally via `GITHUB_ORGANIZATION`.

### Manual bundle workflow

Validate, deploy and run the desired target:

```powershell
# DEV
databricks bundle validate -t dev
databricks bundle deploy -t dev
databricks bundle run github_analytics_pipeline -t dev

# STAGING
databricks bundle validate -t staging
databricks bundle deploy -t staging
databricks bundle run github_analytics_pipeline -t staging

# PROD — execute intentionally after verification
databricks bundle validate -t prod
databricks bundle deploy -t prod
databricks bundle run github_analytics_pipeline -t prod
```

If using a named Databricks CLI profile, append `--profile YOUR_PROFILE` to these commands.

> Each new **full ingestion run** deliberately appends another Bronze snapshot and another set of Gold Metrics observations. Idempotency checks concern the absence of duplicate SCD2 versions and duplicate metric rows **for the same snapshot**, not an expectation that successive acquisitions leave Bronze unchanged.

## 🧪 Validation and Observed Results

### DEV — end-to-end validation

The pipeline was run against the public `databricks` organization. Four successive acquisitions returned **253 repository records each**.

| Table | Observed rows after four acquisitions |
|---|---:|
| Bronze | 1,012 |
| Silver Staging | 253 |
| Silver Changes (latest comparison) | 0 |
| Silver Clean | 253 |
| Gold Repositories | 253 |
| Gold Repository Metrics | 1,012 |

Additional checks passed:

- **Four of four snapshots:** 253 Bronze records, 253 unique repository IDs and 253 corresponding Gold Metrics records per snapshot (`OK`).
- **SCD2 current-version integrity:** 253 distinct repository IDs, 253 active versions and no historical versions in the unchanged-data test.
- **Active-version uniqueness:** no repository had multiple `current = true` versions.
- **Temporal validity:** no invalid `valid_from` / `valid_to` / `current` combinations were found.
- **Incremental repeat execution:** the fourth API acquisition added 253 Bronze and Gold Metrics rows, while descriptive Gold dimensions remained at 253 versions.

An earlier pair of real snapshots also showed an example of **metric changes without SCD2 changes**: `databricks/app-templates` increased from 221 to 222 stars, while its fork count remained at 166.

### Controlled CDC / SCD2 test

A separate development test used `databricks/databricks-grafana-datasource` and changed its description by appending `[SCD2 TEST]` in a **separate test Delta table**, leaving the original Gold table untouched.

1. The synthetic comparison classified the modified repository as `UPDATED`.
2. The corrected `MERGE` closed the original version and inserted a new active version (two total versions: one historical, one current).
3. Re-comparing the **same original incoming update** to the new active version returned `Changes detected: 0`.

This validates the controlled update path. A descriptive update through the **entire live API → Bronze → Gold workflow** is still a separate end-to-end test to complete.

### STAGING and PROD

- **STAGING:** bundle validation, deployment and first Job run completed. The six tables were initialized with 253 rows each on the first acquisition, including 253 initial `NEW` changes.
- **PROD:** the bundle target, deployment directory and Job were configured and verified. A completed first PROD data run and its record counts are **not yet documented here**.

## 🚧 Roadmap

- [x] Build Bronze, Silver and Gold Delta pipelines.
- [x] Implement snapshot-based change detection and manual Delta Lake SCD2 logic.
- [x] Orchestrate the five notebooks with Databricks Asset Bundles and Jobs.
- [x] Configure DEV, STAGING and PROD deployment targets.
- [x] Validate snapshot consistency and test a controlled SCD2 `UPDATED` case.
- [ ] Validate the first PROD data run and record counts.
- [ ] Implement **GitLab CI/CD** for automated validation, deployment and controlled promotion across targets.
- [ ] Test a descriptive update end-to-end using the full pipeline.
- [ ] Handle repositories removed from, or inaccessible in, subsequent API snapshots.
- [ ] Improve API rate-limit handling, retries, snapshot completeness checks and recovery/idempotency safeguards.
- [ ] Expand automated data quality tests and analytical outputs.
- [ ] Explore Terraform for infrastructure provisioning.

## 🛠️ Tech Stack

**Databricks**, **Databricks Jobs**, **Declarative Automation Bundles**, **Serverless**, **PySpark**, **Delta Lake**, **Unity Catalog**, **Databricks Connect**, **Python**, **requests**, **GitHub REST API**, **uv** and **GitLab**.

## 👨‍💻 Author

**Raffaele Marro**  
Data Engineer | Databricks  
[LinkedIn](https://www.linkedin.com/in/raffaele-marro-6b1681282/)
