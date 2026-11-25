# One Free Edition workspace, one catalog per environment

The platform runs on Databricks Free Edition so it costs nothing, and Free Edition allows one workspace and one metastore per account. Dev, staging and prod are therefore three Unity Catalog catalogs in the same workspace instead of three workspaces, as an enterprise would usually run them. Isolation comes from grants: each of staging and prod has its own deploy service principal that can write only to its own catalog, and dev gives each developer their own schemas.
