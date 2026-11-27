"""Pure helpers for rolling prod back (ticket 06): is this a prod tag, and which Gold versions to restore.

Kept free of Spark so mutation testing covers them. gold_versions.py is the Spark job task that calls them.
"""

import re
from typing import Any

PROD_TAG = re.compile(r"prod-\d{4}-\d{2}-\d{2}-[0-9a-f]{7}")


def is_prod_tag(tag: str) -> bool:
    """True only for tags deploy.yml creates, e.g. prod-2026-11-27-58b8181.

    TODO(ticket 06): match the whole string against PROD_TAG. Which re method matches the whole string,
    rather than just the start? (Why does "prod-2026-11-27-58b8181; rm -rf /" have to be rejected?)
    """
    raise NotImplementedError


def versions_for_run(rows: list[dict[str, Any]], run_id: str) -> dict[str, int]:
    """{table_name: version} for the rows recorded before one job run.

    TODO(ticket 06): rows are ops.gold_versions as dicts: {"run_id", "table_name", "version"}.
    Keep only this run's rows. A dict comprehension with an `if` is one line.
    """
    raise NotImplementedError


def restore_statements(versions: dict[str, int]) -> list[str]:
    """One Delta RESTORE per table, sorted by table name so the order is predictable.

    TODO(ticket 06): see the expected strings in tests/test_rollback.py.
    Docs: https://docs.databricks.com/aws/en/sql/language-manual/delta-restore
    """
    raise NotImplementedError
