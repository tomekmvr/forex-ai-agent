from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from math import floor
from typing import Callable, Optional

import pandas as pd

from src.admin.services import close_admin_position, run_admin_snapshot, submit_admin_order
from src.config.runner_settings import AgentRunnerSettings
from src.execution.base import TradeExecutionResult


@dataclass(frozen=True)
class AgentCycleResult:
    timestamp: datetime
    instrument: str
    action: str
    execution_mode: str
    signal: int
    approved: bool
    confidence: float
    source_name: str
    status_message: str
    order_result: Optional[TradeExecutionResult] = None
    close_results: tuple[TradeExecutionResult, ...] = field(default_factory=tuple)

    def to_record(self) -> dict[str, object]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        return payload


def execute_trading_cycle(
    settings: AgentRunnerSettings,
    *,
    snapshot_func: Callable[..., object] = run_admin_snapshot,
    submit_order_func: Callable[..., TradeExecutionResult] = submit_admin_order,
    close_position_func: Callable[..., TradeExecutionResult] = close_admin_position,
) -> AgentCycleResult:
    settings.validate()

    snapshot = snapshot_func(
        equity=settings.equity,
        session_start_equity=settings.session_start_equity,
        current_equity=settings.current_equity,
        instrument=settings.instrument,
        granularity=settings.granularity,
        periods=settings.periods,
        source_mode=settings.source_mode,
        win_probability=settings.win_probability,
        payoff_ratio=settings.payoff_ratio,
        failure_probability=settings.failure_probability,
        decision_threshold=settings.decision_threshold,
    )

    decision = snapshot.orchestrator_decision
    risk = snapshot.risk_decision
    positions = snapshot.positions if isinstance(snapshot.positions, pd.DataFrame) else pd.DataFrame()
    instrument_positions = positions
    if not instrument_positions.empty and "instrument" in instrument_positions.columns:
        instrument_positions = instrument_positions[instrument_positions["instrument"] == settings.instrument]

    if not risk.approved or decision.final_signal == 0:
        return AgentCycleResult(
            timestamp=datetime.now(timezone.utc),
            instrument=settings.instrument,
            action="no_trade",
            execution_mode=settings.execution_mode,
            signal=decision.final_signal,
            approved=risk.approved,
            confidence=decision.confidence,
            source_name=snapshot.source_name,
            status_message=snapshot.status_message,
        )

    order_volume = _resolve_order_volume(settings=settings, approved_units=risk.position_units)
    if order_volume <= 0:
        return AgentCycleResult(
            timestamp=datetime.now(timezone.utc),
            instrument=settings.instrument,
            action="no_trade",
            execution_mode=settings.execution_mode,
            signal=decision.final_signal,
            approved=False,
            confidence=decision.confidence,
            source_name=snapshot.source_name,
            status_message="Resolved execution volume is zero after applying risk limits.",
        )

    target_side = "buy" if decision.final_signal > 0 else "sell"
    target_position_side = "long" if target_side == "buy" else "short"
    same_side_positions = _filter_positions_by_side(instrument_positions, target_position_side)
    opposite_side = "short" if target_position_side == "long" else "long"
    opposite_positions = _filter_positions_by_side(instrument_positions, opposite_side)

    if not same_side_positions.empty and not settings.allow_same_side_reentry:
        return AgentCycleResult(
            timestamp=datetime.now(timezone.utc),
            instrument=settings.instrument,
            action="hold_existing",
            execution_mode=settings.execution_mode,
            signal=decision.final_signal,
            approved=risk.approved,
            confidence=decision.confidence,
            source_name=snapshot.source_name,
            status_message="Existing same-side position detected. New order skipped.",
        )

    close_results = []
    if settings.close_opposite_positions and not opposite_positions.empty:
        for row in opposite_positions.itertuples(index=False):
            close_results.append(
                close_position_func(
                    source_mode=settings.source_mode,
                    instrument=str(row.instrument),
                    position_id=str(getattr(row, "position_id", "")),
                    volume=float(getattr(row, "units", settings.order_volume)),
                    side=str(row.side),
                    execution_mode=settings.execution_mode,
                    confirm_live_execution=settings.enable_live_execution,
                    comment=f"{settings.comment_prefix} close opposite",
                )
            )

    order_result = submit_order_func(
        source_mode=settings.source_mode,
        instrument=settings.instrument,
        side=target_side,
        volume=order_volume,
        execution_mode=settings.execution_mode,
        confirm_live_execution=settings.enable_live_execution,
        comment=f"{settings.comment_prefix} signal={decision.final_signal}",
    )
    action = "submitted_order" if order_result.success else "order_rejected"
    return AgentCycleResult(
        timestamp=datetime.now(timezone.utc),
        instrument=settings.instrument,
        action=action,
        execution_mode=settings.execution_mode,
        signal=decision.final_signal,
        approved=risk.approved,
        confidence=decision.confidence,
        source_name=snapshot.source_name,
        status_message=snapshot.status_message,
        order_result=order_result,
        close_results=tuple(close_results),
    )


def run_agent_loop(settings: AgentRunnerSettings) -> None:
    settings.validate()
    while True:
        result = execute_trading_cycle(settings)
        print(json.dumps(result.to_record(), ensure_ascii=True, default=str))
        if settings.run_once:
            return
        time.sleep(settings.poll_interval_seconds)


def _filter_positions_by_side(frame: pd.DataFrame, side: str) -> pd.DataFrame:
    if frame.empty or "side" not in frame.columns:
        return pd.DataFrame(columns=frame.columns)
    normalized = frame["side"].astype(str).str.lower()
    return frame[normalized == side.lower()].copy()


def _resolve_order_volume(*, settings: AgentRunnerSettings, approved_units: int) -> float:
    if settings.source_mode == "demo":
        return settings.order_volume

    broker_volume = approved_units / settings.units_per_volume
    stepped_volume = floor(broker_volume / settings.volume_step) * settings.volume_step
    resolved = min(settings.order_volume, stepped_volume)
    return round(max(0.0, resolved), 8)


def main() -> None:
    settings = AgentRunnerSettings.from_env()
    run_agent_loop(settings)


if __name__ == "__main__":
    main()