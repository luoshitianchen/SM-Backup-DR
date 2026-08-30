# SM Backup DR

备份与灾备中心：备份任务、RTO/RPO和恢复演练。

```powershell
git clone https://github.com/luoshitianchen/SM-Backup-DR.git
cd SM-Backup-DR
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8430
```

接口：`/health`、`/readyz`、`/api/overview`、`/api/items`、`/api/ops/metrics`、`/api/crypto/status`。

内置 TrustedHost、安全响应头、CSP、国密状态接口和容器加固。

## 企业维护资料

- [安全基线](SECURITY_BASELINE.md)
- [运维与可观测性](OPERATIONS.md)
- [应急响应手册](INCIDENT_RESPONSE.md)
- [生产部署检查清单](DEPLOYMENT_CHECKLIST.md)
- [变更记录](CHANGELOG.md)
- [版本号](VERSION)
- [依赖锁定](requirements.lock)

