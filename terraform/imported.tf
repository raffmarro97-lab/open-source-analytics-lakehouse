resource "databricks_schema" "github_analytics_dev" {

    catalog_name = "opensource_dev"
    name         = "github_analytics"
    force_destroy = false

    properties = {
        collation = "UTF8_BINARY"
        owner     = "root"
    }

    lifecycle {
        prevent_destroy = true
    }

}