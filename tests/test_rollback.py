"""Ticket 06's pure rollback helpers: which tags can be rolled back to, and which Gold versions to restore."""

import pytest

from analytics_platform.cicd import main
from analytics_platform.rollback import is_prod_tag, restore_statements, versions_for_run


@pytest.mark.parametrize("tag", ["prod-2026-11-27-58b8181", "prod-2027-01-31-0a1b2c3"])
def test_prod_tags_are_accepted(tag):
    assert is_prod_tag(tag)


@pytest.mark.parametrize(
    "tag",
    [
        "main",  # a branch: rolling "back" to it would deploy untested code
        "58b8181",  # a bare SHA: maybe never approved for prod
        "staging-2026-11-27-58b8181",
        "prod-2026-11-27-58b818",  # short SHA too short
        "prod-2026-11-27-58b81812",  # too long
        "prod-2026-11-27-58B8181",  # git SHAs are lowercase
        "prod-26-11-27-58b8181",
        "xprod-2026-11-27-58b8181",
        "prod-2026-11-27-58b8181; rm -rf /",
        "",
    ],
)
def test_anything_else_is_rejected(tag):
    assert not is_prod_tag(tag)


RECORDED = [
    {"run_id": "111", "table_name": "prod.gold.dim_customer", "version": 4},
    {"run_id": "111", "table_name": "prod.gold.fct_orders", "version": 9},
    {"run_id": "222", "table_name": "prod.gold.dim_customer", "version": 5},
]


def test_versions_for_run_keeps_only_that_runs_versions():
    assert versions_for_run(RECORDED, "111") == {"prod.gold.dim_customer": 4, "prod.gold.fct_orders": 9}
    assert versions_for_run(RECORDED, "222") == {"prod.gold.dim_customer": 5}


def test_versions_for_an_unknown_run_is_empty():
    assert versions_for_run(RECORDED, "333") == {}


def test_restore_statements_are_one_per_table_in_name_order():
    assert restore_statements({"prod.gold.fct_orders": 9, "prod.gold.dim_customer": 4}) == [
        "RESTORE TABLE prod.gold.dim_customer TO VERSION AS OF 4",
        "RESTORE TABLE prod.gold.fct_orders TO VERSION AS OF 9",
    ]


def test_nothing_to_restore_gives_no_statements():
    assert restore_statements({}) == []


def test_check_tag_exits_0_for_a_prod_tag():
    assert main(["check-tag", "prod-2026-11-27-58b8181"]) == 0


def test_check_tag_exits_1_and_says_why_otherwise(capsys):
    assert main(["check-tag", "main"]) == 1
    assert "not a prod tag: 'main'" in capsys.readouterr().err
