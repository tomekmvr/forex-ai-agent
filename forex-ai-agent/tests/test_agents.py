from __future__ import annotations

import pandas as pd

from src.agents.base import AgentContext, AgentSignal, BaseAgent
from src.agents.orchestrator import Orchestrator
from src.agents.regime_agent import RegimeAgent
from src.agents.sentiment_agent import SentimentAgent
from src.agents.supervisor_agent import SupervisorAgent
from src.agents.technical_agent import TechnicalAgent
from src.ai.openai_client import SupervisorAssessment


class FakeSupervisorClient:
    def assess(self, *, prompt: str) -> SupervisorAssessment:
        assert "market_tail=" in prompt
        return SupervisorAssessment(
            signal=1,
            confidence=0.61,
            reasoning="Supervisor confirms bullish consensus.",
            diagnostics={"source": "fake-openai"},
        )


class SpyAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="spy_agent", weight=1.0)
        self.last_context: AgentContext | None = None

    def isolate_context(self, context: AgentContext) -> AgentContext:
        return context.isolated(market_columns=["close"], metadata_keys=["instrument"])

    def evaluate(self, context: AgentContext) -> AgentSignal:
        self.last_context = context
        return AgentSignal(
            agent_name=self.name,
            signal=1,
            confidence=0.8,
            reasoning="Spy agent confirmed isolated context.",
            diagnostics={},
        )


def test_agent_context_isolation_hides_unneeded_columns_and_metadata():
    spy_agent = SpyAgent()
    context = AgentContext(
        market_features=pd.DataFrame(
            {
                "close": [1.10, 1.11, 1.12],
                "returns": [0.01, 0.01, 0.01],
                "secret_feature": [99, 98, 97],
            }
        ),
        metadata={"instrument": "EUR_USD", "api_token": "top-secret"},
    )

    spy_agent.decide(context)

    assert spy_agent.last_context is not None
    assert list(spy_agent.last_context.market_features.columns) == ["close"]
    assert spy_agent.last_context.metadata == {"instrument": "EUR_USD"}


def test_orchestrator_combines_hub_and_spoke_agent_signals():
    index = pd.date_range("2026-01-01", periods=40, freq="h")
    close = pd.Series([1.1000 + 0.0007 * step for step in range(40)], index=index)
    market_features = pd.DataFrame(
        {
            "close": close,
            "returns": close.pct_change().fillna(0.0),
            "realized_volatility": close.pct_change().rolling(5).std().fillna(0.0015),
            "unused_internal_feature": range(40),
        },
        index=index,
    )
    news_features = pd.DataFrame(
        {
            "sentiment_score": [0.8, 0.4],
            "relevance": [1.0, 0.6],
            "hours_since_release": [1.0, 2.0],
            "internal_news_note": [10, 20],
        }
    )
    calendar_features = pd.DataFrame(
        {
            "impact_weight": [0.1, 0.2],
            "hours_to_event": [10.0, 12.0],
            "hidden_calendar_state": [1, 1],
        }
    )
    context = AgentContext(
        market_features=market_features,
        news_features=news_features,
        calendar_features=calendar_features,
        metadata={"instrument": "EUR_USD", "timestamp": str(index[-1]), "secret": "hidden"},
    )

    orchestrator = Orchestrator(
        agents=[TechnicalAgent(), SentimentAgent(), RegimeAgent()],
        decision_threshold=0.10,
    )

    decision = orchestrator.decide(context)

    assert decision.approved is True
    assert decision.final_signal == 1
    assert len(decision.agent_signals) == 3
    assert {signal.agent_name for signal in decision.agent_signals} == {
        "technical_agent",
        "sentiment_agent",
        "regime_agent",
    }
    assert "Weighted score=" in decision.reasoning


def test_supervisor_agent_returns_structured_signal_from_client():
    index = pd.date_range("2026-01-01", periods=15, freq="h")
    context = AgentContext(
        market_features=pd.DataFrame(
            {
                "close": [1.10 + 0.0002 * step for step in range(15)],
                "returns": [0.0] + [0.0002 for _ in range(14)],
                "realized_volatility": [0.0015 for _ in range(15)],
            },
            index=index,
        ),
        news_features=pd.DataFrame(
            {
                "headline": ["ECB comments lean hawkish"],
                "sentiment_score": [0.55],
                "relevance": [1.0],
                "hours_since_release": [1.0],
            }
        ),
        calendar_features=pd.DataFrame(
            {"event": ["US CPI"], "impact_weight": [0.4], "hours_to_event": [5.0]}
        ),
        metadata={"instrument": "EUR_USD", "timestamp": str(index[-1])},
    )

    signal = SupervisorAgent(FakeSupervisorClient()).decide(context).signal

    assert signal.agent_name == "supervisor_agent"
    assert signal.signal == 1
    assert signal.confidence == 0.61


class FixedSignalAgent(BaseAgent):
    def __init__(self, name: str, signal: int, confidence: float, weight: float = 1.0) -> None:
        super().__init__(name=name, weight=weight)
        self._signal = signal
        self._confidence = confidence

    def isolate_context(self, context: AgentContext) -> AgentContext:
        return context

    def evaluate(self, context: AgentContext) -> AgentSignal:
        return AgentSignal(
            agent_name=self.name,
            signal=self._signal,
            confidence=self._confidence,
            reasoning=f"{self.name} fixed signal.",
            diagnostics={},
        )


def test_orchestrator_blocks_trade_when_supervisor_disagrees():
    orchestrator = Orchestrator(
        agents=[
            FixedSignalAgent("technical_agent", 1, 0.8),
            FixedSignalAgent("sentiment_agent", 1, 0.7),
            FixedSignalAgent("regime_agent", 1, 0.6),
            FixedSignalAgent("supervisor_agent", -1, 0.9),
        ],
        decision_threshold=0.10,
        require_supervisor_confirmation=True,
    )

    decision = orchestrator.decide(AgentContext())

    assert decision.final_signal == 0
    assert decision.approved is False
    assert "Supervisor gate blocked trade due to directional disagreement." in decision.reasoning


def test_orchestrator_confirms_trade_when_supervisor_aligns():
    orchestrator = Orchestrator(
        agents=[
            FixedSignalAgent("technical_agent", 1, 0.8),
            FixedSignalAgent("sentiment_agent", 1, 0.7),
            FixedSignalAgent("regime_agent", 1, 0.6),
            FixedSignalAgent("supervisor_agent", 1, 0.55),
        ],
        decision_threshold=0.10,
        require_supervisor_confirmation=True,
    )

    decision = orchestrator.decide(AgentContext())

    assert decision.final_signal == 1
    assert decision.approved is True
    assert decision.confidence == 0.55
    assert "Supervisor gate confirmed final signal." in decision.reasoning