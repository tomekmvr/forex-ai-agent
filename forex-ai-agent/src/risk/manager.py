from __future__ import annotations

from dataclasses import dataclass, field
from math import floor
from typing import Mapping

import structlog


@dataclass(frozen=True)
class RiskLimits:
    daily_drawdown_limit: float = 0.03
    max_fractional_kelly: float = 0.25
    kelly_safety_factor: float = 0.5
    min_volatility_floor: float = 1e-4
    commission_bps: float = 0.5
    slippage_bps: float = 1.0


@dataclass(frozen=True)
class KillSwitchState:
    triggered: bool
    drawdown: float
    remaining_drawdown_buffer: float
    reason: str


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    kill_switch_triggered: bool
    requested_signal: int
    approved_signal: int
    position_units: int
    capital_fraction: float
    risk_budget: float
    expected_transaction_cost: float
    reasoning: str
    diagnostics: Mapping[str, float | int | str] = field(default_factory=dict)


class RiskManager:
    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()
        self.logger = structlog.get_logger(__name__).bind(component="risk_manager")

    def compute_position_size(
        self,
        *,
        equity: float,
        price: float,
        realized_volatility: float,
        capital_fraction: float,
        stop_loss_multiple: float = 1.0,
        contract_multiplier: float = 1.0,
    ) -> tuple[int, float, float]:
        if equity <= 0 or price <= 0 or contract_multiplier <= 0:
            raise ValueError("equity, price and contract_multiplier must be positive.")

        effective_volatility = max(realized_volatility, self.limits.min_volatility_floor)
        risk_budget = equity * max(0.0, capital_fraction)
        stop_distance = price * effective_volatility * stop_loss_multiple
        transaction_cost_per_unit = self._transaction_cost_per_unit(price=price, contract_multiplier=contract_multiplier)
        risk_per_unit = stop_distance * contract_multiplier + transaction_cost_per_unit
        position_units = 0 if risk_per_unit <= 0 else floor(risk_budget / risk_per_unit)
        total_transaction_cost = position_units * transaction_cost_per_unit

        self.logger.info(
            "reasoning_trace",
            step="compute_position_size",
            equity=equity,
            price=price,
            realized_volatility=realized_volatility,
            effective_volatility=effective_volatility,
            capital_fraction=capital_fraction,
            risk_budget=risk_budget,
            position_units=position_units,
            total_transaction_cost=total_transaction_cost,
        )
        return position_units, risk_budget, total_transaction_cost

    def asymmetric_kelly_fraction(
        self,
        *,
        win_probability: float,
        payoff_ratio: float,
        failure_probability: float,
    ) -> float:
        if payoff_ratio <= 0:
            raise ValueError("payoff_ratio must be positive.")
        if not 0 <= win_probability <= 1:
            raise ValueError("win_probability must be in [0, 1].")
        if not 0 <= failure_probability <= 1:
            raise ValueError("failure_probability must be in [0, 1].")

        loss_probability = 1.0 - win_probability
        raw_kelly = win_probability - (loss_probability / payoff_ratio)
        adjusted_fraction = max(0.0, raw_kelly)
        adjusted_fraction *= self.limits.kelly_safety_factor
        adjusted_fraction *= 1.0 - failure_probability
        adjusted_fraction = min(adjusted_fraction, self.limits.max_fractional_kelly)

        self.logger.info(
            "reasoning_trace",
            step="compute_asymmetric_kelly",
            win_probability=win_probability,
            payoff_ratio=payoff_ratio,
            failure_probability=failure_probability,
            raw_kelly=raw_kelly,
            adjusted_fraction=adjusted_fraction,
        )
        return adjusted_fraction

    def evaluate_kill_switch(
        self,
        *,
        session_start_equity: float,
        current_equity: float,
    ) -> KillSwitchState:
        if session_start_equity <= 0 or current_equity < 0:
            raise ValueError("session_start_equity must be positive and current_equity cannot be negative.")

        drawdown = max(0.0, (session_start_equity - current_equity) / session_start_equity)
        triggered = drawdown >= self.limits.daily_drawdown_limit
        remaining_buffer = max(0.0, self.limits.daily_drawdown_limit - drawdown)
        reason = (
            "Daily drawdown limit exceeded. Flatten positions and stop trading."
            if triggered
            else "Daily drawdown within allowed range."
        )

        self.logger.info(
            "reasoning_trace",
            step="evaluate_kill_switch",
            session_start_equity=session_start_equity,
            current_equity=current_equity,
            drawdown=drawdown,
            triggered=triggered,
        )
        return KillSwitchState(
            triggered=triggered,
            drawdown=drawdown,
            remaining_drawdown_buffer=remaining_buffer,
            reason=reason,
        )

    def gate_trade(
        self,
        *,
        requested_signal: int,
        confidence: float,
        equity: float,
        price: float,
        realized_volatility: float,
        win_probability: float,
        payoff_ratio: float,
        failure_probability: float,
        session_start_equity: float,
        current_equity: float,
        stop_loss_multiple: float = 1.0,
        contract_multiplier: float = 1.0,
    ) -> RiskDecision:
        kill_switch = self.evaluate_kill_switch(
            session_start_equity=session_start_equity,
            current_equity=current_equity,
        )
        if kill_switch.triggered:
            return RiskDecision(
                approved=False,
                kill_switch_triggered=True,
                requested_signal=requested_signal,
                approved_signal=0,
                position_units=0,
                capital_fraction=0.0,
                risk_budget=0.0,
                expected_transaction_cost=0.0,
                reasoning=kill_switch.reason,
                diagnostics={
                    "drawdown": kill_switch.drawdown,
                    "daily_drawdown_limit": self.limits.daily_drawdown_limit,
                },
            )

        kelly_fraction = self.asymmetric_kelly_fraction(
            win_probability=win_probability,
            payoff_ratio=payoff_ratio,
            failure_probability=failure_probability,
        )
        capital_fraction = max(0.0, min(1.0, kelly_fraction * max(0.0, confidence)))
        position_units, risk_budget, total_transaction_cost = self.compute_position_size(
            equity=equity,
            price=price,
            realized_volatility=realized_volatility,
            capital_fraction=capital_fraction,
            stop_loss_multiple=stop_loss_multiple,
            contract_multiplier=contract_multiplier,
        )

        approved = requested_signal != 0 and capital_fraction > 0 and position_units > 0
        approved_signal = requested_signal if approved else 0
        reasoning = self._build_reasoning(
            approved=approved,
            requested_signal=requested_signal,
            approved_signal=approved_signal,
            capital_fraction=capital_fraction,
            position_units=position_units,
            total_transaction_cost=total_transaction_cost,
        )

        self.logger.info(
            "reasoning_trace",
            step="gate_trade",
            requested_signal=requested_signal,
            confidence=confidence,
            capital_fraction=capital_fraction,
            position_units=position_units,
            approved=approved,
        )
        return RiskDecision(
            approved=approved,
            kill_switch_triggered=False,
            requested_signal=requested_signal,
            approved_signal=approved_signal,
            position_units=position_units,
            capital_fraction=capital_fraction,
            risk_budget=risk_budget,
            expected_transaction_cost=total_transaction_cost,
            reasoning=reasoning,
            diagnostics={
                "confidence": confidence,
                "kelly_fraction": kelly_fraction,
                "realized_volatility": realized_volatility,
                "drawdown": kill_switch.drawdown,
            },
        )

    def _transaction_cost_per_unit(self, *, price: float, contract_multiplier: float) -> float:
        total_bps = self.limits.commission_bps + self.limits.slippage_bps
        return price * (total_bps / 10_000.0) * contract_multiplier

    @staticmethod
    def _build_reasoning(
        *,
        approved: bool,
        requested_signal: int,
        approved_signal: int,
        capital_fraction: float,
        position_units: int,
        total_transaction_cost: float,
    ) -> str:
        status = "approved" if approved else "rejected"
        return (
            f"Trade {status}. requested_signal={requested_signal}, approved_signal={approved_signal}, "
            f"capital_fraction={capital_fraction:.4f}, position_units={position_units}, "
            f"expected_transaction_cost={total_transaction_cost:.4f}."
        )
