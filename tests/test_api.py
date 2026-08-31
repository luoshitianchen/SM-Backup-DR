"""SM Backup DR 领域测试：备份任务、快照、恢复演练与统计。"""

import pytest
from fastapi.testclient import TestClient

from app import base
from app.main import VERSION, app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(base, "internal_api_key", lambda: "TEST")
    base.reset_state()
    from app.main import _init as init_db
    init_db()
    with TestClient(app) as c:
        c.headers["X-Internal-Token"] = "TEST"
        yield c


def _job(client, name="nightly"):
    return client.post("/api/backup/jobs", json={"name": name, "source": "postgres://db/prod", "target": "s3://backup/prod", "retention_days": 30}).json()["id"]


def test_health_and_version(client):
    r = client.get("/health", headers={"X-Request-Id": "suite-test"})
    assert r.status_code == 200
    assert r.json()["version"] == VERSION


def test_job_lifecycle(client):
    assert client.post("/api/backup/jobs", json={"name": "nightly", "source": "mysql://prod", "target": "s3://backup"}).status_code == 201
    assert client.post("/api/backup/jobs", json={"name": "nightly", "source": "mysql://prod", "target": "s3://backup"}).status_code == 409
    assert client.get("/api/backup/jobs").json()["total"] == 1


def test_run_and_restore(client):
    job_id = _job(client)
    snap = client.post(f"/api/backup/jobs/{job_id}/run").json()
    assert snap["status"] == "completed"
    assert len(snap["checksum"]) == 64
    assert client.post(f"/api/backup/snapshots/{snap['id']}/restore").json()["message"] == "恢复演练完成"
    stats = client.get("/api/backup/stats").json()
    assert stats["snapshots"] == 1
    assert stats["restored"] == 1


def test_snapshot_filters(client):
    job_id = _job(client)
    client.post(f"/api/backup/jobs/{job_id}/run")
    assert client.get("/api/backup/snapshots", params={"job_id": job_id}).json()["total"] == 1
    assert client.get("/api/backup/policies").json()["jobs"][0]["retention_days"] == 30


def test_missing_job(client):
    assert client.post("/api/backup/jobs/nope/run").status_code == 404
    assert client.post("/api/backup/snapshots/nope/restore").status_code == 404


def test_manifest_and_crypto(client):
    assert client.get("/api/integration/manifest").json()["version"] == VERSION
    enc = client.post("/api/crypto/encrypt", json={"value": "x"}).json()["ciphertext"]
    assert client.post("/api/crypto/decrypt", json={"value": enc}).json()["plaintext"] == "x"


def test_write_requires_auth(client):
    del client.headers["X-Internal-Token"]
    assert client.post("/api/backup/jobs", json={"name": "x", "source": "a", "target": "b"}).status_code == 401
