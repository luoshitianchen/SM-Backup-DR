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
