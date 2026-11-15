import numpy as np
import pytest

from data_validation import DataValidationError, validate_dataset
from model_card import render_model_card


def make(n=200, f=4, c=2):
    rng = np.random.default_rng(0)
    return rng.normal(size=(n, f)), np.arange(n) % c


def test_valid_dataset_returns_stats():
    X, y = make()
    stats = validate_dataset(X, y, n_features=4, n_classes=2)
    assert stats["n_samples"] == 200 and stats["min_class_count"] == 100


def test_rejects_wrong_shape():
    X, y = make()
    with pytest.raises(DataValidationError, match="shape"):
        validate_dataset(X, y, n_features=5, n_classes=2)


def test_rejects_nan():
    X, y = make()
    X[0, 0] = np.nan
    with pytest.raises(DataValidationError, match="NaN"):
        validate_dataset(X, y, n_features=4, n_classes=2)


def test_rejects_out_of_range_labels():
    X, y = make()
    y[0] = 5
    with pytest.raises(DataValidationError, match="labels"):
        validate_dataset(X, y, n_features=4, n_classes=2)


def test_rejects_tiny_classes():
    X, y = make()
    y[:195] = 0
    with pytest.raises(DataValidationError, match="fewer than"):
        validate_dataset(X, y, n_features=4, n_classes=2)


def test_model_card_contains_key_facts():
    card = render_model_card({"accuracy": 0.9, "macro_f1": 0.88, "dataset_sha": "abc", "version": "v1"})
    assert "abc" in card and "0.9" in card and "| version | v1 |" in card
