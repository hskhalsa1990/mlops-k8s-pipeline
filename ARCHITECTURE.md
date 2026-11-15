# Architecture

## Components
| Component | Role |
| --- | --- |
| `train.py` | Trains the Keras model, logs to MLflow, writes `model/` artifacts and quality reports |
| `check_metrics.py` | Accuracy gate; fails the pipeline below `MIN_ACCURACY` |
| `predict.py` | FastAPI inference service (validation, auth, rate limit, metrics, JSON logs) |
| `Dockerfile` | Multi-stage, non-root image that bakes in `model/` |
| `k8s-*.yaml`, `kustomization.yaml` | Kubernetes manifests rendered with Kustomize; `deploy.sh` sets per-environment replicas and log level |
| `monitoring-*.yaml`, `grafana-dashboard.json` | ServiceMonitor, alert rules and Grafana dashboard |
| `ci.yml` (stored as `.github/workflows/ci.yml`) | GitHub Actions: test, scan, train, build, deploy and release (SBOM) |

## Request flow
Client -> Ingress (TLS, rate limit, optional) -> Service (ClusterIP) -> pod -> middleware
(request ID, body limit, security headers) -> auth and rate-limit dependencies -> validation ->
scaler -> model -> response, with Prometheus metrics recorded at each step.

## Design decisions
- **Model baked into the image:** each image is an immutable, traceable unit (commit SHA, dataset SHA).
- **Gate before build:** a model below the accuracy threshold never produces an image.
- **Manual production promotion:** staging deploys automatically; production waits for approval in the `production` GitHub environment.
- **Automatic rollback:** failed rollout or smoke test triggers `kubectl rollout undo`.
- **Secure defaults:** non-root, read-only filesystem, dropped capabilities, ClusterIP, NetworkPolicy.
- **Per-pod rate limiting:** simple and dependency-free; use the Ingress limit for global limits.

## Known limits
- Rate-limit state is per pod and in memory.
- Drift metrics are signals, not automatic retraining triggers.
- The dataset is synthetic; replace `load_data()` in `train.py` before real use.
