"""Inference API: single and batch prediction with health, metrics and model info."""
import hashlib
import json
import logging
import os
import secrets
import sys
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import joblib
import numpy as np
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel, ConfigDict, Field

N_FEATURES = 20
MAX_BATCH = int(os.getenv("MAX_BATCH_SIZE", "64"))
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "0"))  # 0 disables
MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", "1048576"))  # 1 MiB
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}
QUIET_PATHS = {"/metrics", "/health/live", "/health/ready"}

ERROR_RESPONSES = {
    401: {"description": "Invalid or missing API key"},
    422: {"description": "Input failed validation (needs exactly 20 finite floats per row)"},
    429: {"description": "Rate limit exceeded; see the Retry-After header"},
    503: {"description": "Model not loaded yet"},
}

Feature = Annotated[float, Field(allow_inf_nan=False)]
FeatureRow = Annotated[list[Feature], Field(min_length=N_FEATURES, max_length=N_FEATURES)]


# --------------------------------------------------------------------------- logging
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(getattr(record, "fields", {}))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    log = logging.getLogger("ml-api")
    log.handlers = [handler]
    log.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    log.propagate = False
    return log


logger = configure_logging()

# --------------------------------------------------------------------------- metrics
REQUEST_COUNT = Counter("predict_requests_total", "Total prediction requests")
REQUEST_LATENCY = Histogram("predict_latency_seconds", "Prediction latency")
PREDICT_ERRORS = Counter("predict_errors_total", "Prediction requests that failed")
PREDICTED_CLASS = Counter("predict_class_total", "Predictions by class", ["predicted_class"])
HTTP_REQUESTS = Counter(
    "http_requests_total", "HTTP requests", ["method", "path", "status"]
)
CONFIDENCE = Histogram(
    "predict_confidence", "Top-class confidence (watch for drift)",
    buckets=(0.3, 0.5, 0.7, 0.8, 0.9, 0.95, 0.99),
)
INPUT_ZSCORE = Histogram(
    "predict_input_zscore_mean_abs",
    "Mean |z-score| of each input row vs the training scaler (input drift signal)",
    buckets=(0.5, 0.8, 1.0, 1.3, 1.6, 2.0, 3.0, 5.0),
)
RATE_LIMITED = Counter("rate_limited_total", "Requests rejected with 429")
MODEL_LOADED = Gauge("ml_model_loaded", "1 if a model is loaded, else 0")


# --------------------------------------------------------------------------- state
class ModelState:
    model = None
    scaler = None
    metadata: dict = {}

    @property
    def ready(self) -> bool:
        return self.model is not None and self.scaler is not None


state = ModelState()


def load_artifacts() -> None:
    model_path = Path(os.getenv("MODEL_PATH", "model/model.keras"))
    scaler_path = Path(os.getenv("SCALER_PATH", "model/scaler.joblib"))
    metadata_path = Path(os.getenv("METADATA_PATH", "model/metadata.json"))

    if not (model_path.exists() and scaler_path.exists()):
        logger.warning(
            "model artifacts not found", extra={"fields": {"model_path": str(model_path)}}
        )
        MODEL_LOADED.set(0)
        return

    import tensorflow as tf  # imported lazily so tests and tooling stay fast

    state.model = tf.keras.models.load_model(model_path)
    state.scaler = joblib.load(scaler_path)  # nosec B301 - artifact baked into our own image
    if metadata_path.exists():
        state.metadata = json.loads(metadata_path.read_text())
    MODEL_LOADED.set(1)
    logger.info(
        "model loaded",
        extra={"fields": {"model_version": state.metadata.get("version", "unknown")}},
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_artifacts()
    yield


app = FastAPI(
    title="MLOps Classifier API",
    version=os.getenv("APP_VERSION", "dev"),
    description="Real-time classification service. See /docs for the interactive schema.",
    lifespan=lifespan,
)


# --------------------------------------------------------------------------- auth
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(key: str | None = Depends(api_key_header)) -> None:
    """Enforced only when the API_KEY environment variable is set."""
    expected = os.getenv("API_KEY")
    if expected and not (key and secrets.compare_digest(key, expected)):
        raise HTTPException(status_code=401, detail="invalid or missing API key")


# --------------------------------------------------------------------------- rate limit
_hits: dict[str, deque] = defaultdict(deque)
MAX_TRACKED_CLIENTS = 10_000  # upper bound before idle clients are evicted


def _prune_idle_clients(now: float) -> None:
    """Drop clients with no hit in the last 60 s so memory stays bounded."""
    for client in [c for c, w in _hits.items() if not w or now - w[-1] > 60]:
        del _hits[client]


def rate_limit(request: Request, key: str | None = Depends(api_key_header)) -> None:
    """Per-client sliding-window limit (per API key if sent, else per IP). Per pod."""
    limit = RATE_LIMIT_PER_MIN
    if limit <= 0:
        return
    if key:
        client = "key:" + hashlib.sha256(key.encode()).hexdigest()[:16]  # never store raw keys
    else:
        client = f"ip:{request.client.host if request.client else 'unknown'}"
    now = time.monotonic()
    if len(_hits) > MAX_TRACKED_CLIENTS:
        _prune_idle_clients(now)
    window = _hits[client]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= limit:
        RATE_LIMITED.inc()
        retry = max(1, int(60 - (now - window[0])))
        raise HTTPException(
            status_code=429, detail="rate limit exceeded", headers={"Retry-After": str(retry)}
        )
    window.append(now)


# --------------------------------------------------------------------------- schemas
class PredictRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"features": [0.0] * N_FEATURES}})
    features: FeatureRow


class BatchPredictRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"instances": [[0.0] * N_FEATURES, [0.5] * N_FEATURES]}}
    )
    instances: list[FeatureRow] = Field(..., min_length=1, max_length=MAX_BATCH)


class Prediction(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    class_id: int = Field(alias="class")
    confidence: float


class PredictResponse(Prediction):
    model_version: str


class BatchPredictResponse(BaseModel):
    predictions: list[Prediction]
    model_version: str


# --------------------------------------------------------------------------- middleware
class BodyTooLarge(Exception):
    """Raised inside the receive channel once a request body exceeds the limit."""


class BodyLimitMiddleware:
    """Enforce MAX_BODY_BYTES on the bytes actually received.

    The Content-Length check in `observability` is only a fast path; chunked uploads send no
    Content-Length, so the limit is also counted while the body streams in.
    """

    def __init__(self, app, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        received = 0
        started = False

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise BodyTooLarge
            return message

        async def tracking_send(message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except BodyTooLarge:
            if not started:
                response = JSONResponse({"detail": "request body too large"}, status_code=413)
                await response(scope, receive, send)


# Added before `observability` so it sits inside it: metrics and logs then see a normal 413.
app.add_middleware(BodyLimitMiddleware, max_bytes=MAX_BODY_BYTES)


@app.middleware("http")
async def observability(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    start = time.perf_counter()
    status = 500
    try:
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > MAX_BODY_BYTES:
            response = JSONResponse({"detail": "request body too large"}, status_code=413)
        else:
            response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response
    finally:
        route = request.scope.get("route")
        path = route.path if route else "unmatched"
        HTTP_REQUESTS.labels(request.method, path, str(status)).inc()
        if path not in QUIET_PATHS:
            logger.info(
                "request",
                extra={"fields": {
                    "request_id": request_id,
                    "method": request.method,
                    "path": path,
                    "status": status,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                }},
            )


# --------------------------------------------------------------------------- inference
# Model endpoints are served under /v1 (documented) and, unchanged, at the root (legacy alias).
router = APIRouter()


def _require_model() -> None:
    if not state.ready:
        raise HTTPException(status_code=503, detail="model not loaded")


def _infer(rows: list[list[float]]) -> list[Prediction]:
    try:
        x = state.scaler.transform(np.array(rows, dtype=np.float32))
        for z in np.abs(x).mean(axis=1):
            INPUT_ZSCORE.observe(float(z))
        probs = state.model.predict(x, verbose=0)
    except Exception:
        PREDICT_ERRORS.inc()
        logger.exception("inference failed")
        raise HTTPException(status_code=500, detail="inference failed") from None
    results = []
    for p in probs:
        cls = int(np.argmax(p))
        PREDICTED_CLASS.labels(str(cls)).inc()
        CONFIDENCE.observe(float(p[cls]))
        results.append(Prediction(**{"class": cls, "confidence": float(p[cls])}))
    return results


def _version() -> str:
    return str(state.metadata.get("version", "unknown"))


@router.post(
    "/predict",
    response_model=PredictResponse,
    tags=["inference"],
    summary="Classify one feature vector",
    responses=ERROR_RESPONSES,
    dependencies=[Depends(verify_api_key), Depends(rate_limit)],
)
def predict(body: PredictRequest):
    _require_model()
    REQUEST_COUNT.inc()
    with REQUEST_LATENCY.time():
        (result,) = _infer([body.features])
    return PredictResponse(
        **{"class": result.class_id, "confidence": result.confidence, "model_version": _version()}
    )


@router.post(
    "/predict/batch",
    response_model=BatchPredictResponse,
    tags=["inference"],
    summary="Classify up to MAX_BATCH_SIZE feature vectors",
    responses=ERROR_RESPONSES,
    dependencies=[Depends(verify_api_key), Depends(rate_limit)],
)
def predict_batch(body: BatchPredictRequest):
    _require_model()
    REQUEST_COUNT.inc(len(body.instances))
    with REQUEST_LATENCY.time():
        results = _infer(body.instances)
    return BatchPredictResponse(predictions=results, model_version=_version())


# --------------------------------------------------------------------------- operations
@router.get("/model/info", tags=["operations"], dependencies=[Depends(verify_api_key)])
def model_info():
    _require_model()
    return {"n_features": N_FEATURES, "max_batch_size": MAX_BATCH, **state.metadata}


app.include_router(router, prefix="/v1")
app.include_router(router, include_in_schema=False)  # legacy unversioned paths


@app.get("/version", tags=["operations"])
def version():
    """Build and model version, for dashboards and incident triage."""
    return {"app_version": app.version, "model_version": _version()}


@app.get("/health/live", tags=["operations"])
def live():
    """Liveness: the process is up. Never depends on the model."""
    return {"status": "alive"}


@app.get("/health/ready", tags=["operations"])
def ready():
    """Readiness: only succeeds once the model is loaded."""
    _require_model()
    return {"status": "ready"}


@app.get("/health", tags=["operations"])
@app.get("/", include_in_schema=False)
def health():
    """Backwards-compatible health endpoint."""
    return {
        "status": "healthy" if state.ready else "model_not_loaded",
        "model_loaded": state.ready,
    }


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
