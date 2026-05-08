from __future__ import annotations

import math

import pandas as pd
import structlog

from src.agents.base import AgentContext, AgentSignal, BaseAgent


class TechnicalAgent(BaseAgent):
    def __init__(self, fast_window: int = 10, slow_window: int = 30, weight: float = 1.0) -> None:
        super().__init__(name="technical_agent", weight=weight)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.logger = structlog.get_logger(__name__).bind(component=self.name)

    def isolate_context(self, context: AgentContext) -> AgentContext:
        return context.isolated(
            market_columns=["close", "returns", "realized_volatility"],
            metadata_keys=["instrument", "timestamp"],
        )

    def evaluate(self, context: AgentContext) -> AgentSignal:
        market_features = context.market_features
        if market_features is None or "close" not in market_features.columns:
            raise ValueError("TechnicalAgent requires market_features with a 'close' column.")

        close = market_features["close"].astype(float)
        fast_ma = close.rolling(self.fast_window, min_periods=self.fast_window).mean().iloc[-1]
        slow_ma = close.rolling(self.slow_window, min_periods=self.slow_window).mean().iloc[-1]
        realized_volatility = float(
            market_features.get("realized_volatility", close.pct_change().rolling(20).std()).iloc[-1]
        )

        ma_gap = 0.0 if pd.isna(fast_ma) or pd.isna(slow_ma) else float((fast_ma / slow_ma) - 1.0)
        confidence = min(0.99, abs(ma_gap) * 250)
        if realized_volatility > 0:
            confidence = confidence / (1.0 + realized_volatility * 10)

        signal = 0
        if ma_gap > 0:
            signal = 1
        elif ma_gap < 0:
            signal = -1

        self.logger.info(
            "reasoning_trace",
            step="technical_agent_evaluate",
            ma_gap=ma_gap,
            realized_volatility=realized_volatility,
            signal=signal,
            confidence=confidence,
        )
        return AgentSignal(
            agent_name=self.name,
            signal=signal,
            confidence=max(0.0, min(1.0, confidence)),
            reasoning=(
                f"Fast/slow moving average gap={ma_gap:.5f}, volatility={realized_volatility:.5f}."
            ),
            diagnostics={
                "fast_window": self.fast_window,
                "slow_window": self.slow_window,
                "ma_gap": ma_gap,
            },
        )
