from __future__ import annotations

import pandas as pd
import structlog

from src.agents.base import AgentContext, AgentSignal, BaseAgent


class SentimentAgent(BaseAgent):
    def __init__(self, weight: float = 0.8) -> None:
        super().__init__(name="sentiment_agent", weight=weight)
        self.logger = structlog.get_logger(__name__).bind(component=self.name)

    def isolate_context(self, context: AgentContext) -> AgentContext:
        return context.isolated(
            news_columns=["sentiment_score", "relevance", "hours_since_release"],
            calendar_columns=["impact_weight", "hours_to_event"],
            metadata_keys=["instrument", "timestamp"],
        )

    def evaluate(self, context: AgentContext) -> AgentSignal:
        news_features = context.news_features
        calendar_features = context.calendar_features

        if news_features is None or news_features.empty:
            return AgentSignal(
                agent_name=self.name,
                signal=0,
                confidence=0.0,
                reasoning="No news features available.",
                diagnostics={"news_count": 0},
            )

        sentiment_score = news_features["sentiment_score"].astype(float)
        relevance = news_features.get("relevance", pd.Series(1.0, index=news_features.index)).astype(float)
        freshness = news_features.get(
            "hours_since_release",
            pd.Series(0.0, index=news_features.index),
        ).astype(float)

        freshness_weight = 1.0 / (1.0 + freshness.clip(lower=0.0))
        weighted_sentiment = float((sentiment_score * relevance * freshness_weight).sum() / max(relevance.sum(), 1e-9))

        event_risk_penalty = 0.0
        if calendar_features is not None and not calendar_features.empty:
            imminent_events = calendar_features[calendar_features["hours_to_event"].astype(float) <= 4.0]
            if not imminent_events.empty:
                event_risk_penalty = float(imminent_events["impact_weight"].astype(float).mean())

        adjusted_score = weighted_sentiment * (1.0 - min(0.8, event_risk_penalty))
        confidence = min(0.95, abs(adjusted_score))
        signal = 0 if abs(adjusted_score) < 0.05 else (1 if adjusted_score > 0 else -1)

        self.logger.info(
            "reasoning_trace",
            step="sentiment_agent_evaluate",
            weighted_sentiment=weighted_sentiment,
            event_risk_penalty=event_risk_penalty,
            adjusted_score=adjusted_score,
            signal=signal,
            confidence=confidence,
        )
        return AgentSignal(
            agent_name=self.name,
            signal=signal,
            confidence=confidence,
            reasoning=(
                f"Weighted sentiment={weighted_sentiment:.4f}, adjusted by calendar risk to {adjusted_score:.4f}."
            ),
            diagnostics={
                "news_count": int(len(news_features)),
                "event_risk_penalty": event_risk_penalty,
            },
        )
