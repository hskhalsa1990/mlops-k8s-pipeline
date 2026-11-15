import pytest

ROW = [0.0] * 20


@pytest.mark.usefixtures("loaded")
@pytest.mark.parametrize("prefix", ["/v1", ""])
def test_predict_available_versioned_and_legacy(client, prefix):
    response = client.post(f"{prefix}/predict", json={"features": ROW})
    assert response.status_code == 200
    assert response.json()["class"] == 3


@pytest.mark.usefixtures("loaded")
def test_v1_batch_and_model_info(client):
    batch = client.post("/v1/predict/batch", json={"instances": [ROW, ROW]})
    assert batch.status_code == 200
    assert len(batch.json()["predictions"]) == 2
    assert client.get("/v1/model/info").json()["version"] == "test123"


def test_openapi_documents_only_v1(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/v1/predict" in paths
    assert "/predict" not in paths
