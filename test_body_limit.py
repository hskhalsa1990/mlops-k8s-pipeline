from fastapi.testclient import TestClient

from predict import MAX_BODY_BYTES, app


def test_chunked_body_over_limit_is_rejected():
    """No Content-Length is sent for a generator body, so only the streaming check can catch it."""
    half = b"x" * (MAX_BODY_BYTES // 2 + 1)
    response = TestClient(app).post(
        "/predict", content=iter([half, half]), headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413
    assert response.json() == {"detail": "request body too large"}
    assert response.headers["x-request-id"]
