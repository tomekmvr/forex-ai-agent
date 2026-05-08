from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import structlog

from src.agents.base import AgentContext, AgentSignal, BaseAgent


@dataclass(frozen=True)
class OrchestratorDecision:
    final_signal: int
    confidence: float
    weighted_score: float
    approved: bool
    agent_signals: tuple[AgentSignal, ...]
    reasoning: str


class Orchestrator:
    def __init__(self, agents: Sequence[BaseAgent], decision_threshold: float = 0.15) -> None:
        if not agents:
            raise ValueError("Orchestrator requires at least one agent.")
        self.agents = tuple(agents)
        self.decision_threshold = decision_threshold
        self.logger = structlog.get_logger(__name__).bind(component="orchestrator")

    def decide(self, context: AgentContext) -> OrchestratorDecision:
        agent_signals = []
        weighted_signal_sum = 0.0
        weight_sum = 0.0

        for agent in self.agents:
            decision = agent.decide(context)
            agent_signals.append(decision.signal)
            contribution = decision.signal.signal * decision.signal.confidence * agent.weight
            weighted_signal_sum += contribution
            weight_sum += agent.weight

        weighted_score = 0.0 if weight_sum == 0 else weighted_signal_sum / weight_sum
        confidence = min(0.99, abs(weighted_score))
        final_signal = 0 if abs(weighted_score) < self.decision_threshold else (1 if weighted_score > 0 else -1)
        approved = final_signal != 0
        reasoning = self._format_reasoning(weighted_score, agent_signals)

        self.logger.info(
            "reasoning_trace",
            step="orchestrator_decide",
            weighted_score=weighted_score,
            confidence=confidence,
            final_signal=final_signal,
            approved=approved,
        )
        return OrchestratorDecision(
            final_signal=final_signal,
            confidence=confidence,
            weighted_score=weighted_score,
            approved=approved,
            agent_signals=tuple(agent_signals),
            reasoning=reasoning,
        )

    @staticmethod
    def _format_reasoning(weighted_score: float, agent_signals: Sequence[AgentSignal]) -> str:
        signal_summaries = ", ".join(
            f"{signal.agent_name}: signal={signal.signal}, confidence={signal.confidence:.2f}"
            for signal in agent_signals
        )
        return f"Weighted score={weighted_score:.4f}. Agent breakdown: {signal_summaries}."
