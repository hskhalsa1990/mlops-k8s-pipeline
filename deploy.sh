#!/usr/bin/env bash
# Usage: deploy.sh <namespace> <image>
# Renders manifests, applies them, waits for rollout, smoke-tests, and rolls back on failure.
# Per-environment settings (override with HPA_MIN, HPA_MAX, LOG_LEVEL):
#   production: 3-20 replicas, INFO   staging: 1-3 replicas, DEBUG   anything else: 2-10, INFO
set -euo pipefail

NS="${1:?namespace required}"
IMAGE="${2:?image required}"
TIMEOUT="${ROLLOUT_TIMEOUT:-180s}"

case "$NS" in
  production) DEF_MIN=3; DEF_MAX=20; DEF_LOG=INFO ;;
  staging) DEF_MIN=1; DEF_MAX=3; DEF_LOG=DEBUG ;;
  *) DEF_MIN=2; DEF_MAX=10; DEF_LOG=INFO ;;
esac
HPA_MIN="${HPA_MIN:-$DEF_MIN}"
HPA_MAX="${HPA_MAX:-$DEF_MAX}"
LOG_LEVEL="${LOG_LEVEL:-$DEF_LOG}"

[[ "$HPA_MIN" =~ ^[0-9]+$ && "$HPA_MAX" =~ ^[0-9]+$ ]] || { echo "HPA_MIN/HPA_MAX must be numbers" >&2; exit 1; }
[[ "$LOG_LEVEL" =~ ^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$ ]] || { echo "invalid LOG_LEVEL" >&2; exit 1; }

kubectl get namespace "$NS" >/dev/null 2>&1 || kubectl create namespace "$NS"

echo "Applying manifests to ${NS} (replicas ${HPA_MIN}-${HPA_MAX}, log level ${LOG_LEVEL})"
kubectl kustomize . \
  | sed -e "s|IMAGE_PLACEHOLDER|${IMAGE}|g" \
        -e "s|^  minReplicas: .*|  minReplicas: ${HPA_MIN}|" \
        -e "s|^  maxReplicas: .*|  maxReplicas: ${HPA_MAX}|" \
        -e "s|^  LOG_LEVEL: .*|  LOG_LEVEL: ${LOG_LEVEL}|" \
  | kubectl apply -n "$NS" -f -

if [ "${ENABLE_MONITORING:-false}" = "true" ]; then
  kubectl apply -n "$NS" -f monitoring-servicemonitor.yaml -f monitoring-prometheusrule.yaml
fi

if ! kubectl rollout status deployment/ml-model-api -n "$NS" --timeout="$TIMEOUT"; then
  echo "Rollout failed; rolling back" >&2
  kubectl rollout undo deployment/ml-model-api -n "$NS"
  kubectl rollout status deployment/ml-model-api -n "$NS" --timeout="$TIMEOUT" || true
  exit 1
fi

# Smoke test from inside a pod: the model must be loaded and ready.
# It also sends one real prediction (using the pod's API_KEY if one is configured), because a pod
# can be ready yet still return errors.
SMOKE_PY='
import json, os, urllib.request as u
assert u.urlopen("http://localhost:8080/health/ready", timeout=5).status == 200
headers = {"Content-Type": "application/json"}
if os.environ.get("API_KEY"):
    headers["X-API-Key"] = os.environ["API_KEY"]
req = u.Request(
    "http://localhost:8080/v1/predict",
    data=json.dumps({"features": [0.0] * 20}).encode(),
    headers=headers,
)
body = json.load(u.urlopen(req, timeout=10))
assert "class" in body and 0.0 <= body["confidence"] <= 1.0, body
'
if ! kubectl exec -n "$NS" deploy/ml-model-api -- python -c "$SMOKE_PY"; then
  echo "Smoke test failed; rolling back" >&2
  kubectl rollout undo deployment/ml-model-api -n "$NS"
  exit 1
fi

echo "Deployed ${IMAGE} to namespace ${NS}"
