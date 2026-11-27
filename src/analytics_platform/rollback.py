"""Pure helpers for rolling prod back (ticket 06): is this a prod tag, and which Gold versions to restore.

Kept free of Spark so mutation testing covers them. gold_versions.py is the Spark job task that calls them.
"""

import re
from typing import Any

PROD_TAG = re.compile(r"prod-\d{4}-\d{2}-\d{2}-[0-9a-f]{7}")


def is_prod_tag(tag: str) -> bool:
    """True only for tags deploy.yml creates, e.g. prod-2026-11-27-58b8181."""
    return bool(PROD_TAG.fullmatch(tag))


def versions_for_run(rows: list[dict[str, Any]], run_id: str) -> dict[str, int]:
    """{table_name: version} for the rows recorded before one job run."""
    return {row["table_name"]: row["version"] for row in rows if row["run_id"] == run_id}


def restore_statements(versions: dict[str, int]) -> list[str]:
    """One Delta RESTORE per table, sorted by table name so the order is predictable."""
    return [
        f"RESTORE TABLE {table_name} TO VERSION AS OF {version}" for table_name, version in sorted(versions.items())
    ]
