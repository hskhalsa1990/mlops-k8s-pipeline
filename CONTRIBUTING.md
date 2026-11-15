# Contributing

1. Fork and create a branch from `main`.
2. `make install` (installs dependencies and pre-commit hooks).
3. Make your change with tests. Run `make ci` (lint + tests); if you touched training run `make train`, and if you touched manifests, `deploy.sh` or the Dockerfile run `make manifests` and `make lint-infra`.
4. Update `CHANGELOG.md` under `[Unreleased]`.
5. Open a pull request using the template; CI must be green.

## Standards
- Formatting and linting: `ruff` (`make format`). Max line length 100.
- Commits: short imperative subject (`Add batch size limit`), body explains why.
- No secrets in commits; use GitHub Actions secrets or Kubernetes Secrets.
- Manifests (`k8s-*.yaml`, `monitoring-*.yaml`) must pass `kubeconform`.
- Keep the repository flat: new modules, tests and docs go in the root.

## Decisions and docs
Record significant design decisions in `DECISIONS.md`. Keep `SLO.md` and the alert rules in sync.

## Releases
Update `CHANGELOG.md`, then push a tag such as `v1.0.0` from `main`. The `release` job attaches an
SBOM and creates a GitHub release with generated notes.
