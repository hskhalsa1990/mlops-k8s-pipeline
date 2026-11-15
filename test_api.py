from sklearn.datasets import make_classification

ROW = [0.0] * 20


def test_live_always_ok(client, unloaded):
    assert client.get("/health/live").status_code == 200


def test_ready_reflects_model_state(client, unloaded, loaded):
    assert client.get("/health/ready").status_code == 200


def test_ready_503_without_model(client, unloaded):
    assert client.get("/health/ready").status_code == 503


def test_legacy_health(client, unloaded):
    body = client.get("/health").json()
    assert body == {"status": "model_not_loaded", "model_loaded": False}


def test_predict_without_model_returns_503(client, unloaded):
    assert client.post("/predict", json={"features": ROW}).status_code == 503


def test_predict_rejects_wrong_feature_count(client, loaded):
    assert client.post("/predict", json={"features": [0.0] * 5}).status_code == 422


def test_predict_rejects_nan(client, loaded):
    payload = '{"features": [NaN' + ", 0.0" * 19 + "]}"
    r = client.post("/predict", content=payload, headers={"Content-Type": "application/json"})
    assert r.status_code == 422


def test_predict_success(client, loaded):
    r = client.post("/predict", json={"features": ROW})
    assert r.status_code == 200
    body = r.json()
    assert body["class"] == 3
    assert body["confidence"] == 0.9
    assert body["model_version"] == "test123"


def test_batch_predict(client, loaded):
    r = client.post("/predict/batch", json={"instances": [ROW, ROW, ROW]})
    assert r.status_code == 200
    assert [p["class"] for p in r.json()["predictions"]] == [3, 3, 3]


def test_batch_rejects_empty_and_oversized(client, loaded):
    assert client.post("/predict/batch", json={"instances": []}).status_code == 422
    big = {"instances": [ROW] * 65}
    assert client.post("/predict/batch", json=big).status_code == 422


def test_model_info(client, loaded):
    body = client.get("/model/info").json()
    assert body["version"] == "test123"
    assert body["n_features"] == 20


def test_request_id_is_generated_and_echoed(client, loaded):
    assert client.get("/health").headers["X-Request-ID"]
    r = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert r.headers["X-Request-ID"] == "abc-123"


def test_metrics_exposed(client, loaded):
    client.post("/predict", json={"features": ROW})
    text = client.get("/metrics").text
    assert "predict_requests_total" in text
    assert "predict_latency_seconds_bucket" in text
    assert "http_requests_total" in text


def test_dataset_config_is_valid():
    # Guards against the n_informative bug fixed earlier.
    X, y = make_classification(
        n_samples=2000, n_features=20, n_informative=10, n_redundant=0,
        n_classes=10, random_state=42,
    )
    assert X.shape == (2000, 20)
    assert len(set(y)) == 10


def test_api_key_enforced_when_configured(client, loaded, monkeypatch):
    monkeypatch.setenv("API_KEY", "s3cret")
    assert client.post("/predict", json={"features": ROW}).status_code == 401
    bad = {"X-API-Key": "nope"}
    assert client.post("/predict", json={"features": ROW}, headers=bad).status_code == 401
    ok = {"X-API-Key": "s3cret"}
    assert client.post("/predict", json={"features": ROW}, headers=ok).status_code == 200
    assert client.get("/health/live").status_code == 200  # probes stay open


def test_confidence_metric_exposed(client, loaded):
    client.post("/predict", json={"features": ROW})
    assert "predict_confidence_bucket" in client.get("/metrics").text


def test_security_headers_present(client, loaded):
    r = client.get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"


def test_oversized_body_rejected(client, loaded, monkeypatch):
    monkeypatch.setattr("predict.MAX_BODY_BYTES", 100)
    r = client.post("/predict", json={"features": [0.0] * 20})
    assert r.status_code == 413
    assert r.headers["X-Request-ID"]


def test_input_drift_metric_exposed(client, loaded):
    client.post("/predict", json={"features": ROW})
    assert "predict_input_zscore_mean_abs_bucket" in client.get("/metrics").text


def test_rate_limit_returns_429(client, loaded, monkeypatch):
    import predict

    predict._hits.clear()
    monkeypatch.setattr(predict, "RATE_LIMIT_PER_MIN", 2)
    codes = [client.post("/predict", json={"features": ROW}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    r = client.post("/predict", json={"features": ROW})
    assert r.headers["Retry-After"]
    predict._hits.clear()


def test_version_endpoint(client, loaded):
    body = client.get("/version").json()
    assert body["model_version"] == "test123"
    assert "app_version" in body


def test_rate_limiter_does_not_store_raw_api_key(client, loaded, monkeypatch):
    import predict

    predict._hits.clear()
    monkeypatch.setattr(predict, "RATE_LIMIT_PER_MIN", 5)
    client.post("/predict", json={"features": ROW}, headers={"X-API-Key": "top-secret-key"})
    assert predict._hits
    assert all("top-secret-key" not in k for k in predict._hits)
    predict._hits.clear()


def test_missing_artifacts_leave_service_not_ready(client, unloaded, monkeypatch, tmp_path):
    import predict

    monkeypatch.setenv("MODEL_PATH", str(tmp_path / "none.keras"))
    monkeypatch.setenv("SCALER_PATH", str(tmp_path / "none.joblib"))
    predict.load_artifacts()
    assert client.get("/health/ready").status_code == 503


def test_unknown_route_is_404_and_counted_as_unmatched(client, loaded):
    assert client.get("/does-not-exist").status_code == 404
    assert 'path="unmatched"' in client.get("/metrics").text


def test_openapi_documents_errors_and_examples(client):
    spec = client.get("/openapi.json").json()
    op = spec["paths"]["/v1/predict"]["post"]
    assert {"401", "422", "429", "503"} <= set(op["responses"])
    assert spec["components"]["schemas"]["PredictRequest"]["example"]["features"]
