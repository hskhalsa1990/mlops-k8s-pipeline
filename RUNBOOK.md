# Runbook

Namespace examples use `production`; substitute `staging` as needed.

| Alert | Meaning | First steps |
| --- | --- | --- |
| `MLApiDown` | Prometheus cannot scrape the service | `kubectl get pods -n production`; check events and logs; verify the NetworkPolicy and Service selector |
| `MLModelNotLoaded` | Pod is up but has no model | Confirm `model/` is in the image (`kubectl exec ... ls model`); check `MODEL_PATH`; roll back |
| `MLApiHighLatency` | p95 above 500 ms | Check HPA (`kubectl get hpa`), CPU throttling and batch sizes; scale up or raise limits |
| `MLApiHighErrorRate` | More than 5% 5xx | Inspect logs filtered by `request_id`; roll back if it started with a deploy |
| `MLConfidenceDrift` / `MLInputDrift` | Live data differs from training data | Compare recent inputs to the training distribution; retrain with fresh data |
| `MLApiErrorBudgetFastBurn` | Error ratio far above the 99.5% availability budget (see [SLO](SLO.md)) | Treat as an incident: check recent deploys and roll back first, investigate second |
| `MLNoTraffic` | No requests for an hour | Check upstream callers, Ingress and DNS |

## Common commands
```bash
kubectl logs -n production deploy/ml-model-api --tail=200
kubectl rollout history deploy/ml-model-api -n production
kubectl rollout undo deploy/ml-model-api -n production
kubectl port-forward -n production svc/ml-api-service 8080:80   # then: curl localhost:8080/version
```

## Rollback
`deploy.sh` rolls back automatically if the rollout or the smoke test fails. For a manual
rollback use `kubectl rollout undo`, or re-run the production job of an earlier successful workflow run in the GitHub Actions UI.

## Rotating the API key
```bash
kubectl create secret generic ml-api-secret --from-literal=api-key=<new> -n production \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl rollout restart deploy/ml-model-api -n production
```
