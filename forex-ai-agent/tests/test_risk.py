from src.risk.manager import RiskLimits, RiskManager


def test_volatility_scaled_position_size_shrinks_as_volatility_rises():
    manager = RiskManager(RiskLimits(commission_bps=0.0, slippage_bps=0.0))

    low_vol_units, _, _ = manager.compute_position_size(
        equity=100_000,
        price=1.10,
        realized_volatility=0.004,
        capital_fraction=0.01,
    )
    high_vol_units, _, _ = manager.compute_position_size(
        equity=100_000,
        price=1.10,
        realized_volatility=0.020,
        capital_fraction=0.01,
    )

    assert low_vol_units > high_vol_units


def test_asymmetric_kelly_fraction_is_capped_and_penalized_by_failure_probability():
    manager = RiskManager(RiskLimits(max_fractional_kelly=0.20, kelly_safety_factor=0.5))

    safer_fraction = manager.asymmetric_kelly_fraction(
        win_probability=0.58,
        payoff_ratio=1.8,
        failure_probability=0.05,
    )
    stressed_fraction = manager.asymmetric_kelly_fraction(
        win_probability=0.58,
        payoff_ratio=1.8,
        failure_probability=0.40,
    )

    assert 0.0 < safer_fraction <= 0.20
    assert stressed_fraction < safer_fraction


def test_kill_switch_triggers_when_daily_drawdown_limit_is_breached():
    manager = RiskManager(RiskLimits(daily_drawdown_limit=0.03))

    state = manager.evaluate_kill_switch(session_start_equity=100_000, current_equity=96_500)

    assert state.triggered is True
    assert state.drawdown == 0.035
    assert "Flatten positions" in state.reason


def test_gate_trade_rejects_signals_when_kill_switch_is_active():
    manager = RiskManager(RiskLimits(daily_drawdown_limit=0.02))

    decision = manager.gate_trade(
        requested_signal=1,
        confidence=0.8,
        equity=100_000,
        price=1.10,
        realized_volatility=0.006,
        win_probability=0.58,
        payoff_ratio=1.6,
        failure_probability=0.08,
        session_start_equity=100_000,
        current_equity=97_500,
    )

    assert decision.approved is False
    assert decision.kill_switch_triggered is True
    assert decision.position_units == 0
    assert decision.approved_signal == 0


def test_gate_trade_approves_signal_with_safe_size_and_costs():
    manager = RiskManager(
        RiskLimits(
            daily_drawdown_limit=0.05,
            max_fractional_kelly=0.25,
            kelly_safety_factor=0.5,
            commission_bps=0.5,
            slippage_bps=1.0,
        )
    )

    decision = manager.gate_trade(
        requested_signal=1,
        confidence=0.75,
        equity=100_000,
        price=1.10,
        realized_volatility=0.005,
        win_probability=0.60,
        payoff_ratio=1.8,
        failure_probability=0.05,
        session_start_equity=100_000,
        current_equity=99_200,
    )

    assert decision.approved is True
    assert decision.kill_switch_triggered is False
    assert decision.position_units > 0
    assert decision.capital_fraction > 0
    assert decision.expected_transaction_cost > 0