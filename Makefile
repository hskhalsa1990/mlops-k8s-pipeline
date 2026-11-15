.DEFAULT_GOAL := help
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.PHONY: install lint format test train run docker-build docker-run smoke audit load-test manifests lint-infra docs-check ci clean help

help:  ## Show targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

install:  ## Install runtime and dev dependencies
	pip install -r requirements-train.txt -r requirements-dev.txt
	pre-commit install

lint:  ## Lint and check formatting
	ruff check .
	ruff format --check .

format:  ## Auto-fix lint issues and format
	ruff check --fix .
	ruff format .

test:  ## Run tests with coverage
	python -m pytest

train:  ## Train the model and write artifacts to model/
	python train.py && python check_metrics.py

run:  ## Serve the API locally on :8080
	uvicorn predict:app --port 8080 --reload

docker-build:  ## Build the image (requires model/ from `make train`)
	docker build --build-arg VERSION=local -t mlops-classifier:local .

docker-run:  ## Run the local image on :8080 (read-only, non-root, like production)
	docker run --rm -p 8080:8080 --read-only --tmpfs /tmp --cap-drop ALL mlops-classifier:local

smoke:  ## Call a running local API
	curl -s localhost:8080/health/ready

audit:  ## Scan Python dependencies for known vulnerabilities
	pip install pip-audit && pip-audit -r requirements.txt

load-test:  ## Send 200 requests to a running local API and print latency stats
	python load_test.py --url http://localhost:8080 --requests 200

manifests:  ## Render the Kustomize manifests (requires kubectl)
	kubectl kustomize . >/dev/null
	@echo "manifests render OK"

lint-infra:  ## Lint the shell script and the Dockerfile (needs shellcheck, hadolint)
	shellcheck deploy.sh
	hadolint --failure-threshold error Dockerfile

docs-check:  ## Fail on broken relative Markdown links
	python check_docs.py

ci: lint test  ## Run the same checks as the CI lint-test job

clean:  ## Remove generated artifacts and caches
	rm -rf model reports mlruns metrics.txt metrics.json coverage.xml report.xml .pytest_cache .ruff_cache .coverage
