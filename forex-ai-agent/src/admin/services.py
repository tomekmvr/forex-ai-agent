from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.agents.base import AgentContext
from src.agents.orchestrator import Orchestrator, OrchestratorDecision
from src.agents.regime_agent import RegimeAgent
from src.agents.sentiment_agent import SentimentAgent
from src.agents.supervisor_agent import SupervisorAgent
from src.agents.technical_agent import TechnicalAgent
from src.ai.openai_client import OpenAISupervisorClient
from src.config.ai_settings import AISettings
from src.config.settings import ExecutionSettings
from src.execution.adapters import (
    BrokerAdminAdapter,
    BrokerDataSnapshot,
    DemoBrokerAdapter,
    OandaBrokerAdapter,
    build_mt5_admin_adapter,
)
from src.execution.base import AccountSnapshot, TradeExecutionResult, TradeOrderRequest
from src.risk.manager import KillSwitchState, RiskDecision, RiskLimits, RiskManager


@dataclass(frozen=True)
class AdminPanelSnapshot:
    source_name: str
    status_message: str
    live_connected: bool
    market_features: pd.DataFrame
    news_features: pd.DataFrame
    calendar_features: pd.DataFrame
    account_snapshot: AccountSnapshot
    positions: pd.DataFrame
    trade_history: pd.DataFrame
    kill_switch_state: KillSwitchState
    orchestrator_decision: OrchestratorDecision
    risk_decision: RiskDecision


MT5_SYMBOL_PRESETS = ("DE30.pro", "US100.pro", "GER40.pro", "XAUUSD", "EURUSD", "GBPUSD")
OANDA_SYMBOL_PRESETS = ("EUR_USD", "GBP_USD", "USD_JPY", "XAU_USD")


def build_agent_stack() -> list:
    agents = [TechnicalAgent(), SentimentAgent(), RegimeAgent()]
    ai_settings = AISettings.from_env()
    if ai_settings.enabled:
        agents.append(SupervisorAgent(OpenAISupervisorClient(ai_settings)))
    return agents


def _resolve_risk_inputs(
    *,
    snapshot: BrokerDataSnapshot,
    equity: float,
    session_start_equity: float,
    current_equity: float,
) -> tuple[float, float, float]:
    if not snapshot.live_connected:
        return equity, session_start_equity, current_equity

    broker_equity = float(snapshot.account_snapshot.equity)
    resolved_session_start = max(float(session_start_equity), broker_equity)
    return broker_equity, resolved_session_start, broker_equity


def build_market_features(price_frame: pd.DataFrame) -> pd.DataFrame:
    if "close" not in price_frame.columns:
        raise ValueError("price_frame must contain a 'close' column.")

    market_features = price_frame.copy()
    market_features["close"] = market_features["close"].astype(float)
    market_features["returns"] = market_features["close"].pct_change().fillna(0.0)
    market_features["realized_volatility"] = (
        market_features["returns"].rolling(20).std().fillna(market_features["returns"].std(ddof=0))
    )
    market_features["realized_volatility"] = market_features["realized_volatility"].fillna(0.001)
    return market_features


def build_default_news_features() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "headline": ["ECB tone supportive for EUR", "US data mixed before session"],
            "sentiment_score": [0.65, 0.15],
            "relevance": [1.0, 0.7],
            "hours_since_release": [1.0, 4.0],
        }
    )


def build_default_calendar_features() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "event": ["ECB Speaker", "US CPI"],
            "impact_weight": [0.15, 0.35],
            "hours_to_event": [12.0, 18.0],
        }
    )


def _resolve_agent_side_inputs(
    *,
    snapshot: BrokerDataSnapshot,
    news_features: pd.DataFrame | None,
    calendar_features: pd.DataFrame | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if news_features is not None:
        news_frame = news_features.copy()
    elif snapshot.live_connected:
        news_frame = pd.DataFrame(columns=["headline", "sentiment_score", "relevance", "hours_since_release"])
    else:
        news_frame = build_default_news_features()

    if calendar_features is not None:
        calendar_frame = calendar_features.copy()
    elif snapshot.live_connected:
        calendar_frame = pd.DataFrame(columns=["event", "impact_weight", "hours_to_event"])
    else:
        calendar_frame = build_default_calendar_features()

    return news_frame, calendar_frame


def build_admin_adapter(source_mode: str) -> BrokerAdminAdapter:
    normalized_source = source_mode.lower()
    if normalized_source == "demo":
        return DemoBrokerAdapter()

    settings = ExecutionSettings.from_env()
    if settings.broker_name.startswith("oanda"):
        return OandaBrokerAdapter(settings)
    if settings.broker_name == "tms_oanda_mt5":
        return build_mt5_admin_adapter(settings)

    if normalized_source == "broker":
        raise ValueError(
            f"Broker profile '{settings.broker_name}' is not supported by the admin adapter yet."
        )
    return DemoBrokerAdapter()


def get_symbol_presets(source_mode: str) -> tuple[str, ...]:
    if source_mode == "demo":
        return OANDA_SYMBOL_PRESETS

    try:
        settings = ExecutionSettings.from_env()
    except Exception:
        return OANDA_SYMBOL_PRESETS

    if settings.is_mt5_profile:
        return MT5_SYMBOL_PRESETS
    if settings.broker_name.startswith("oanda"):
        return OANDA_SYMBOL_PRESETS
    return OANDA_SYMBOL_PRESETS


def submit_admin_order(
    *,
    source_mode: str,
    instrument: str,
    side: str,
    volume: float,
    execution_mode: str = "paper",
    confirm_live_execution: bool = False,
    comment: str = "Forex AI Agent Admin",
) -> TradeExecutionResult:
    if execution_mode not in {"paper", "live"}:
        raise ValueError("execution_mode must be either 'paper' or 'live'.")
    if execution_mode == "live" and not confirm_live_execution:
        raise ValueError("Live execution requires explicit confirmation.")

    if execution_mode == "paper":
        return TradeExecutionResult(
            success=True,
            broker="paper",
            instrument=instrument,
            side=side,
            requested_volume=volume,
            filled_volume=volume,
            executed_price=0.0,
            broker_order_id="paper-order",
            status_code="PAPER",
            message="Paper mode enabled. No live order was sent.",
            request_payload={
                "instrument": instrument,
                "side": side,
                "volume": volume,
                "comment": comment,
            },
        )

    normalized_source = "broker" if source_mode == "auto" else source_mode
    adapter = build_admin_adapter(normalized_source)
    order = TradeOrderRequest(
        instrument=instrument,
        side=side,
        volume=volume,
        comment=comment,
    )
    return adapter.submit_market_order(order)


def close_admin_position(
    *,
    source_mode: str,
    instrument: str,
    position_id: str,
    volume: float,
    side: str,
    execution_mode: str = "paper",
    confirm_live_execution: bool = False,
    comment: str = "Forex AI Agent Admin close",
) -> TradeExecutionResult:
    if execution_mode not in {"paper", "live"}:
        raise ValueError("execution_mode must be either 'paper' or 'live'.")
    if execution_mode == "live" and not confirm_live_execution:
        raise ValueError("Live execution requires explicit confirmation.")

    if execution_mode == "paper":
        return TradeExecutionResult(
            success=True,
            broker="paper",
            instrument=instrument,
            side="sell" if side.lower() == "long" else "buy",
            requested_volume=volume,
            filled_volume=volume,
            executed_price=0.0,
            broker_order_id=position_id,
            status_code="PAPER_CLOSE",
            message="Paper mode enabled. No live close order was sent.",
            request_payload={
                "instrument": instrument,
                "position_id": position_id,
                "volume": volume,
                "side": side,
                "comment": comment,
            },
        )

    normalized_source = "broker" if source_mode == "auto" else source_mode
    adapter = build_admin_adapter(normalized_source)
    return adapter.close_position(
        instrument=instrument,
        position_id=position_id,
        volume=volume,
        side=side,
        comment=comment,
    )


def load_market_snapshot(
    *,
    source_mode: str,
    instrument: str,
    granularity: str,
    periods: int,
) -> BrokerDataSnapshot:
    if source_mode == "auto":
        try:
            adapter = build_admin_adapter("broker")
            return adapter.load_snapshot(instrument=instrument, granularity=granularity, count=periods)
        except Exception as exc:
            demo_snapshot = DemoBrokerAdapter().load_snapshot(
                instrument=instrument,
                granularity=granularity,
                count=periods,
            )
            return BrokerDataSnapshot(
                source_name=demo_snapshot.source_name,
                status_message=f"Broker data unavailable, fallback to demo: {exc}",
                live_connected=False,
                market_prices=demo_snapshot.market_prices,
                account_snapshot=demo_snapshot.account_snapshot,
                positions=demo_snapshot.positions,
                trade_history=demo_snapshot.trade_history,
            )

    adapter = build_admin_adapter(source_mode)
    return adapter.load_snapshot(instrument=instrument, granularity=granularity, count=periods)


def run_admin_snapshot(
    *,
    price_frame: pd.DataFrame | None = None,
    equity: float,
    session_start_equity: float,
    current_equity: float,
    instrument: str = "EUR_USD",
    granularity: str = "H1",
    periods: int = 120,
    source_mode: str = "demo",
    win_probability: float = 0.57,
    payoff_ratio: float = 1.8,
    failure_probability: float = 0.08,
    decision_threshold: float = 0.15,
    risk_limits: RiskLimits | None = None,
    news_features: pd.DataFrame | None = None,
    calendar_features: pd.DataFrame | None = None,
    broker_snapshot: BrokerDataSnapshot | None = None,
) -> AdminPanelSnapshot:
    resolved_snapshot = broker_snapshot
    if resolved_snapshot is None:
        if price_frame is not None:
            resolved_snapshot = BrokerDataSnapshot(
                source_name="custom",
                status_message="Custom price frame supplied directly to admin service.",
                live_connected=False,
                market_prices=price_frame.copy(),
                account_snapshot=AccountSnapshot(
                    broker="custom",
                    account_id="custom-account",
                    balance=session_start_equity,
                    equity=current_equity,
                    unrealized_pnl=current_equity - equity,
                    realized_pnl=0.0,
                    margin_used=0.0,
                    margin_available=current_equity,
                ),
                positions=tuple(),
            )
        else:
            resolved_snapshot = load_market_snapshot(
                source_mode=source_mode,
                instrument=instrument,
                granularity=granularity,
                periods=periods,
            )

    market_features = build_market_features(resolved_snapshot.market_prices)
    news_frame, calendar_frame = _resolve_agent_side_inputs(
        snapshot=resolved_snapshot,
        news_features=news_features,
        calendar_features=calendar_features,
    )

    context = AgentContext(
        market_features=market_features,
        news_features=news_frame,
        calendar_features=calendar_frame,
        metadata={
            "instrument": instrument,
            "timestamp": str(market_features.index[-1]),
        },
    )

    ai_settings = AISettings.from_env()
    orchestrator = Orchestrator(
        agents=build_agent_stack(),
        decision_threshold=decision_threshold,
        require_supervisor_confirmation=ai_settings.enabled and ai_settings.decision_mode == "supervisor",
    )
    orchestrator_decision = orchestrator.decide(context)

    resolved_equity, resolved_session_start_equity, resolved_current_equity = _resolve_risk_inputs(
        snapshot=resolved_snapshot,
        equity=equity,
        session_start_equity=session_start_equity,
        current_equity=current_equity,
    )

    latest_price = float(market_features["close"].iloc[-1])
    latest_volatility = float(market_features["realized_volatility"].iloc[-1])
    risk_manager = RiskManager(risk_limits)
    kill_switch_state = risk_manager.evaluate_kill_switch(
        session_start_equity=resolved_session_start_equity,
        current_equity=resolved_current_equity,
    )
    risk_decision = risk_manager.gate_trade(
        requested_signal=orchestrator_decision.final_signal,
        confidence=orchestrator_decision.confidence,
        equity=resolved_equity,
        price=latest_price,
        realized_volatility=latest_volatility,
        win_probability=win_probability,
        payoff_ratio=payoff_ratio,
        failure_probability=failure_probability,
        session_start_equity=resolved_session_start_equity,
        current_equity=resolved_current_equity,
    )

    return AdminPanelSnapshot(
        source_name=resolved_snapshot.source_name,
        status_message=resolved_snapshot.status_message,
        live_connected=resolved_snapshot.live_connected,
        market_features=market_features,
        news_features=news_frame,
        calendar_features=calendar_frame,
        account_snapshot=resolved_snapshot.account_snapshot,
        positions=pd.DataFrame([position.to_record() for position in resolved_snapshot.positions]),
        trade_history=pd.DataFrame([deal.to_record() for deal in resolved_snapshot.trade_history]),
        kill_switch_state=kill_switch_state,
        orchestrator_decision=orchestrator_decision,
        risk_decision=risk_decision,
    )
