"""Dataset checks that run before training, so bad data fails fast and loudly."""

import numpy as np


class DataValidationError(ValueError):
    """Raised when the training data violates the expected schema."""


def validate_dataset(
    X: np.ndarray,
    y: np.ndarray,
    n_features: int,
    n_classes: int,
    min_per_class: int = 10,
) -> dict:
    """Validate shape, finiteness, label range and class balance; return summary stats."""
    problems: list[str] = []
    if X.ndim != 2 or X.shape[1] != n_features:
        problems.append(f"expected X with shape (n, {n_features}), got {X.shape}")
    if len(X) != len(y):
        problems.append(f"X has {len(X)} rows but y has {len(y)}")
    if not problems:
        if not np.isfinite(X).all():
            problems.append("X contains NaN or infinite values")
        if y.min() < 0 or y.max() >= n_classes:
            problems.append(f"labels must be in [0, {n_classes - 1}]")
        else:
            counts = np.bincount(y.astype(int), minlength=n_classes)
            too_small = [int(c) for c in np.flatnonzero(counts < min_per_class)]
            if too_small:
                problems.append(f"classes with fewer than {min_per_class} samples: {too_small}")
    if problems:
        raise DataValidationError("; ".join(problems))
    counts = np.bincount(y.astype(int), minlength=n_classes)
    return {
        "n_samples": int(len(X)),
        "min_class_count": int(counts.min()),
        "max_class_count": int(counts.max()),
    }
