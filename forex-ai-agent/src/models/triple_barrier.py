from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import structlog


@dataclass(frozen=True)
class TripleBarrierConfig:
    profit_taking_multiple: float = 2.0
    stop_loss_multiple: float = 1.0
    vertical_barrier_bars: int = 20
    volatility_lookback: int = 50
    min_target_return: float = 1e-4


class TripleBarrierLabeler:
    """Generate event labels using profit-taking, stop-loss and time barriers."""

    def __init__(self, config: Optional[TripleBarrierConfig] = None) -> None:
        self.config = config or TripleBarrierConfig()
        self.logger = structlog.get_logger(__name__).bind(component="triple_barrier_labeler")

    def estimate_volatility(self, prices: pd.Series) -> pd.Series:
        clean_prices = self._validate_prices(prices)
        returns = clean_prices.pct_change()
        volatility = returns.ewm(span=self.config.volatility_lookback, min_periods=3).std()
        return volatility.rename("volatility")

    def label_events(
        self,
        prices: pd.Series,
        sides: Optional[pd.Series] = None,
        volatility: Optional[pd.Series] = None,
    ) -> pd.DataFrame:
        clean_prices = self._validate_prices(prices)
        side_series = self._validate_sides(clean_prices, sides)
        volatility_series = (volatility if volatility is not None else self.estimate_volatility(clean_prices))
        volatility_series = volatility_series.reindex(clean_prices.index).astype(float)

        self.logger.info(
            "reasoning_trace",
            step="generate_triple_barrier_labels",
            observation_count=len(clean_prices),
            vertical_barrier_bars=self.config.vertical_barrier_bars,
            profit_taking_multiple=self.config.profit_taking_multiple,
            stop_loss_multiple=self.config.stop_loss_multiple,
        )

        records = []
        max_start = len(clean_prices) - self.config.vertical_barrier_bars - 1
        if max_start < 0:
            return pd.DataFrame()

        for position in range(max_start + 1):
            event_time = clean_prices.index[position]
            side = int(np.sign(side_series.iloc[position]))
            target = float(volatility_series.iloc[position])

            if side == 0 or np.isnan(target) or target < self.config.min_target_return:
                continue

            entry_price = float(clean_prices.iloc[position])
            expiry_position = position + self.config.vertical_barrier_bars
            expiry_time = clean_prices.index[expiry_position]
            future_path = clean_prices.iloc[position + 1 : expiry_position + 1]
            signed_returns = ((future_path / entry_price) - 1.0) * side

            profit_taking = self.config.profit_taking_multiple * target
            stop_loss = self.config.stop_loss_multiple * target
            take_profit_hits = signed_returns[signed_returns >= profit_taking]
            stop_loss_hits = signed_returns[signed_returns <= -stop_loss]

            exit_time = expiry_time
            label = 0

            if not take_profit_hits.empty and not stop_loss_hits.empty:
                if take_profit_hits.index[0] <= stop_loss_hits.index[0]:
                    exit_time = take_profit_hits.index[0]
                    label = 1
                else:
                    exit_time = stop_loss_hits.index[0]
                    label = -1
            elif not take_profit_hits.empty:
                exit_time = take_profit_hits.index[0]
                label = 1
            elif not stop_loss_hits.empty:
                exit_time = stop_loss_hits.index[0]
                label = -1

            exit_price = float(clean_prices.loc[exit_time])
            realized_return = ((exit_price / entry_price) - 1.0) * side
            upper_barrier, lower_barrier = self._price_barriers(
                entry_price=entry_price,
                side=side,
                target=target,
            )

            records.append(
                {
                    "event_time": event_time,
                    "expiry_time": expiry_time,
                    "exit_time": exit_time,
                    "entry_price": entry_price,
                    "upper_barrier": upper_barrier,
                    "lower_barrier": lower_barrier,
                    "target_volatility": target,
                    "side": side,
                    "label": label,
                    "realized_return": realized_return,
                    "meta_label": int(realized_return > 0),
                }
            )

        if not records:
            return pd.DataFrame()

        return pd.DataFrame.from_records(records).set_index("event_time")

    def _price_barriers(self, entry_price: float, side: int, target: float) -> tuple[float, float]:
        profit_taking = self.config.profit_taking_multiple * target
        stop_loss = self.config.stop_loss_multiple * target
        if side > 0:
            upper_barrier = entry_price * (1.0 + profit_taking)
            lower_barrier = entry_price * (1.0 - stop_loss)
        else:
            upper_barrier = entry_price * (1.0 - profit_taking)
            lower_barrier = entry_price * (1.0 + stop_loss)
        return float(upper_barrier), float(lower_barrier)

    @staticmethod
    def _validate_prices(prices: pd.Series) -> pd.Series:
        if not isinstance(prices, pd.Series):
            raise TypeError("prices must be a pandas Series.")
        clean_prices = prices.dropna().astype(float)
        if clean_prices.empty:
            raise ValueError("prices must contain at least one non-null observation.")
        return clean_prices

    @staticmethod
    def _validate_sides(prices: pd.Series, sides: Optional[pd.Series]) -> pd.Series:
        if sides is None:
            return pd.Series(1, index=prices.index, dtype=int, name="side")
        aligned_sides = sides.reindex(prices.index).fillna(0).astype(int)
        return aligned_sides.rename("side")
