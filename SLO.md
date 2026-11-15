# Service level objectives

These targets are the ones the shipped alert rules in `monitoring-prometheusrule.yaml` enforce.
Adjust both together if you change them.

| Objective | Target | Measured by | Alert |
| --- | --- | --- | --- |
| Availability | 99.5% of requests are not 5xx | `http_requests_total` | `MLApiHighErrorRate` (> 5% for 5 min), `MLApiErrorBudgetFastBurn` (> 14% over 5 min and 1 h) |
| Latency | p95 prediction latency below 500 ms | `predict_latency_seconds` | `MLApiHighLatency` |
| Model readiness | Every running pod has a model loaded | `ml_model_loaded` | `MLModelNotLoaded` |
| Data health (signal) | Median confidence >= 0.5, median input z-score <= 1.5 | `predict_confidence`, `predict_input_zscore_mean_abs` | `MLConfidenceDrift`, `MLInputDrift` |

## Error budget
A 99.5% availability target leaves a 0.5% error budget. The fast-burn alert fires at a 14% error
ratio, about 28 times the sustainable rate, and means the budget is being consumed in hours rather
than weeks. Follow the [runbook](RUNBOOK.md) and consider rolling back the latest deployment.

## Notes
Drift alerts are signals for investigation, not automatic retraining triggers.
