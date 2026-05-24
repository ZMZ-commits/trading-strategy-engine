from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional
from pydantic import BaseModel, Field

StrategyStatus = Literal["idle", "running", "completed", "error"]


class Transaction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    type: Literal["signal", "order", "error"]
    message: str
    data: dict = Field(default_factory=dict)


class RunResult(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str
    state: StrategyStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    transactions: list[Transaction] = Field(default_factory=list)
    notifications: list[str] = Field(default_factory=list)


class RunConfig(BaseModel):
    config: dict = Field(default_factory=dict)
