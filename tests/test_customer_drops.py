"""The Customer File Drop chaos generator."""

import json
import urllib.request
from datetime import date
from pathlib import Path

import pytest

from analytics_platform.customer_drops import (
    FAULTS,
    ChaosRates,
    download,
    generate,
    load_customers,
    main,
    malform,
    write_drop,
)

DAY_1 = date(2017, 1, 1)
DAY_2 = date(2017, 1, 2)
NO_CHAOS = ChaosRates()

CUSTOMERS_CSV = """customer_id,customer_unique_id,customer_zip_code_prefix,customer_city,customer_state
c1,alice,1001,sao paulo,SP
c2,bob,20040,rio de janeiro,RJ
c3,alice,30110,belo horizonte,MG
c4,carla,40010,salvador,BA
c5,carla,50010,recife,PE
"""
ORDERS_CSV = """"order_id","customer_id","order_status","order_purchase_timestamp"
o1,"c1",delivered,2017-01-01 10:56:33
o2,"c2",delivered,2017-01-02 08:00:00
o3,"c3",delivered,2017-03-01 09:30:00
o4,"c4",delivered,2017-01-01 23:59:59
o5,"c5",delivered,2017-01-01 08:00:00
"""


@pytest.fixture
def olist(tmp_path):
    cache = tmp_path / "olist"
    cache.mkdir()
    (cache / "olist_customers_dataset.csv").write_text(CUSTOMERS_CSV)
    (cache / "olist_orders_dataset.csv").write_text(ORDERS_CSV)
    return cache


@pytest.fixture
def customers(olist):
    return load_customers(olist / "olist_customers_dataset.csv", olist / "olist_orders_dataset.csv")


def ids(rows):
    return [row["customer_unique_id"] for row in rows]


def test_a_customer_is_one_unique_id_at_their_first_order(customers):
    assert [c.unique_id for c in customers] == ["alice", "bob", "carla"]
    alice = customers[0]
    assert (alice.city, alice.updated_at) == ("sao paulo", DAY_1)
    assert customers[2].city == "salvador", "on a same-day tie the first row in the file wins"


def test_a_customer_appears_from_the_day_of_their_first_order(customers):
    drops = generate(customers, DAY_1, 2, NO_CHAOS, seed=1)
    assert ids(drops[DAY_1]) == ["alice", "carla"]
    assert ids(drops[DAY_2]) == ["alice", "bob", "carla"]


def test_without_chaos_each_row_is_the_clean_customer(customers):
    drops = generate(customers, DAY_1, 1, NO_CHAOS, seed=1)
    assert drops[DAY_1][0] == {
        "customer_unique_id": "alice",
        "zip_code_prefix": "1001",
        "city": "sao paulo",
        "state": "SP",
        "updated_at": "2017-01-01",
    }


def test_duplicates_repeat_a_row(customers):
    drops = generate(customers, DAY_1, 1, ChaosRates(duplicate=1.0), seed=1)
    assert ids(drops[DAY_1]) == ["alice", "alice", "carla", "carla"]
    assert drops[DAY_1][0] == drops[DAY_1][1]


@pytest.mark.parametrize(
    ("fault", "column", "value"),
    [
        ("missing_id", "customer_unique_id", ""),
        ("bad_zip", "zip_code_prefix", "not-a-zip"),
        ("bad_date", "updated_at", "not-a-date"),
    ],
)
def test_each_fault_breaks_one_column(customers, fault, column, value):
    row = generate(customers, DAY_1, 1, NO_CHAOS, seed=1)[DAY_1][0]
    broken = malform(row, fault)
    assert broken[column] == value
    assert {k: v for k, v in broken.items() if k != column} == {k: v for k, v in row.items() if k != column}
    assert row["customer_unique_id"] == "alice", "the original row is not changed"


def test_malformed_rows_replace_the_clean_row(customers):
    drops = generate(customers, DAY_1, 30, ChaosRates(malformed=1.0), seed=1)
    rows = [row for day_rows in drops.values() for row in day_rows]
    clean = generate(customers, DAY_1, 30, NO_CHAOS, seed=1)
    assert len(rows) == sum(len(day_rows) for day_rows in clean.values())
    faults_seen = {fault for fault in FAULTS for row in rows if malform(row, fault) == row}
    assert faults_seen == set(FAULTS)


def test_a_changed_address_appears_the_next_day(customers):
    drops = generate(customers, DAY_1, 2, ChaosRates(address_change=1.0), seed=3)
    day_1 = {row["customer_unique_id"]: row for row in drops[DAY_1]}
    day_2 = {row["customer_unique_id"]: row for row in drops[DAY_2]}
    assert all(row["updated_at"] == "2017-01-01" for row in day_1.values())
    assert day_2["alice"]["updated_at"] == "2017-01-02"
    assert day_2["bob"]["updated_at"] == "2017-01-02", "bob is new today, so he has not moved yet"
    addresses = {(c.zip_code_prefix, c.city, c.state) for c in customers}
    assert all((row["zip_code_prefix"], row["city"], row["state"]) in addresses for row in day_2.values())
    moved = [uid for uid in day_1 if day_2[uid]["city"] != day_1[uid]["city"]]
    assert moved, "at least one existing Customer has a new address"


def test_a_move_keeps_the_new_address_on_later_days(customers):
    drops = generate(customers, DAY_1, 3, ChaosRates(address_change=0.5), seed=7)
    for day, next_day in [(DAY_1, DAY_2), (DAY_2, date(2017, 1, 3))]:
        today = {row["customer_unique_id"]: row for row in drops[day]}
        for row in drops[next_day]:
            if row["updated_at"] != next_day.isoformat():
                assert row == today[row["customer_unique_id"]]


def test_the_same_seed_gives_byte_identical_file_drops(customers, tmp_path):
    rates = ChaosRates(duplicate=0.3, malformed=0.3, address_change=0.3)
    first = [write_drop(tmp_path / "a", d, r) for d, r in generate(customers, DAY_1, 3, rates, seed=9).items()]
    second = [write_drop(tmp_path / "b", d, r) for d, r in generate(customers, DAY_1, 3, rates, seed=9).items()]
    assert [p.read_bytes() for p in first] == [p.read_bytes() for p in second]
    other = generate(customers, DAY_1, 3, rates, seed=10)
    assert other != generate(customers, DAY_1, 3, rates, seed=9)


def test_a_drop_lands_under_its_ingest_date(customers, tmp_path):
    rows = generate(customers, DAY_1, 1, NO_CHAOS, seed=1)[DAY_1]
    path = write_drop(tmp_path, DAY_1, rows)
    assert path == tmp_path / "customers" / "ingest_date=2017-01-01" / "customers_2017-01-01.csv"
    lines = path.read_text().splitlines()
    assert lines[0] == "customer_unique_id,zip_code_prefix,city,state,updated_at"
    assert lines[1] == "alice,1001,sao paulo,SP,2017-01-01"
    assert b"\r\n" not in path.read_bytes()
    assert write_drop(tmp_path, DAY_1, rows[:1]) == path, "a re-run overwrites the day's drop"
    assert len(path.read_text().splitlines()) == 2


def test_download_fetches_once_into_the_cache(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "f.csv").write_text("a,b\n")
    cache = tmp_path / "cache" / "olist"
    path = download("f.csv", cache, base_url=source.as_uri())
    assert path == cache / "f.csv"
    assert path.read_text() == "a,b\n"
    (source / "f.csv").unlink()
    assert download("f.csv", cache, base_url=source.as_uri()) == path


def test_download_uses_the_cache_without_a_network_call(tmp_path):
    (tmp_path / "f.csv").write_text("cached\n")
    assert download("f.csv", tmp_path, base_url="https://example.invalid").read_text() == "cached\n"


def test_an_interrupted_download_is_not_cached(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "f.csv").write_text("a,b\n")
    cache = tmp_path / "cache"

    def interrupted(url, filename):
        Path(filename).write_text("a,")
        raise ConnectionResetError

    monkeypatch.setattr(urllib.request, "urlretrieve", interrupted)
    with pytest.raises(ConnectionResetError):
        download("f.csv", cache, base_url=source.as_uri())
    assert not (cache / "f.csv").exists()
    monkeypatch.undo()
    assert download("f.csv", cache, base_url=source.as_uri()).read_text() == "a,b\n"


def test_download_refuses_plain_http(tmp_path):
    with pytest.raises(ValueError, match="refusing"):
        download("f.csv", tmp_path, base_url="http://example.com")


def test_main_writes_one_drop_per_day_and_logs_it(olist, tmp_path, capsys):
    out = tmp_path / "landing"
    assert main(["--start", "2017-01-01", "--days", "2", "--out", str(out), "--cache", str(olist)]) == 0
    logs = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [log["ingest_date"] for log in logs] == ["2017-01-01", "2017-01-02"]
    assert logs[0]["event"] == "customer_drop"
    assert sorted(p.name for p in (out / "customers").iterdir()) == ["ingest_date=2017-01-01", "ingest_date=2017-01-02"]


def test_main_defaults_to_one_day(olist, tmp_path, capsys):
    assert main(["--start", "2017-01-01", "--out", str(tmp_path), "--cache", str(olist)]) == 0
    assert len(capsys.readouterr().out.splitlines()) == 1


@pytest.mark.parametrize("missing", ["--start", "--out"])
def test_main_requires_start_and_out(olist, tmp_path, missing):
    args = {"--start": "2017-01-01", "--out": str(tmp_path), "--cache": str(olist)}
    del args[missing]
    with pytest.raises(SystemExit):
        main([part for pair in args.items() for part in pair])


def test_main_help_describes_the_generator(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    assert "Chaos generator for Customer File Drops" in capsys.readouterr().out
