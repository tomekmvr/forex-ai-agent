"""Execution layer for historical market data and live broker connectivity."""

from .adapters import (
	BrokerAdminAdapter,
	BrokerDataSnapshot,
	DemoBrokerAdapter,
	Mt5BrokerAdapter,
	Mt5RelayBrokerAdapter,
	OandaBrokerAdapter,
	build_mt5_admin_adapter,
)
from .base import (
	AccountSnapshot,
	Candle,
	MarketEvent,
	PositionSnapshot,
	TradeExecutionResult,
	TradeHistoryRecord,
	TradeOrderRequest,
)
from .gateway import MarketGateway

__all__ = [
	"AccountSnapshot",
	"BrokerAdminAdapter",
	"BrokerDataSnapshot",
	"Candle",
	"DemoBrokerAdapter",
	"MarketEvent",
	"MarketGateway",
	"Mt5BrokerAdapter",
	"Mt5RelayBrokerAdapter",
	"OandaBrokerAdapter",
	"PositionSnapshot",
	"TradeExecutionResult",
	"TradeHistoryRecord",
	"TradeOrderRequest",
	"build_mt5_admin_adapter",
]
