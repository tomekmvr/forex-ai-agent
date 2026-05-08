import pandas as pd

from src.admin.services import (
    build_market_features,
    close_admin_position,
    get_symbol_presets,
    load_market_snapshot,
    run_admin_snapshot,
    submit_admin_order,
)
from src.execution.adapters import BrokerDataSnapshot
from src.execution.base import AccountSnapshot, PositionSnapshot


def test_build_market_features_enriches_price_frame():
    index = pd.date_range("2026-01-01", periods=30, freq="h")
    price_frame = pd.DataFrame({"close": [1.10 + step * 0.0005 for step in range(30)]}, index=index)

    market_features = build_market_features(price_frame)

    assert "returns" in market_features.columns
    assert "realized_volatility" in market_features.columns
    assert market_features["realized_volatility"].iloc[-1] >= 0


def test_run_admin_snapshot_returns_orchestrator_and_risk_decisions():
    index = pd.date_range("2026-01-01", periods=60, freq="h")
    price_frame = pd.DataFrame({"close": [1.08 + step * 0.0004 for step in range(60)]}, index=index)

    snapshot = run_admin_snapshot(
        price_frame=price_frame,
        equity=100_000,
        session_start_equity=100_000,
        current_equity=99_400,
        win_probability=0.58,
        payoff_ratio=1.8,
        failure_probability=0.07,
    )

    assert snapshot.orchestrator_decision.final_signal in {-1, 0, 1}
    assert 0.0 <= snapshot.orchestrator_decision.confidence <= 0.99
    assert snapshot.risk_decision.requested_signal == snapshot.orchestrator_decision.final_signal
    assert snapshot.market_features.index.is_monotonic_increasing


def test_load_market_snapshot_returns_demo_data_in_demo_mode():
    snapshot = load_market_snapshot(
        source_mode="demo",
        instrument="EUR_USD",
        granularity="H1",
        periods=48,
    )

    assert snapshot.source_name == "demo"
    assert not snapshot.market_prices.empty
    assert snapshot.account_snapshot.broker == "demo"
    assert len(snapshot.positions) == 1


def test_run_admin_snapshot_preserves_broker_snapshot_metadata():
    index = pd.date_range("2026-01-01", periods=60, freq="h")
    broker_snapshot = BrokerDataSnapshot(
        source_name="oanda_practice",
        status_message="Loaded broker snapshot for EUR_USD.",
        live_connected=True,
        market_prices=pd.DataFrame({"close": [1.08 + step * 0.0002 for step in range(60)]}, index=index),
        account_snapshot=AccountSnapshot(
            broker="oanda_practice",
            account_id="101-001-1234567-001",
            balance=100_000.0,
            equity=100_250.0,
            unrealized_pnl=250.0,
            realized_pnl=500.0,
            margin_used=5_000.0,
            margin_available=95_250.0,
        ),
        positions=(
            PositionSnapshot(
                instrument="EUR_USD",
                side="long",
                units=10_000.0,
                entry_price=1.0820,
                current_price=1.0845,
                unrealized_pnl=25.0,
                realized_pnl=0.0,
            ),
        ),
    )

    snapshot = run_admin_snapshot(
        broker_snapshot=broker_snapshot,
        equity=100_000,
        session_start_equity=100_000,
        current_equity=99_700,
        instrument="EUR_USD",
    )

    assert snapshot.source_name == "oanda_practice"
    assert snapshot.live_connected is True
    assert snapshot.account_snapshot.account_id == "101-001-1234567-001"
    assert not snapshot.positions.empty
    assert snapshot.kill_switch_state.triggered is False
    assert snapshot.trade_history.empty


def test_run_admin_snapshot_uses_broker_equity_for_live_risk_inputs():
    index = pd.date_range("2026-01-01", periods=60, freq="h")
    broker_snapshot = BrokerDataSnapshot(
        source_name="oanda_practice",
        status_message="Loaded broker snapshot for EUR_USD.",
        live_connected=True,
        market_prices=pd.DataFrame({"close": [1.08 + step * 0.0002 for step in range(60)]}, index=index),
        account_snapshot=AccountSnapshot(
            broker="oanda_practice",
            account_id="101-001-1234567-001",
            balance=100_000.0,
            equity=100_250.0,
            unrealized_pnl=250.0,
            realized_pnl=500.0,
            margin_used=5_000.0,
            margin_available=95_250.0,
        ),
        positions=tuple(),
    )

    snapshot = run_admin_snapshot(
        broker_snapshot=broker_snapshot,
        equity=10_000,
        session_start_equity=99_000,
        current_equity=10_000,
        instrument="EUR_USD",
    )

    assert snapshot.kill_switch_state.drawdown == 0.0
    assert snapshot.risk_decision.risk_budget > 5_000


def test_run_admin_snapshot_does_not_inject_fake_news_for_live_broker_data():
    index = pd.date_range("2026-01-01", periods=60, freq="h")
    broker_snapshot = BrokerDataSnapshot(
        source_name="oanda_practice",
        status_message="Loaded broker snapshot for EUR_USD.",
        live_connected=True,
        market_prices=pd.DataFrame({"close": [1.08 + step * 0.0002 for step in range(60)]}, index=index),
        account_snapshot=AccountSnapshot(
            broker="oanda_practice",
            account_id="101-001-1234567-001",
            balance=100_000.0,
            equity=100_250.0,
            unrealized_pnl=250.0,
            realized_pnl=500.0,
            margin_used=5_000.0,
            margin_available=95_250.0,
        ),
        positions=tuple(),
    )

    snapshot = run_admin_snapshot(
        broker_snapshot=broker_snapshot,
        equity=100_000,
        session_start_equity=100_000,
        current_equity=100_000,
        instrument="EUR_USD",
    )

    assert snapshot.news_features.empty is True
    assert snapshot.calendar_features.empty is True
    sentiment_signal = next(
        signal for signal in snapshot.orchestrator_decision.agent_signals if signal.agent_name == "sentiment_agent"
    )
    assert sentiment_signal.signal == 0
    assert sentiment_signal.confidence == 0.0


def test_get_symbol_presets_returns_mt5_symbols_for_mt5_profile(monkeypatch):
    monkeypatch.setenv("FOREX_AGENT_BROKER_PROFILE", "tms_oanda_mt5")

    presets = get_symbol_presets("broker")

    assert "DE30.pro" in presets
    assert "US100.pro" in presets


def test_submit_admin_order_requires_confirmation_in_live_mode():
    try:
        submit_admin_order(
            source_mode="demo",
            instrument="DE30.pro",
            side="buy",
            volume=0.10,
            execution_mode="live",
            confirm_live_execution=False,
        )
    except ValueError as exc:
        assert "explicit confirmation" in str(exc)
    else:
        raise AssertionError("submit_admin_order should reject live execution without confirmation")


def test_close_admin_position_returns_paper_close_result():
    result = close_admin_position(
        source_mode="broker",
        instrument="DE30.pro",
        position_id="555001",
        volume=0.20,
        side="long",
        execution_mode="paper",
        confirm_live_execution=False,
    )

    assert result.success is True
    assert result.status_code == "PAPER_CLOSE"
    assert result.side == "sell"