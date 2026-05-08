import numpy as np
import pandas as pd

from src.dataprep.fractional_diff import FractionalDifferentiator


def test_fractional_diff_weights_truncate_when_small():
    differentiator = FractionalDifferentiator(weight_threshold=1e-3)

    weights = differentiator.get_weights(d_value=0.4, size=500)

    assert len(weights) < 500
    assert weights[0] == 1.0


def test_find_min_d_reaches_stationarity_on_random_walk():
    random_state = np.random.default_rng(7)
    steps = random_state.normal(loc=0.0, scale=1.0, size=500)
    prices = pd.Series(100 + np.cumsum(steps), name="eurusd_close")
    differentiator = FractionalDifferentiator(adf_significance_level=0.05, weight_threshold=1e-4)

    result = differentiator.find_min_d(prices, candidate_d_values=np.arange(0.2, 1.01, 0.1))

    assert 0.2 <= result.d_value <= 1.0
    assert result.adf_pvalue <= 0.05
    assert not result.differentiated.empty
    assert result.differentiated.index.is_monotonic_increasing