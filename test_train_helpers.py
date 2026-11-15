import json

import numpy as np
import pytest

pytest.importorskip("tensorflow")
pytest.importorskip("mlflow")

from train import dataset_fingerprint, write_reports  # noqa: E402


def test_fingerprint_is_stable_and_sensitive():
    X = np.arange(40, dtype=float).reshape(10, 4)
    y = np.arange(10)
    assert dataset_fingerprint(X, y) == dataset_fingerprint(X.copy(), y.copy())
    assert dataset_fingerprint(X, y) != dataset_fingerprint(X + 1, y)


def test_reports_written(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_reports(np.array([0, 1, 1, 0]), np.array([0, 1, 0, 0]))
    report = json.loads((tmp_path / "reports/classification_report.json").read_text())
    assert "macro avg" in report
    assert (tmp_path / "reports/confusion_matrix.json").exists()
