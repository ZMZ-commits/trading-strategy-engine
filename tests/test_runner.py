import json
import uuid
from pathlib import Path
import pytest
from trading_strategy_engine import run_strategy, get_status


@pytest.fixture
def store(tmp_path):
    return tmp_path


@pytest.fixture
def strategy(store):
    sid = str(uuid.uuid4())
    slug = "test-strategy"
    d = store / slug
    d.mkdir()
    (d / "runs").mkdir()
    (d / "strategy.json").write_text(json.dumps({
        "id": sid, "name": "Test", "slug": slug,
        "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z",
        "lastRunAt": None, "lastRunStatus": "idle",
        "config": {}, "transactions": [], "notifications": [],
    }))
    return {"id": sid, "dir": d}


def test_run_creates_run_file(strategy, store):
    result = run_strategy(strategy["id"], {}, store)
    runs = list((strategy["dir"] / "runs").glob("*.json"))
    assert len(runs) == 1
    assert result.run_id in runs[0].name


def test_run_returns_completed(strategy, store):
    result = run_strategy(strategy["id"], {}, store)
    assert result.state == "completed"
    assert result.strategy_id == strategy["id"]


def test_run_appends_transaction(strategy, store):
    result = run_strategy(strategy["id"], {}, store)
    assert len(result.transactions) == 1
    assert result.transactions[0].type == "signal"


def test_run_updates_strategy_json(strategy, store):
    run_strategy(strategy["id"], {}, store)
    data = json.loads((strategy["dir"] / "strategy.json").read_text())
    assert data["lastRunStatus"] == "completed"
    assert len(data["transactions"]) == 1


def test_get_status_idle_before_run(strategy, store):
    result = get_status(strategy["id"], store)
    assert result.state == "idle"


def test_get_status_completed_after_run(strategy, store):
    run_strategy(strategy["id"], {}, store)
    result = get_status(strategy["id"], store)
    assert result.state == "completed"


def test_get_status_missing_strategy(store):
    result = get_status("nonexistent-id", store)
    assert result.state == "idle"
