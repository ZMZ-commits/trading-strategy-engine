import json
from trading_strategy_engine.models import Transaction, RunResult
from datetime import datetime, timezone


def test_transaction_round_trip():
    t = Transaction(run_id="r1", type="signal", message="test", data={"k": "v"})
    restored = Transaction.model_validate_json(t.model_dump_json())
    assert restored.id == t.id
    assert restored.type == "signal"


def test_run_result_round_trip():
    r = RunResult(strategy_id="s1", state="completed", started_at=datetime.now(timezone.utc))
    restored = RunResult.model_validate_json(r.model_dump_json())
    assert restored.state == "completed"
    assert restored.strategy_id == "s1"
