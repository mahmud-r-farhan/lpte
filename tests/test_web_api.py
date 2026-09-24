"""Optional HTTP demo integration; core users need not install FastAPI/httpx."""

import importlib.util
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

spec = importlib.util.spec_from_file_location(
    "lpte_web_demo", Path(__file__).parent.parent / "website" / "app.py"
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
app = module.app


@pytest.fixture
def client():
    with TestClient(app) as session:
        yield session


def test_health_languages_and_same_origin(client):
    assert client.get("/api/health").json()["version"] == "1.2.0"
    codes = {p["code"] for p in client.get("/api/languages").json()["languages"]}
    assert {"en", "bn", "zh", "ja", "ko", "ru", "es", "hi", "fr", "de", "ar"} <= codes
    assert client.get("/").status_code == 200
    assert "access-control-allow-origin" not in client.get(
        "/api/health", headers={"Origin": "https://not-our-site.example"}).headers


def test_single_decisions_and_surface_masking(client):
    payload = {"text": "f4ck this bullsh1t", "policy": "balanced"}
    result = client.post("/api/analyze", json=payload).json()
    assert result["decision"]["action"] == "MASK"
    assert result["sanitized"] == "**** this ********"
    assert result["categories"] == ["profanity"]
    allowed = client.post("/api/analyze", json={"text": "damn", "policy": "lenient"}).json()
    assert allowed["decision"]["action"] == "ALLOW"
    assert allowed["sanitized"] == "damn"
    blocked = client.post("/api/analyze", json={
        "text": "you nigger", "policy": "balanced", "threshold": .99,
    }).json()
    assert not blocked["is_toxic"]  # global threshold is separate
    assert blocked["decision"]["action"] == "BLOCK"


def test_code_switch_batch_and_errors(client):
    mixed = client.post("/api/analyze", json={
        "text": "তুই একদম idiot", "language": "bn+en", "policy": "balanced",
    }).json()
    assert mixed["matched_terms"] == ["idiot"]
    assert mixed["sanitized"] == "তুই একদম *****"
    batch = client.post("/api/batch", json={"texts": ["hello", "damn", "কুত্তা"],
                                              "language": "auto", "policy": "balanced"}).json()
    assert batch["total"] == 3 and batch["toxic_count"] == 2
    assert batch["results"][0]["decision"]["action"] == "ALLOW"
    assert client.post("/api/analyze", json={"text": "hello", "language": "unknown"}).status_code == 400
    assert client.post("/api/analyze", json={"text": " ", "policy": "balanced"}).status_code == 422
    assert client.post("/api/analyze", json={"text": "hello", "threshold": 2}).status_code == 422
    assert client.post("/api/analyze", json={"text": "hello", "policy": "invalid"}).status_code == 422
    assert client.post("/api/batch", json={"texts": ["hello", " "]}).status_code == 422
    assert client.post("/api/batch", json={"texts": ["x" * 2001]}).status_code == 422
    assert client.post("/api/batch", json={"texts": ["hi"] * 51}).status_code == 422
