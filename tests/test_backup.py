"""备份与容灾业务深化测试：备份任务/恢复演练/保留策略。"""
from __future__ import annotations

H = {"X-Internal-Token": "test-internal-key-12345"}


# ── 工具：创建一个备份任务并返回其 id ──
async def _make_job(client, name: str = "job-dr-001") -> str:
    resp = await client.post("/api/backup/jobs", json={
        "name": name, "schedule": "0 2 * * *", "target_system": "订单库",
        "backup_type": "full", "retention_days": 30,
    }, headers=H)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ═══════════════════════════════════════════════════════════
# 备份任务
# ═══════════════════════════════════════════════════════════
class TestBackupJob:
    async def test_create_job_success(self, client):
        rid = await client.post("/api/backup/jobs", json={
            "name": "job-biz-01", "schedule": "0 1 * * *", "target_system": "用户中心",
            "backup_type": "incremental", "retention_days": 14,
        }, headers=H)
        assert rid.status_code == 201
        data = rid.json()
        assert data["name"] == "job-biz-01"
        assert data["status"] == "enabled"
        assert data["backup_type"] == "incremental"

    async def test_create_job_requires_token(self, client):
        resp = await client.post("/api/backup/jobs", json={
            "name": "no-token-job", "schedule": "0 1 * * *", "target_system": "x",
        })
        assert resp.status_code in (401, 403)

    async def test_create_job_duplicate_name(self, client):
        await _make_job(client, "job-dup-01")
        resp = await client.post("/api/backup/jobs", json={
            "name": "job-dup-01", "schedule": "0 1 * * *", "target_system": "x",
        }, headers=H)
        assert resp.status_code == 409

    async def test_list_jobs(self, client):
        await _make_job(client, "job-list-01")
        resp = await client.get("/api/backup/jobs", headers=H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    async def test_list_jobs_status_filter(self, client):
        await _make_job(client, "job-filter-01")
        resp = await client.get("/api/backup/jobs?status=enabled", headers=H)
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["status"] == "enabled"

    async def test_list_jobs_keyword_search(self, client):
        await client.post("/api/backup/jobs", json={
            "name": "kw-unique-alpha", "schedule": "0 1 * * *", "target_system": "专属关键词系统",
        }, headers=H)
        resp = await client.get("/api/backup/jobs?keyword=" + "专属关键词", headers=H)
        assert resp.status_code == 200
        names = [i["name"] for i in resp.json()["items"]]
        assert "kw-unique-alpha" in names

    async def test_get_job_by_id(self, client):
        job_id = await _make_job(client, "job-get-01")
        resp = await client.get(f"/api/backup/jobs/{job_id}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["id"] == job_id

    async def test_get_job_not_found(self, client):
        resp = await client.get("/api/backup/jobs/no-such-id", headers=H)
        assert resp.status_code == 404

    async def test_update_job(self, client):
        job_id = await _make_job(client, "job-upd-01")
        resp = await client.patch(f"/api/backup/jobs/{job_id}", json={
            "target_system": "新目标库", "retention_days": 60,
        }, headers=H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["target_system"] == "新目标库"
        assert data["retention_days"] == 60

    async def test_job_valid_transition_pause(self, client):
        job_id = await _make_job(client, "job-pause-01")
        resp = await client.patch(f"/api/backup/jobs/{job_id}/status",
                                  json={"status": "paused"}, headers=H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"

    async def test_job_invalid_transition(self, client):
        job_id = await _make_job(client, "job-badtr-01")
        # enabled -> completed 是合法的；completed -> enabled 应被拒绝
        await client.patch(f"/api/backup/jobs/{job_id}/status",
                           json={"status": "completed"}, headers=H)
        resp = await client.patch(f"/api/backup/jobs/{job_id}/status",
                                  json={"status": "enabled"}, headers=H)
        assert resp.status_code == 400

    async def test_job_failed_sets_last_run(self, client):
        job_id = await _make_job(client, "job-fail-01")
        resp = await client.patch(f"/api/backup/jobs/{job_id}/status",
                                  json={"status": "failed"}, headers=H)
        assert resp.status_code == 200
        assert resp.json()["last_run_at"] is not None


# ═══════════════════════════════════════════════════════════
# 恢复演练
# ═══════════════════════════════════════════════════════════
class TestRestoreDrill:
    async def test_create_drill_success(self, client):
        job_id = await _make_job(client, "drill-job-01")
        resp = await client.post("/api/backup/drills", json={
            "name": "演练一", "backup_job_id": job_id, "planned_date": "2026-10-01",
        }, headers=H)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "planned"
        assert data["backup_job_id"] == job_id

    async def test_create_drill_missing_job(self, client):
        resp = await client.post("/api/backup/drills", json={
            "name": "孤儿演练", "backup_job_id": "no-such-job",
        }, headers=H)
        assert resp.status_code == 400

    async def test_drill_full_flow(self, client):
        job_id = await _make_job(client, "drill-flow-01")
        created = await client.post("/api/backup/drills", json={
            "name": "全流程演练", "backup_job_id": job_id,
        }, headers=H)
        drill_id = created.json()["id"]
        r1 = await client.patch(f"/api/backup/drills/{drill_id}/status",
                                json={"status": "in_progress"}, headers=H)
        assert r1.status_code == 200
        r2 = await client.post(f"/api/backup/drills/{drill_id}/finish", json={
            "result_summary": "恢复成功", "duration_minutes": 25, "passed": True,
        }, headers=H)
        assert r2.status_code == 200
        assert r2.json()["status"] == "passed"
        assert r2.json()["duration_minutes"] == 25

    async def test_drill_invalid_transition(self, client):
        job_id = await _make_job(client, "drill-bad-01")
        created = await client.post("/api/backup/drills", json={
            "name": "错误迁移演练", "backup_job_id": job_id,
        }, headers=H)
        drill_id = created.json()["id"]
        # planned 不能直接 -> passed
        resp = await client.patch(f"/api/backup/drills/{drill_id}/status",
                                  json={"status": "passed"}, headers=H)
        assert resp.status_code == 400

    async def test_finish_only_in_progress(self, client):
        job_id = await _make_job(client, "drill-fin-01")
        created = await client.post("/api/backup/drills", json={
            "name": "未开始演练", "backup_job_id": job_id,
        }, headers=H)
        drill_id = created.json()["id"]
        resp = await client.post(f"/api/backup/drills/{drill_id}/finish", json={
            "result_summary": "x", "duration_minutes": 1, "passed": True,
        }, headers=H)
        assert resp.status_code == 400

    async def test_list_drills_filter(self, client):
        job_id = await _make_job(client, "drill-list-01")
        await client.post("/api/backup/drills", json={
            "name": "筛选演练", "backup_job_id": job_id,
        }, headers=H)
        resp = await client.get(f"/api/backup/drills?backup_job_id={job_id}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1


# ═══════════════════════════════════════════════════════════
# 保留策略
# ═══════════════════════════════════════════════════════════
class TestRetentionPolicy:
    async def test_create_policy_success(self, client):
        resp = await client.post("/api/backup/policies", json={
            "name": "policy-biz-01", "strategy": "weekly",
            "keep_count": 12, "archive_after_days": 90,
        }, headers=H)
        assert resp.status_code == 201
        data = resp.json()
        assert data["strategy"] == "weekly"
        assert data["keep_count"] == 12
        assert data["status"] == "active"

    async def test_create_policy_duplicate(self, client):
        await client.post("/api/backup/policies", json={
            "name": "policy-dup-01", "strategy": "daily", "keep_count": 7,
        }, headers=H)
        resp = await client.post("/api/backup/policies", json={
            "name": "policy-dup-01", "strategy": "daily", "keep_count": 7,
        }, headers=H)
        assert resp.status_code == 409

    async def test_list_policies(self, client):
        await client.post("/api/backup/policies", json={
            "name": "policy-list-01", "strategy": "monthly", "keep_count": 6,
        }, headers=H)
        resp = await client.get("/api/backup/policies", headers=H)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_update_policy(self, client):
        created = await client.post("/api/backup/policies", json={
            "name": "policy-upd-01", "strategy": "daily", "keep_count": 7,
        }, headers=H)
        pid = created.json()["id"]
        resp = await client.patch(f"/api/backup/policies/{pid}", json={
            "keep_count": 14, "archive_after_days": 180,
        }, headers=H)
        assert resp.status_code == 200
        assert resp.json()["keep_count"] == 14
        assert resp.json()["archive_after_days"] == 180

    async def test_policy_disable(self, client):
        created = await client.post("/api/backup/policies", json={
            "name": "policy-dis-01", "strategy": "daily", "keep_count": 7,
        }, headers=H)
        pid = created.json()["id"]
        resp = await client.patch(f"/api/backup/policies/{pid}/status",
                                  json={"status": "disabled"}, headers=H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"

    async def test_get_policy_not_found(self, client):
        resp = await client.get("/api/backup/policies/no-such", headers=H)
        assert resp.status_code == 404

    async def test_policy_requires_token(self, client):
        resp = await client.post("/api/backup/policies", json={
            "name": "no-token-policy", "strategy": "daily", "keep_count": 7,
        })
        assert resp.status_code in (401, 403)
