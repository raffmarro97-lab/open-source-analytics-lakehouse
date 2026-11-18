output "catalogs" {
  description = "Existing Unity Catalog catalogs"

  value = {
    for env, catalog in data.databricks_catalog.existing :
    env => catalog.name
  }
}

output "schemas" {
  description = "Existing Unity Catalog schemas"

  value = {
    for env, schema in data.databricks_schema.existing :
    env => schema.name
  }
}