from __future__ import annotations

from typing import Optional

import pandas as pd
import structlog

from src.agents.base import AgentContext, AgentSignal, BaseAgent
from src.ai.openai_client import OpenAISupervisorClient


class SupervisorAgent(BaseAgent):
    def __init__(self, client: OpenAISupervisorClient, weight: float = 1.1) -> None:
        super().__init__(name="supervisor_agent", weight=weight)
        self.client = client
        self.logger = structlog.get_logger(__name__).bind(component=self.name)

    def isolate_context(self, context: AgentContext) -> AgentContext:
        return context.isolated(
            market_columns=["close", "returns", "realized_volatility"],
            news_columns=["headline", "sentiment_score", "relevance", "hours_since_release"],
            calendar_columns=["event", "impact_weight", "hours_to_event"],
            metadata_keys=["instrument", "timestamp"],
        )

    def evaluate(self, context: AgentContext) -> AgentSignal:
        prompt = self._build_prompt(context)
        assessment = self.client.assess(prompt=prompt)
        self.logger.info(
            "reasoning_trace",
            step="supervisor_agent_evaluate",
            signal=assessment.signal,
            confidence=assessment.confidence,
        )
        return AgentSignal(
            agent_name=self.name,
            signal=assessment.signal,
            confidence=assessment.confidence,
            reasoning=assessment.reasoning,
            diagnostics=assessment.diagnostics,
        )

    @staticmethod
    def _build_prompt(context: AgentContext) -> str:
        market_frame = context.market_features if context.market_features is not None else pd.DataFrame()
        news_frame = context.news_features if context.news_features is not None else pd.DataFrame()
        calendar_frame = context.calendar_features if context.calendar_features is not None else pd.DataFrame()

        market_tail = market_frame.tail(10).to_dict(orient="records") if not market_frame.empty else []
        news_rows = news_frame.head(5).to_dict(orient="records") if not news_frame.empty else []
        calendar_rows = calendar_frame.head(5).to_dict(orient="records") if not calendar_frame.empty else []

        return (
            "You are a forex trading supervisor. Review the latest structured market, news, and calendar context. "
            "Return only JSON with fields signal (-1,0,1), confidence (0..1), reasoning, diagnostics. "
            "Be conservative around missing or contradictory evidence.\n"
            f"metadata={dict(context.metadata)}\n"
            f"market_tail={market_tail}\n"
            f"news_rows={news_rows}\n"
            f"calendar_rows={calendar_rows}"
        )