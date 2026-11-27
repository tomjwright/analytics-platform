# Postmortem: <one line on what broke>

Blameless: this is about how the system let the mistake through and how we recovered, not who made it.

<!--
TODO(ticket 06): run the drill, then fill in every section with what actually happened (times, run ids,
row counts, tags) and delete this comment. The test fails until no TODO is left.

The drill:
1. Break staging: on a branch, make dim_customer fail a dbt test (e.g. emit a duplicate key). Merge it
   (or run deploy.yml with workflow_dispatch). Confirm staging fails and prod never asks for approval.
   Revert, and confirm the next deploy goes green.
2. Break prod's data: a change that passes every test but is wrong (e.g. upper-case every city), merged
   and approved. Note the customer_tracer run id that built it.
3. Recover with no UI edits:
   - code: gh workflow run rollback -f tag=<previous prod-* tag> -f restore_run_id=<bad run id>
   - approve, then check prod.gold.dim_customer is back (row counts, a few cities, DESCRIBE HISTORY).
4. Time each step: detect, decide, roll back, verify.
-->

## Summary
TODO: what broke, for how long, how it was fixed, in 3 sentences.

## Timeline
TODO: UTC times, from the bad merge to verified recovery.

## Impact
TODO: which tables, how many rows were wrong, for how long, who would have seen it.

## Root cause
TODO: why the tests didn't catch it (the "five whys", stopping at a process or system gap).

## Recovery
TODO: the exact commands, the tag and run id, and how you verified Gold was back.

## Actions
TODO: what changes so this can't happen again, or is caught sooner (each with an owner and a ticket).
