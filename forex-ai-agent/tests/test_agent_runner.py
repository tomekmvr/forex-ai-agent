from datetime import datetime, timezone

import pandas as pd

from src.admin.services import AdminPanelSnapshot
from src.agents.base import AgentSignal
from src.agents.orchestrator import OrchestratorDecision
from src.config.runner_settings import AgentRunnerSettings
from src.execution.base import AccountSnapshot, TradeExecutionResult
from src.risk.manager import KillSwitchState, RiskDecision
from src.runtime.agent_runner import execute_trading_cycle


def _build_snapshot(
    *,
    signal: int,
    approved: bool,
    positions: pd.DataFrame | None = None,
    position_units: int = 100,
) -> AdminPanelSnapshot:
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
            position_units=position_units,
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


def test_execute_trading_cycle_caps_broker_volume_with_risk_units(monkeypatch):
    monkeypatch.setenv("FOREX_AGENT_BROKER_PROFILE", "tms_oanda_mt5")
    monkeypatch.setenv("FOREX_AGENT_MT5_RELAY_URL", "http://127.0.0.1:8765")
    monkeypatch.setenv("FOREX_AGENT_MT5_RELAY_TOKEN", "relay-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("FOREX_AGENT_AI_DECISION_MODE", "supervisor")
    settings = AgentRunnerSettings(
        source_mode="broker",
        execution_mode="live",
        enable_live_execution=True,
        instrument="DE30.pro",
        order_volume=0.10,
        units_per_volume=1000,
        volume_step=0.01,
    )
    calls = []

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
        snapshot_func=lambda **kwargs: _build_snapshot(signal=1, approved=True, position_units=35),
        submit_order_func=fake_submit_order_func,
    )

    assert result.action == "submitted_order"
    assert calls[0]["volume"] == 0.03


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


def test_runner_validation_rejects_live_broker_mode_without_openai_supervisor(monkeypatch):
    monkeypatch.setenv("FOREX_AGENT_BROKER_PROFILE", "tms_oanda_mt5")
    monkeypatch.setenv("FOREX_AGENT_MT5_LOGIN", "123456")
    monkeypatch.setenv("FOREX_AGENT_MT5_PASSWORD", "secret")
    monkeypatch.setenv("FOREX_AGENT_MT5_SERVER", "OANDATMS-MT5")
    monkeypatch.setenv("FOREX_AGENT_MT5_TERMINAL_PATH", "C:/Program Files/TMS OANDA MetaTrader 5/terminal64.exe")
    monkeypatch.setenv("FOREX_AGENT_RUNNER_UNITS_PER_VOLUME", "1000")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("FOREX_AGENT_OPENAI_API_KEY", raising=False)

    settings = AgentRunnerSettings(
        **{
            **AgentRunnerSettings.from_env().__dict__,
            "source_mode": "broker",
            "execution_mode": "live",
            "enable_live_execution": True,
        }
    )

    try:
        settings.validate()
    except ValueError as exc:
        assert "OpenAI supervisor configuration" in str(exc)
    else:
        raise AssertionError("Live broker runner should reject missing OpenAI supervisor configuration")


def test_runner_validation_rejects_mt5_live_mode_without_terminal_path(monkeypatch):
    monkeypatch.setenv("FOREX_AGENT_BROKER_PROFILE", "tms_oanda_mt5")
    monkeypatch.setenv("FOREX_AGENT_MT5_LOGIN", "123456")
    monkeypatch.setenv("FOREX_AGENT_MT5_PASSWORD", "secret")
    monkeypatch.setenv("FOREX_AGENT_MT5_SERVER", "OANDATMS-MT5")
    monkeypatch.delenv("FOREX_AGENT_MT5_TERMINAL_PATH", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("FOREX_AGENT_AI_DECISION_MODE", "supervisor")
    monkeypatch.setenv("FOREX_AGENT_RUNNER_UNITS_PER_VOLUME", "1000")

    settings = AgentRunnerSettings(
        **{
            **AgentRunnerSettings.from_env().__dict__,
            "source_mode": "broker",
            "execution_mode": "live",
            "enable_live_execution": True,
        }
    )

    try:
        settings.validate()
    except ValueError as exc:
        assert "MT5_TERMINAL_PATH" in str(exc)
    else:
        raise AssertionError("Live MT5 runner should reject missing terminal path when no relay is configured")


def test_runner_validation_accepts_live_broker_mode_with_mt5_and_openai(monkeypatch):
    monkeypatch.setenv("FOREX_AGENT_BROKER_PROFILE", "tms_oanda_mt5")
    monkeypatch.setenv("FOREX_AGENT_MT5_LOGIN", "123456")
    monkeypatch.setenv("FOREX_AGENT_MT5_PASSWORD", "secret")
    monkeypatch.setenv("FOREX_AGENT_MT5_SERVER", "OANDATMS-MT5")
    monkeypatch.setenv("FOREX_AGENT_MT5_TERMINAL_PATH", "C:/Program Files/TMS OANDA MetaTrader 5/terminal64.exe")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("FOREX_AGENT_AI_DECISION_MODE", "supervisor")
    monkeypatch.setenv("FOREX_AGENT_RUNNER_UNITS_PER_VOLUME", "1000")

    settings = AgentRunnerSettings.from_env()

    settings.validate()


def test_runner_validation_rejects_broker_mode_without_units_per_volume(monkeypatch):
    monkeypatch.setenv("FOREX_AGENT_BROKER_PROFILE", "tms_oanda_mt5")
    monkeypatch.setenv("FOREX_AGENT_MT5_RELAY_URL", "http://127.0.0.1:8765")
    monkeypatch.setenv("FOREX_AGENT_MT5_RELAY_TOKEN", "relay-secret")

    settings = AgentRunnerSettings(source_mode="broker", execution_mode="paper", units_per_volume=0)

    try:
        settings.validate()
    except ValueError as exc:
        assert "UNITS_PER_VOLUME" in str(exc)
    else:
        raise AssertionError("Broker runner should reject missing units-per-volume mapping")