from __future__ import annotations

import numpy as np
import pandas as pd
import structlog

from src.agents.base import AgentContext, AgentSignal, BaseAgent

try:
    from hmmlearn.hmm import GaussianHMM
except ImportError:  # pragma: no cover - optional path
    GaussianHMM = None


class RegimeAgent(BaseAgent):
    def __init__(self, weight: float = 1.2, n_regimes: int = 2) -> None:
        super().__init__(name="regime_agent", weight=weight)
        self.n_regimes = n_regimes
        self.logger = structlog.get_logger(__name__).bind(component=self.name)

    def isolate_context(self, context: AgentContext) -> AgentContext:
        return context.isolated(
            market_columns=["close", "returns", "realized_volatility"],
            metadata_keys=["instrument", "timestamp"],
        )

    def evaluate(self, context: AgentContext) -> AgentSignal:
        market_features = context.market_features
        if market_features is None or "close" not in market_features.columns:
            raise ValueError("RegimeAgent requires market_features with a 'close' column.")

        returns = market_features.get("returns", market_features["close"].pct_change()).dropna().astype(float)
        if len(returns) < 10:
            return AgentSignal(
                agent_name=self.name,
                signal=0,
                confidence=0.0,
                reasoning="Insufficient observations for regime inference.",
                diagnostics={"observation_count": int(len(returns))},
            )

        if GaussianHMM is not None and len(returns) >= 25:
            signal, confidence, reasoning, diagnostics = self._evaluate_with_hmm(returns)
        else:
            signal, confidence, reasoning, diagnostics = self._evaluate_with_heuristic(returns)

        self.logger.info(
            "reasoning_trace",
            step="regime_agent_evaluate",
            signal=signal,
            confidence=confidence,
            **diagnostics,
        )
        return AgentSignal(
            agent_name=self.name,
            signal=signal,
            confidence=confidence,
            reasoning=reasoning,
            diagnostics=diagnostics,
        )

    def _evaluate_with_hmm(self, returns: pd.Series) -> tuple[int, float, str, dict[str, float | str]]:
        model = GaussianHMM(n_components=self.n_regimes, covariance_type="diag", n_iter=200, random_state=7)
        matrix = returns.to_numpy().reshape(-1, 1)
        model.fit(matrix)
        hidden_states = model.predict(matrix)
        state_means = {state: float(returns.to_numpy()[hidden_states == state].mean()) for state in np.unique(hidden_states)}
        state_vols = {
            state: float(returns.to_numpy()[hidden_states == state].std(ddof=0)) for state in np.unique(hidden_states)
        }
        latest_state = int(hidden_states[-1])
        latest_mean = state_means[latest_state]
        latest_vol = max(state_vols[latest_state], 1e-8)
        signal = 0 if abs(latest_mean) < latest_vol * 0.1 else (1 if latest_mean > 0 else -1)
        confidence = min(0.95, abs(latest_mean) / latest_vol)
        reasoning = (
            f"HMM regime {latest_state} mean return={latest_mean:.6f}, volatility={latest_vol:.6f}."
        )
        diagnostics = {
            "method": "hmm",
            "latest_state": latest_state,
            "latest_mean": latest_mean,
            "latest_volatility": latest_vol,
        }
        return signal, confidence, reasoning, diagnostics

    def _evaluate_with_heuristic(self, returns: pd.Series) -> tuple[int, float, str, dict[str, float | str]]:
        recent_window = returns.tail(20)
        mean_return = float(recent_window.mean())
        volatility = float(recent_window.std(ddof=0))
        signal = 0 if abs(mean_return) < max(volatility * 0.15, 1e-5) else (1 if mean_return > 0 else -1)
        confidence = min(0.9, abs(mean_return) / max(volatility, 1e-8))
        reasoning = (
            f"Heuristic regime mean return={mean_return:.6f}, volatility={volatility:.6f}."
        )
        diagnostics = {
            "method": "heuristic",
            "latest_mean": mean_return,
            "latest_volatility": volatility,
        }
        return signal, confidence, reasoning, diagnostics
