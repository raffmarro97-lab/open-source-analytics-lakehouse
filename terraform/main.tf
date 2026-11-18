locals {
  catalogs = {
    dev     = "opensource_dev"
    staging = "opensource_staging"
    prod    = "opensource_prod"
  }
}

data "databricks_catalog" "existing" {
  for_each = local.catalogs

  name = each.value
}

data "databricks_schema" "existing" {
  for_each = local.catalogs

  name = "${each.value}.github_analytics"
}