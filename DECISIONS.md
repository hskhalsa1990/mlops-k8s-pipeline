# Architecture decision records

Short records of significant decisions. Add a new numbered section (Context, Decision,
Consequences) when a decision changes how the system is built or operated.

| ADR | Decision |
| --- | --- |
| [0001](#0001-bake-the-trained-model-into-the-container-image) | Bake the trained model into the container image |
| [0002](#0002-promote-to-production-manually-through-a-github-environment) | Promote to production manually through a GitHub environment |
| [0003](#0003-deploy-smoke-test-sends-a-real-prediction) | Deploy smoke test sends a real prediction |
| [0004](#0004-rate-limiting-is-per-pod-and-in-memory) | Rate limiting is per pod and in memory |

## 0001: Bake the trained model into the container image

### Context
The service needs a trained model at start-up. It could be pulled from object storage or a model
registry at runtime, or shipped inside the image.

### Decision
`model/` is copied into the image at build time, after the accuracy gate has passed.

### Consequences
- Each image is an immutable unit: commit SHA, dataset fingerprint and model always match.
- Rollback is a normal `kubectl rollout undo`; no separate model version to reconcile.
- No runtime dependency on external storage, and the root filesystem can stay read-only.
- A new model means a new image build; images grow with model size.

## 0002: Promote to production manually through a GitHub environment

### Context
Staging should receive every successful `main` build, but production changes need a human decision.

### Decision
`deploy-staging` runs automatically. `deploy-production` uses the `production` GitHub environment
with required reviewers, so the job pauses until a maintainer approves it in the Actions UI.

### Consequences
- The approval is recorded by GitHub against the exact workflow run.
- Production always deploys the exact image that was built, scanned and run on staging.
- Rolling back to an earlier build means re-running the production job of an earlier run.

## 0003: Deploy smoke test sends a real prediction

### Context
A pod can pass its readiness probe (the model file loaded) and still fail on real requests, for
example because of a scaler or schema mismatch.

### Decision
After the rollout completes, `deploy.sh` runs a check inside a pod: `/health/ready` must return
200 and `POST /v1/predict` with a zero vector must return a class and a confidence between 0 and 1.
The pod's own `API_KEY` is used when one is configured. Any failure triggers `kubectl rollout undo`.

### Consequences
- Broken models and incompatible artifacts are caught before they stay in production.
- The check uses only the Python already in the image; no extra tools are required.
- The input is synthetic, so it proves the serving path works, not that predictions are correct.

## 0004: Rate limiting is per pod and in memory

### Context
The API needs basic abuse protection without adding Redis or another shared dependency.

### Decision
Each pod keeps a sliding window per client (API key hash, otherwise IP) and answers 429 with
`Retry-After`. It is disabled by default (`RATE_LIMIT_PER_MIN=0`).

### Consequences
- Effective limit is roughly `limit x replicas`; use the Ingress limit for a global cap.
- Behind a proxy, set uvicorn's `--forwarded-allow-ips` so the real client IP is used.
- State is lost on restart, which is acceptable for abuse protection.
