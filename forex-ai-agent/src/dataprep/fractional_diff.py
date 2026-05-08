from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np
import pandas as pd
import structlog
from statsmodels.tsa.stattools import adfuller

try:
    from fracdiff import fdiff as accelerated_fdiff
except ImportError:  # pragma: no cover - optional fast path
    accelerated_fdiff = None


@dataclass(frozen=True)
class FractionalDiffResult:
    differentiated: pd.Series
    d_value: float
    adf_pvalue: float
    used_accelerated_backend: bool


class FractionalDifferentiator:
    """Apply fractional differentiation while searching for the lowest stationary order."""

    def __init__(
        self,
        adf_significance_level: float = 0.05,
        weight_threshold: float = 1e-5,
    ) -> None:
        self.adf_significance_level = adf_significance_level
        self.weight_threshold = weight_threshold
        self.logger = structlog.get_logger(__name__).bind(component="fractional_differentiator")

    def find_min_d(
        self,
        series: pd.Series,
        candidate_d_values: Optional[Iterable[float]] = None,
    ) -> FractionalDiffResult:
        clean_series = self._validate_series(series)
        if candidate_d_values is None:
            candidates = list(np.arange(0.1, 1.01, 0.1))
        else:
            candidates = list(candidate_d_values)
        if not candidates:
            raise ValueError("candidate_d_values must contain at least one candidate.")

        self.logger.info(
            "reasoning_trace",
            step="search_min_fractional_difference_order",
            series_name=clean_series.name,
            candidate_count=len(candidates),
            adf_significance_level=self.adf_significance_level,
        )

        best_result: Optional[FractionalDiffResult] = None
        for d_value in candidates:
            differentiated = self.transform(clean_series, d_value=d_value)
            if differentiated.empty:
                continue

            try:
                adf_pvalue = self.adf_pvalue(differentiated)
            except ValueError:
                self.logger.info(
                    "reasoning_trace",
                    step="skip_fractional_difference_order",
                    d_value=float(d_value),
                    usable_observations=len(differentiated),
                    reason="insufficient_observations_for_adf",
                )
                continue

            result = FractionalDiffResult(
                differentiated=differentiated,
                d_value=float(d_value),
                adf_pvalue=adf_pvalue,
                used_accelerated_backend=accelerated_fdiff is not None,
            )
            best_result = result
            if adf_pvalue <= self.adf_significance_level:
                self.logger.info(
                    "reasoning_trace",
                    step="selected_fractional_difference_order",
                    d_value=float(d_value),
                    adf_pvalue=adf_pvalue,
                )
                return result

        if best_result is None:
            raise ValueError("Fractional differentiation produced no usable observations.")

        self.logger.warning(
            "reasoning_trace",
            step="no_stationary_fractional_difference_order_found",
            fallback_d_value=best_result.d_value,
            fallback_adf_pvalue=best_result.adf_pvalue,
        )
        return best_result

    def transform(self, series: pd.Series, d_value: float) -> pd.Series:
        clean_series = self._validate_series(series)
        if not 0 < d_value <= 1:
            raise ValueError("d_value must be in the interval (0, 1].")

        self.logger.info(
            "reasoning_trace",
            step="apply_fractional_difference",
            series_name=clean_series.name,
            d_value=float(d_value),
            accelerated_backend=accelerated_fdiff is not None,
        )

        if accelerated_fdiff is not None:
            values = accelerated_fdiff(clean_series.to_numpy(dtype=float), n=d_value, window=0, mode="same")
            differentiated = pd.Series(values, index=clean_series.index, name=clean_series.name)
            return differentiated.dropna()

        weights = self.get_weights(d_value=d_value, size=clean_series.size)
        window_width = len(weights)
        output = pd.Series(index=clean_series.index, dtype=float, name=clean_series.name)

        for position in range(window_width - 1, clean_series.size):
            window = clean_series.iloc[position - window_width + 1 : position + 1]
            output.iloc[position] = float(np.dot(weights[::-1], window.to_numpy(dtype=float)))

        return output.dropna()

    def get_weights(self, d_value: float, size: int) -> np.ndarray:
        if size <= 0:
            raise ValueError("size must be positive.")

        weights = [1.0]
        for k in range(1, size):
            weight = -weights[-1] * (d_value - k + 1) / k
            if abs(weight) < self.weight_threshold:
                break
            weights.append(weight)
        return np.array(weights, dtype=float)

    @staticmethod
    def adf_pvalue(series: pd.Series) -> float:
        if len(series) < 10:
            raise ValueError("ADF test requires at least 10 observations.")
        return float(adfuller(series, autolag="AIC")[1])

    @staticmethod
    def _validate_series(series: pd.Series) -> pd.Series:
        if not isinstance(series, pd.Series):
            raise TypeError("series must be a pandas Series.")
        clean_series = series.dropna().astype(float)
        if clean_series.empty:
            raise ValueError("series must contain at least one non-null observation.")
        return clean_series
