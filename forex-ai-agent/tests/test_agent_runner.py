from datetime import datetime, timezone

import pandas as pd

from src.admin.services import AdminPanelSnapshot
from src.agents.base import AgentSignal
from src.agents.orchestrator import OrchestratorDecision
from src.config.runner_settings import AgentRunnerSettings
from src.execution.base import AccountSnapshot, TradeExecutionResult
from src.risk.manager import KillSwitchState, RiskDecision
from src.runtime.agent_runner import execute_trading_cycle


def _build_snapshot(*, signal: int, approved: bool, positions: pd.DataFrame | None = None) -> AdminPanelSnapshot:
    index = pd.date_range("2026-01-01", periods=60, freq="h")
    return AdminPanelSnapshot(
        source_name="demo",
        status_message="snapshot ok",
        live_connected=False,
        market_features=pd.DataFrame(
            {
                "close": [1.08 + step * 0.0002 for step in range(60)],
                "realized_volatility": [0.0015 for _ in range(60)],
            },
            index=index,
        ),
        news_features=pd.DataFrame(),
        calendar_features=pd.DataFrame(),
        account_snapshot=AccountSnapshot(
            broker="demo",
            account_id="demo",
            balance=100_000.0,
            equity=100_000.0,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            margin_used=0.0,
            margin_available=100_000.0,
        ),
        positions=positions if positions is not None else pd.DataFrame(),
        trade_history=pd.DataFrame(),
        kill_switch_state=KillSwitchState(False, 0.0, 0.03, "ok"),
        orchestrator_decision=OrchestratorDecision(
            final_signal=signal,
            confidence=0.62,
            weighted_score=0.62,
            approved=signal != 0,
            agent_signals=(
                AgentSignal("technical_agent", signal, 0.62, "ok"),
            ),
            reasoning="ok",
        ),
        risk_decision=RiskDecision(
            approved=approved,
            kill_switch_triggered=False,
            requested_signal=signal,
            approved_signal=signal if approved else 0,
            position_units=100,
            capital_fraction=0.02,
            risk_budget=2000.0,
            expected_transaction_cost=2.0,
            reasoning="ok",
            diagnostics={},
        ),
    )


def test_execute_trading_cycle_submits_order_when_approved():
    settings = AgentRunnerSettings(source_mode="demo", execution_mode="paper", instrument="DE30.pro")
    calls = []

    def fake_snapshot_func(**kwargs):
        return _build_snapshot(signal=1, approved=True)

    def fake_submit_order_func(**kwargs):
        calls.append(kwargs)
        return TradeExecutionResult(
            success=True,
            broker="paper",
            instrument=kwargs["instrument"],
            side=kwargs["side"],
            requested_volume=kwargs["volume"],
            filled_volume=kwargs["volume"],
            executed_price=0.0,
            broker_order_id="paper-order",
            status_code="PAPER",
            message="ok",
            request_payload=kwargs,
        )

    result = execute_trading_cycle(
        settings,
        snapshot_func=fake_snapshot_func,
        submit_order_func=fake_submit_order_func,
    )

    assert result.action == "submitted_order"
    assert len(calls) == 1
    assert calls[0]["side"] == "buy"
    assert calls[0]["volume"] == settings.order_volume


def test_execute_trading_cycle_skips_when_same_side_position_exists():
    settings = AgentRunnerSettings(source_mode="demo", execution_mode="paper", instrument="DE30.pro")
    positions = pd.DataFrame(
        [
            {
                "instrument": "DE30.pro",
                "side": "long",
                "units": 0.10,
                "position_id": "123",
            }
        ]
    )

    result = execute_trading_cycle(
        settings,
        snapshot_func=lambda **kwargs: _build_snapshot(signal=1, approved=True, positions=positions),
    )

    assert result.action == "hold_existing"
    assert result.order_result is None


def test_execute_trading_cycle_closes_opposite_position_before_submitting():
    settings = AgentRunnerSettings(source_mode="demo", execution_mode="paper", instrument="DE30.pro")
    positions = pd.DataFrame(
        [
            {
                "instrument": "DE30.pro",
                "side": "short",
                "units": 0.10,
                "position_id": "123",
            }
        ]
    )
    close_calls = []
    submit_calls = []

    def fake_close_position_func(**kwargs):
        close_calls.append(kwargs)
        return TradeExecutionResult(
            success=True,
            broker="paper",
            instrument=kwargs["instrument"],
            side="buy",
            requested_volume=kwargs["volume"],
            filled_volume=kwargs["volume"],
            executed_price=0.0,
            broker_order_id="close-order",
            status_code="PAPER_CLOSE",
            message="closed",
            request_payload=kwargs,
        )

    def fake_submit_order_func(**kwargs):
        submit_calls.append(kwargs)
        return TradeExecutionResult(
            success=True,
            broker="paper",
            instrument=kwargs["instrument"],
            side=kwargs["side"],
            requested_volume=kwargs["volume"],
            filled_volume=kwargs["volume"],
            executed_price=0.0,
            broker_order_id="paper-order",
            status_code="PAPER",
            message="ok",
            request_payload=kwargs,
        )

    result = execute_trading_cycle(
        settings,
        snapshot_func=lambda **kwargs: _build_snapshot(signal=1, approved=True, positions=positions),
        submit_order_func=fake_submit_order_func,
        close_position_func=fake_close_position_func,
    )

    assert len(close_calls) == 1
    assert len(submit_calls) == 1
    assert result.action == "submitted_order"