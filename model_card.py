"""Render a short, human-readable model card from training metadata."""


def render_model_card(metadata: dict) -> str:
    rows = "\n".join(f"| {key} | {value} |" for key, value in sorted(metadata.items()))
    return f"""# Model card: mlops-classifier

## Intended use
Multi-class classification of {metadata.get("n_features", "?")} numeric features into
{metadata.get("n_classes", "?")} classes, served by the inference API in this repository.

## Training data
Fingerprint `{metadata.get("dataset_sha", "unknown")}`. The default loader produces synthetic data;
replace it with your dataset and describe its source, collection period and known biases here.

## Evaluation
Accuracy {metadata.get("accuracy", "?")}, macro-F1 {metadata.get("macro_f1", "?")} on a stratified
20% hold-out. See `classification_report.json` and `confusion_matrix.json` for per-class results.

## Limitations
Inputs must match the training feature order and scale. Monitor `predict_confidence` and
`predict_input_zscore_mean_abs` for drift and retrain when alerts fire.

## Metadata
| Field | Value |
| --- | --- |
{rows}
"""
