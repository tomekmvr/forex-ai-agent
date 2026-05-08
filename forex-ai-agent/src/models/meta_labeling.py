from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
import structlog
from sklearn.base import ClassifierMixin, clone
from sklearn.linear_model import LogisticRegression


class MetaLabelingModel:
    """Train a primary direction model and a meta model that filters weak signals."""

    def __init__(
        self,
        primary_model: Optional[ClassifierMixin] = None,
        meta_model: Optional[ClassifierMixin] = None,
        primary_probability_threshold: float = 0.45,
        meta_probability_threshold: float = 0.5,
    ) -> None:
        self.primary_model = primary_model or LogisticRegression(max_iter=1000, class_weight="balanced")
        self.meta_model = meta_model or LogisticRegression(max_iter=1000, class_weight="balanced")
        self.primary_probability_threshold = primary_probability_threshold
        self.meta_probability_threshold = meta_probability_threshold
        self.logger = structlog.get_logger(__name__).bind(component="meta_labeling_model")
        self._fitted_primary_model: Optional[ClassifierMixin] = None
        self._fitted_meta_model: Optional[ClassifierMixin] = None

    def fit(
        self,
        features: pd.DataFrame,
        direction_labels: pd.Series,
        meta_labels: Optional[pd.Series] = None,
    ) -> "MetaLabelingModel":
        feature_frame = self._validate_features(features)
        direction_series = self._validate_target(direction_labels, feature_frame.index, name="direction_labels")

        self.logger.info(
            "reasoning_trace",
            step="fit_meta_labeling_models",
            sample_count=len(feature_frame),
            feature_count=feature_frame.shape[1],
        )

        self._fitted_primary_model = clone(self.primary_model)
        self._fitted_primary_model.fit(feature_frame, direction_series)

        primary_signals = self.predict_primary(feature_frame)
        primary_confidence = self.predict_primary_confidence(feature_frame)

        if meta_labels is None:
            meta_series = pd.Series(
                ((primary_signals != 0) & (primary_signals == np.sign(direction_series))).astype(int),
                index=feature_frame.index,
                name="meta_labels",
            )
        else:
            meta_series = self._validate_target(meta_labels, feature_frame.index, name="meta_labels")

        meta_features = self.build_meta_features(feature_frame, primary_signals, primary_confidence)
        train_mask = primary_signals != 0
        if train_mask.sum() == 0:
            raise ValueError("Primary model did not produce any directional signals for meta training.")

        self._fitted_meta_model = clone(self.meta_model)
        self._fitted_meta_model.fit(meta_features.loc[train_mask], meta_series.loc[train_mask])
        return self

    def predict_primary(self, features: pd.DataFrame) -> pd.Series:
        model = self._require_primary_model()
        feature_frame = self._validate_features(features)

        if not hasattr(model, "predict_proba"):
            return pd.Series(model.predict(feature_frame), index=feature_frame.index, name="primary_signal")

        probabilities = model.predict_proba(feature_frame)
        classes = list(model.classes_)
        primary_signals = np.zeros(len(feature_frame), dtype=int)

        if -1 in classes and 1 in classes:
            short_probability = probabilities[:, classes.index(-1)]
            long_probability = probabilities[:, classes.index(1)]
            primary_signals = np.where(
                long_probability >= self.primary_probability_threshold,
                1,
                np.where(short_probability >= self.primary_probability_threshold, -1, 0),
            )
        else:
            predicted = model.predict(feature_frame)
            primary_signals = np.asarray(predicted, dtype=int)

        self.logger.info(
            "reasoning_trace",
            step="predict_primary_direction",
            sample_count=len(feature_frame),
            active_signal_count=int(np.count_nonzero(primary_signals)),
        )
        return pd.Series(primary_signals, index=feature_frame.index, name="primary_signal")

    def predict_primary_confidence(self, features: pd.DataFrame) -> pd.Series:
        model = self._require_primary_model()
        feature_frame = self._validate_features(features)

        if hasattr(model, "predict_proba"):
            confidence = model.predict_proba(feature_frame).max(axis=1)
        else:
            confidence = np.ones(len(feature_frame), dtype=float)
        return pd.Series(confidence, index=feature_frame.index, name="primary_confidence")

    def build_meta_features(
        self,
        features: pd.DataFrame,
        primary_signals: pd.Series,
        primary_confidence: pd.Series,
    ) -> pd.DataFrame:
        feature_frame = self._validate_features(features)
        signal_series = primary_signals.reindex(feature_frame.index).fillna(0).astype(int)
        confidence_series = primary_confidence.reindex(feature_frame.index).fillna(0.0).astype(float)
        meta_features = feature_frame.copy()
        meta_features["primary_signal"] = signal_series
        meta_features["primary_confidence"] = confidence_series
        meta_features["abs_primary_signal"] = signal_series.abs()
        return meta_features

    def predict(self, features: pd.DataFrame) -> pd.Series:
        model = self._require_meta_model()
        feature_frame = self._validate_features(features)
        primary_signals = self.predict_primary(feature_frame)
        primary_confidence = self.predict_primary_confidence(feature_frame)
        meta_features = self.build_meta_features(feature_frame, primary_signals, primary_confidence)

        if hasattr(model, "predict_proba") and 1 in list(model.classes_):
            probabilities = model.predict_proba(meta_features)[:, list(model.classes_).index(1)]
            decisions = (probabilities >= self.meta_probability_threshold).astype(int)
        else:
            decisions = np.asarray(model.predict(meta_features), dtype=int)

        decisions = np.where(primary_signals.to_numpy() == 0, 0, decisions)
        self.logger.info(
            "reasoning_trace",
            step="predict_meta_labels",
            sample_count=len(feature_frame),
            approved_signal_count=int(decisions.sum()),
        )
        return pd.Series(decisions, index=feature_frame.index, name="trade_decision")

    def _require_primary_model(self) -> ClassifierMixin:
        if self._fitted_primary_model is None:
            raise ValueError("Primary model has not been fitted yet.")
        return self._fitted_primary_model

    def _require_meta_model(self) -> ClassifierMixin:
        if self._fitted_meta_model is None:
            raise ValueError("Meta model has not been fitted yet.")
        return self._fitted_meta_model

    @staticmethod
    def _validate_features(features: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(features, pd.DataFrame):
            raise TypeError("features must be a pandas DataFrame.")
        if features.empty:
            raise ValueError("features must not be empty.")
        return features.astype(float)

    @staticmethod
    def _validate_target(target: pd.Series, index: pd.Index, name: str) -> pd.Series:
        if not isinstance(target, pd.Series):
            target = pd.Series(target, index=index, name=name)
        aligned = target.reindex(index)
        if aligned.isna().any():
            raise ValueError(f"{name} must align with the feature index and contain no missing values.")
        return aligned.astype(int).rename(name)
