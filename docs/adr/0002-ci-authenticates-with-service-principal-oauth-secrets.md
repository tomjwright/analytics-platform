# CI authenticates with service principal OAuth secrets, not OIDC

GitHub OIDC (workload identity federation) is the recommended way for GitHub Actions to reach Databricks, but its federation policies need the account console, which Free Edition does not provide. CI instead signs in with each deploy service principal's OAuth M2M client ID and secret, stored as secrets on the GitHub Environments `staging` and `prod`; `prod` requires a reviewer's approval before its job can read them.
