from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

import pandas as pd


@dataclass(frozen=True)
class AgentContext:
    market_features: Optional[pd.DataFrame] = None
    news_features: Optional[pd.DataFrame] = None
    calendar_features: Optional[pd.DataFrame] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def isolated(
        self,
        *,
        market_columns: Optional[list[str]] = None,
        news_columns: Optional[list[str]] = None,
        calendar_columns: Optional[list[str]] = None,
        metadata_keys: Optional[list[str]] = None,
    ) -> "AgentContext":
        return AgentContext(
            market_features=self._select_columns(self.market_features, market_columns),
            news_features=self._select_columns(self.news_features, news_columns),
            calendar_features=self._select_columns(self.calendar_features, calendar_columns),
            metadata=self._select_metadata(metadata_keys),
        )

    def _select_columns(
        self,
        frame: Optional[pd.DataFrame],
        columns: Optional[list[str]],
    ) -> Optional[pd.DataFrame]:
        if frame is None:
            return None
        if columns is None:
            return frame.copy()
        available_columns = [column for column in columns if column in frame.columns]
        return frame.loc[:, available_columns].copy()

    def _select_metadata(self, metadata_keys: Optional[list[str]]) -> Mapping[str, Any]:
        if metadata_keys is None:
            return dict(self.metadata)
        return {key: self.metadata[key] for key in metadata_keys if key in self.metadata}


@dataclass(frozen=True)
class AgentSignal:
    agent_name: str
    signal: int
    confidence: float
    reasoning: str
    diagnostics: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentDecision:
    signal: AgentSignal
    context: AgentContext


class BaseAgent(ABC):
    name: str
    weight: float

    def __init__(self, name: str, weight: float = 1.0) -> None:
        self.name = name
        self.weight = weight

    @abstractmethod
    def isolate_context(self, context: AgentContext) -> AgentContext:
        raise NotImplementedError

    @abstractmethod
    def evaluate(self, context: AgentContext) -> AgentSignal:
        raise NotImplementedError

    def decide(self, context: AgentContext) -> AgentDecision:
        isolated_context = self.isolate_context(context)
        signal = self.evaluate(isolated_context)
        return AgentDecision(signal=signal, context=isolated_context)
