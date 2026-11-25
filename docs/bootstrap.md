# Bootstrap

Every manual, one-time step needed to recreate this platform from nothing.
Everything else is in the bundle or a workflow. If you click something in a UI
and it is not on this page, add it.

## Databricks

1. Sign up for Databricks Free Edition. Note the workspace URL
   (`https://<id>.cloud.databricks.com`, everything up to `.com`). This is `DATABRICKS_HOST`.
2. Create the catalogs: Catalog -> **+** -> Create catalog, once each for `dev`, `staging` and `prod`
   (ADR 0001: one workspace, one catalog per environment).
3. Create the deploy service principals: Settings -> Identity and access -> Service principals -> Add.

   | Name | Application ID | Deploys to |
   |---|---|---|
   | `sp-staging-deploy` | `acb14c44-9506-4f19-9375-e0b223869d04` | `staging` |
   | `sp-prod-deploy` | `a8ff1413-0ca6-426d-a62f-8c264d455332` | `prod` |

   Application IDs are identifiers, not secrets. `databricks.yml` uses them in `run_as`.
4. On each principal's **Configurations** tab, tick **Workspace access** and **Databricks SQL access**.
   Leave its Permissions tab alone: those control who can manage the principal, not what it can do.
5. On each principal's **Secrets** tab, click **Generate secret** with a 90-day lifetime. Copy the
   client ID and secret straight into GitHub (below). The secret is shown only once.

   | Principal | Secret expires |
   |---|---|
   | `sp-staging-deploy` | 2027-02-23 |
   | `sp-prod-deploy` | 2027-02-23 |

6. Grant each principal write access to its own catalog only. Run in SQL Editor as the workspace admin:

   ```sql
   GRANT USE CATALOG, USE SCHEMA, CREATE SCHEMA, CREATE TABLE, CREATE VOLUME,
         SELECT, MODIFY, READ VOLUME, WRITE VOLUME
   ON CATALOG staging TO `acb14c44-9506-4f19-9375-e0b223869d04`;

   GRANT USE CATALOG, USE SCHEMA, CREATE SCHEMA, CREATE TABLE, CREATE VOLUME,
         SELECT, MODIFY, READ VOLUME, WRITE VOLUME
   ON CATALOG prod TO `a8ff1413-0ca6-426d-a62f-8c264d455332`;
   ```

   Check with `SHOW GRANTS ON CATALOG staging;` and `SHOW GRANTS ON CATALOG prod;`. Each principal
   appears on its own catalog only. `ALL PRIVILEGES` is avoided because it includes `MANAGE`,
   which would let a principal grant access to others.

## GitHub

1. Settings -> Environments -> New environment: `staging`, then `prod`.
2. In each environment add three **Environment secrets** (not repository secrets), with the same
   names in both so `deploy.yml` reads them the same way:
   - `DATABRICKS_HOST`: the workspace URL (same value in both)
   - `DATABRICKS_CLIENT_ID`: that environment's principal Application ID
   - `DATABRICKS_CLIENT_SECRET`: that environment's principal OAuth secret
3. On `prod`, tick **Required reviewers**, add `tomjwright` and save. The prod deploy job then waits
   for an approval before it can read the prod secrets or run.

## Rotating a service principal secret

A principal can hold up to 5 secrets, so rotation has no downtime. Only the secret changes;
the host and client ID stay the same.

1. Generate a new secret on the principal's Secrets tab. The old one keeps working.
2. Update GitHub: `gh secret set DATABRICKS_CLIENT_SECRET --env staging` (or `--env prod`).
3. Re-run the latest deploy workflow run and check it passes.
4. Delete the old secret in Databricks.
5. Update the expiry date in the table above. Rotate staging and prod on different days.

If a secret leaks, do steps 1-4 at once, deleting the leaked secret first.

## Proof: staging cannot write to prod

Run as the staging principal, from a local shell (never commit these values):

```bash
export DATABRICKS_HOST=https://<workspace>.cloud.databricks.com
export DATABRICKS_CLIENT_ID=acb14c44-9506-4f19-9375-e0b223869d04
export DATABRICKS_CLIENT_SECRET=<staging secret>
databricks current-user me                    # shows the principal, not you
databricks schemas create should_fail prod    # expect PERMISSION_DENIED
databricks schemas create proof_ok staging    # expect success, then drop it
unset DATABRICKS_CLIENT_ID DATABRICKS_CLIENT_SECRET
```

Result: (not run yet; paste both outputs here and in the PR)
