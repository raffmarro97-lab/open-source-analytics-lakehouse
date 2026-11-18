#Schema managed by terraform in dev
resource "databricks_schema" "terraform_test" {
  catalog_name = data.databricks_catalog.existing["dev"].name
  name         = "terraform_iac_test"
  comment      = "Test schema managed by Terraform"

  force_destroy = false

  lifecycle {
    prevent_destroy = true
  }
}