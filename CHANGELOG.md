# Changelog

All notable changes are documented here. Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/).

## [Unreleased]
### Changed
- Project moved to GitHub: GitHub Actions workflow (`ci.yml`), images pushed to GitHub Container Registry, production approval through a GitHub environment, SBOM attached to GitHub releases
- Flat repository layout: modules, tests, manifests and docs live in the root (`predict.py` instead of `src/predict.py`, `k8s-*.yaml` instead of `kubernetes/`, one `DECISIONS.md` instead of `docs/adr/`)
- Staging and production settings (replica bounds, log level) are applied by `deploy.sh` instead of Kustomize overlays
- Deploy jobs run only when the repository variable `ENABLE_DEPLOY` is `true`
- Author and copyright name set to H. S. Khalsa

### Removed
- Woodpecker CI pipelines, Forgejo issue templates and the optional cosign signing pipeline (they only apply to Codeberg or need extra folders)

### Fixed
- `test_api.py` looked up the legacy `/predict` path in the OpenAPI spec, which only documents `/v1`
- `train.py` uses `datetime.UTC` (ruff `UP017` for Python 3.12)
- `bandit` findings on `urlopen` in `load_test.py` and `joblib.load` in `predict.py` reviewed and annotated
- ruff treats `fastapi.Depends` in argument defaults as intentional (`B008`)

## [1.1.0] - Hardening release

### Added
- Versioned API: `/v1/predict`, `/v1/predict/batch`, `/v1/model/info` (unversioned paths stay as hidden legacy aliases); the deploy smoke test and load test use `/v1`
- Pre-training dataset validation (`data_validation.py`) and an auto-generated `reports/model_card.md`
- `LICENSE` (MIT), `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `.editorconfig`, issue templates
- `ARCHITECTURE.md`, `RUNBOOK.md`, `SLO.md` and architecture decision records (`DECISIONS.md`)
- `check_docs.py`, `make docs-check` and a test that fails on broken Markdown links
- `requirements-train.txt` (MLflow, training only), `make ci`, `make clean`, `make docker-run`, `make manifests`
- CI: `lint-shell-docker` step (`shellcheck`, `hadolint`) required before the image build
- Alert `MLApiErrorBudgetFastBurn`, a `runbook_url` on every alert rule, optional egress-deny `NetworkPolicy`
- OpenAPI examples and documented error responses (401/422/429/503); stricter Renovate rules
- Tests for hashed rate-limit keys, missing artifacts, unmatched routes, chunked bodies and rate-limiter cleanup

### Changed
- Training runs as `python -m src.train`
- `deploy.sh` smoke test sends a real `/v1/predict` request, not only a readiness check
- Replica count is owned by the HPA (no `replicas` in the Deployment or overlays)
- Service type is `ClusterIP`; expose it through the optional Ingress
- Rate limiter stores a hash of the API key instead of the raw key
- Multi-stage Dockerfile on Python 3.12; MLflow is not part of the serving image
- Fixable CRITICAL image vulnerabilities always block the pipeline
- `.dockerignore` and `.gitignore` exclude CI workspace artifacts (`.cache`, `.image`, `reports`)
- Makefile: `help` is the default target, strict shell flags
- README restructured

### Fixed
- Body size limit is also enforced on chunked uploads without `Content-Length`
- Rate limiter no longer grows without bound: idle clients are evicted above 10,000 tracked
- PodDisruptionBudget uses `maxUnavailable: 1`, so node drains are not blocked with one replica
- Pipeline kubectl image is `alpine/k8s` (`bitnami/kubectl` is no longer published for free)
- Optional MLflow model logging can no longer fail the training gate
- Removed committed `__pycache__` directories

## [1.0.0] - Initial release
### Added
- Batch predictions, model info, liveness/readiness endpoints, optional API-key auth
- Structured JSON logging, request IDs, confidence/drift metrics, Grafana dashboard
- Security scans, automatic rollback with smoke tests, hardened Kubernetes manifests
- Input drift metric (`predict_input_zscore_mean_abs`), `MLInputDrift` and `MLNoTraffic` alerts, Grafana panel
- Security headers and request body size limit (413)
- Per-class classification report, confusion matrix and dataset fingerprint from training
- CI: `pip-audit` job, SBOM artifact, configurable Trivy blocking (`TRIVY_EXIT_CODE`), tag-based release
- Optional `ResourceQuota`/`LimitRange`, `load_test.py`, `make audit` and `make load-test`
- Per-client rate limiting (429 + Retry-After), `/version` endpoint
- Kustomize manifests with staging/production settings applied at deploy time
- CI: kubeconform manifest validation, optional cosign image signing
- CI pipeline with Trivy scanning, gitleaks and bandit, automatic rollback and a manual production promotion step
