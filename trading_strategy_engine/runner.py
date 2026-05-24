from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .models import RunResult, Transaction


def _find_strategy_dir(store_path: Path, strategy_id: str) -> Path:
    for d in store_path.iterdir():
        if not d.is_dir():
            continue
        json_file = d / "strategy.json"
        if json_file.exists():
            data = json.loads(json_file.read_text())
            if data.get("id") == strategy_id:
                return d
    raise FileNotFoundError(f"Strategy {strategy_id} not found")


def run_strategy(strategy_id: str, config: dict, store_path: Path) -> RunResult:
    store_path = Path(store_path)
    strategy_dir = _find_strategy_dir(store_path, strategy_id)
    runs_dir = strategy_dir / "runs"
    runs_dir.mkdir(exist_ok=True)

    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    run_file = runs_dir / f"{run_id}.json"
    draft = RunResult(run_id=run_id, strategy_id=strategy_id, state="running", started_at=started_at)
    run_file.write_text(draft.model_dump_json(indent=2))

    transaction = Transaction(
        run_id=run_id,
        type="signal",
        message=f"Strategy initialized, run {run_id} started",
    )

    completed_at = datetime.now(timezone.utc)
    result = RunResult(
        run_id=run_id,
        strategy_id=strategy_id,
        state="completed",
        started_at=started_at,
        completed_at=completed_at,
        transactions=[transaction],
    )
    run_file.write_text(result.model_dump_json(indent=2))

    strategy_json = strategy_dir / "strategy.json"
    data = json.loads(strategy_json.read_text())
    data["lastRunAt"] = completed_at.isoformat()
    data["lastRunStatus"] = "completed"
    existing_txns = data.get("transactions", [])
    existing_txns.append(json.loads(transaction.model_dump_json()))
    data["transactions"] = existing_txns
    strategy_json.write_text(json.dumps(data, indent=2, default=str))

    return result


def get_status(strategy_id: str, store_path: Path) -> RunResult:
    store_path = Path(store_path)
    idle = RunResult(
        strategy_id=strategy_id,
        state="idle",
        started_at=datetime.now(timezone.utc),
    )
    try:
        strategy_dir = _find_strategy_dir(store_path, strategy_id)
    except FileNotFoundError:
        return idle

    runs_dir = strategy_dir / "runs"
    if not runs_dir.exists():
        return idle

    run_files = sorted(runs_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not run_files:
        return idle

    return RunResult.model_validate_json(run_files[0].read_text())
