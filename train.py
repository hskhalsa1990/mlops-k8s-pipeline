"""Train the classifier, log to MLflow, and write deployable artifacts.

Run with `python train.py`.
Outputs: model/model.keras, model/scaler.joblib, model/metadata.json,
metrics.txt (Prometheus text format) and metrics.json.
"""
import hashlib
import json
import logging
import os
from datetime import UTC, datetime

import joblib
import mlflow
import sklearn
import tensorflow as tf
from sklearn.datasets import make_classification
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from data_validation import validate_dataset
from model_card import render_model_card

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("train")

SEED = int(os.getenv("SEED", "42"))
EPOCHS = int(os.getenv("EPOCHS", "30"))
N_FEATURES = 20
N_CLASSES = 10


def load_data():
    """Dummy data - replace with your real dataset loader.

    n_informative must be >= log2(n_classes * n_clusters_per_class), so 10 is safe.
    """
    return make_classification(
        n_samples=2000, n_features=N_FEATURES, n_informative=10, n_redundant=0,
        n_classes=N_CLASSES, random_state=SEED,
    )


def build_model() -> tf.keras.Model:
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(N_FEATURES,)),
        tf.keras.layers.Dense(128, activation="relu"),
        tf.keras.layers.Dropout(0.5),
        tf.keras.layers.Dense(N_CLASSES, activation="softmax"),
    ])
    model.compile(
        optimizer="adam",
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def write_reports(y_true, y_pred) -> None:
    """Per-class precision/recall/F1 and the confusion matrix, kept as CI artifacts."""
    os.makedirs("reports", exist_ok=True)
    report = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
    with open("reports/classification_report.json", "w") as f:
        json.dump(report, f, indent=2)
    with open("reports/confusion_matrix.json", "w") as f:
        json.dump(confusion_matrix(y_true, y_pred).tolist(), f)


def dataset_fingerprint(X, y) -> str:
    """SHA-256 of the training data so every model can be traced to its exact dataset."""
    digest = hashlib.sha256()
    digest.update(X.tobytes())
    digest.update(y.tobytes())
    return digest.hexdigest()[:16]


def main() -> None:
    tf.keras.utils.set_random_seed(SEED)
    os.makedirs("model", exist_ok=True)

    X, y = load_data()
    stats = validate_dataset(X, y, N_FEATURES, N_CLASSES)
    log.info("Dataset validated: %s", stats)
    data_hash = dataset_fingerprint(X, y)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=SEED, stratify=y
    )
    scaler = StandardScaler().fit(X_train)
    X_train, X_test = scaler.transform(X_train), scaler.transform(X_test)
    joblib.dump(scaler, "model/scaler.joblib")

    commit = os.getenv("CI_COMMIT_SHA", "")
    version = commit[:8] if commit else "local"
    with mlflow.start_run(run_name=f"train-{version}"):
        mlflow.log_params(
            {"seed": SEED, "epochs": EPOCHS, "version": version, "dataset_sha": data_hash}
        )
        model = build_model()
        early_stop = tf.keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=5, restore_best_weights=True
        )
        model.fit(
            X_train, y_train, epochs=EPOCHS, validation_data=(X_test, y_test),
            callbacks=[early_stop], verbose=2,
        )

        _, acc = model.evaluate(X_test, y_test, verbose=0)
        acc = float(acc)
        y_pred = model.predict(X_test, verbose=0).argmax(1)
        macro_f1 = float(f1_score(y_test, y_pred, average="macro"))
        write_reports(y_test, y_pred)
        mlflow.log_metrics({"accuracy": acc, "macro_f1": macro_f1})
        mlflow.log_artifacts("reports")
        try:
            mlflow.keras.log_model(model, "mlflow_model")
        except Exception:  # optional artifact; the deployable model is saved below
            log.warning("MLflow model logging failed; continuing", exc_info=True)
        model.save("model/model.keras")

    metadata = {
        "version": version,
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "accuracy": round(acc, 4),
        "macro_f1": round(macro_f1, 4),
        "n_features": N_FEATURES,
        "n_classes": N_CLASSES,
        "seed": SEED,
        "dataset_sha": data_hash,
        "tensorflow": tf.__version__,
        "scikit_learn": sklearn.__version__,
    }
    with open("model/metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    with open("reports/model_card.md", "w") as f:
        f.write(render_model_card(metadata))

    # Prometheus text format for tools that read simple metrics files.
    with open("metrics.txt", "w") as f:
        f.write(f"accuracy {acc:.4f}\nmacro_f1 {macro_f1:.4f}\n")
    with open("metrics.json", "w") as f:
        json.dump({"accuracy": acc, "macro_f1": macro_f1}, f)

    log.info("Model trained: %.1f%% accuracy, macro-F1 %.3f", acc * 100, macro_f1)


if __name__ == "__main__":
    main()
