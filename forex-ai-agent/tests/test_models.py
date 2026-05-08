import pandas as pd

from src.models.meta_labeling import MetaLabelingModel
from src.models.triple_barrier import TripleBarrierConfig, TripleBarrierLabeler


def test_triple_barrier_uses_dynamic_volatility_scaled_barriers():
    index = pd.date_range("2026-01-01", periods=8, freq="h")
    prices = pd.Series([100.0, 100.4, 100.6, 101.7, 101.9, 101.8, 102.1, 102.2], index=index)
    sides = pd.Series(1, index=index)
    volatility = pd.Series([0.004, 0.005, 0.006, 0.007, 0.004, 0.006, 0.005, 0.004], index=index)
    labeler = TripleBarrierLabeler(
        TripleBarrierConfig(
            profit_taking_multiple=1.0,
            stop_loss_multiple=1.0,
            vertical_barrier_bars=3,
            volatility_lookback=3,
            min_target_return=1e-6,
        )
    )

    labels = labeler.label_events(prices=prices, sides=sides, volatility=volatility)

    assert not labels.empty
    assert labels.iloc[0]["label"] == 1
    assert labels.iloc[0]["meta_label"] == 1
    assert labels.iloc[0]["upper_barrier"] > labels.iloc[0]["entry_price"]
    assert labels.iloc[0]["target_volatility"] != labels.iloc[1]["target_volatility"]


def test_meta_labeling_model_filters_weaker_primary_signals():
    features = pd.DataFrame(
        {
            "trend_strength": [-2.5, -2.0, -1.5, -0.1, 0.1, 1.4, 2.0, 2.5],
            "volatility_regime": [0.2, 0.3, 0.4, 0.9, 0.95, 0.4, 0.3, 0.2],
        }
    )
    direction_labels = pd.Series([-1, -1, -1, 1, 1, 1, 1, 1])
    meta_labels = pd.Series([1, 1, 1, 0, 0, 1, 1, 1])
    model = MetaLabelingModel(primary_probability_threshold=0.45, meta_probability_threshold=0.5)

    model.fit(features, direction_labels, meta_labels)
    primary_signals = model.predict_primary(features)
    trade_decisions = model.predict(features)

    assert set(primary_signals.unique()).issubset({-1, 0, 1})
    assert set(trade_decisions.unique()).issubset({0, 1})
    assert trade_decisions.iloc[[0, 1, 2, 5, 6, 7]].mean() > trade_decisions.iloc[[3, 4]].mean()