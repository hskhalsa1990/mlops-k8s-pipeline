import numpy as np
import pytest
from fastapi.testclient import TestClient

from predict import app, state


class FakeScaler:
    def transform(self, x):
        return x


class FakeModel:
    """Predicts class 3 with 0.9 confidence for every row."""

    def predict(self, x, verbose=0):
        probs = np.full((len(x), 10), 0.1 / 9)
        probs[:, 3] = 0.9
        return probs


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def loaded(monkeypatch):
    monkeypatch.setattr(state, "model", FakeModel())
    monkeypatch.setattr(state, "scaler", FakeScaler())
    monkeypatch.setattr(state, "metadata", {"version": "test123", "accuracy": 0.9})


@pytest.fixture
def unloaded(monkeypatch):
    monkeypatch.setattr(state, "model", None)
    monkeypatch.setattr(state, "scaler", None)
