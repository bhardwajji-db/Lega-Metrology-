# MetrCheck AI — Docker Deployment Guide

MetrCheck AI (PS 26034) is fully containerized using a two-container Docker architecture:
1. **Backend Service (`metrcheck-backend`)**: Python 3.11 FastAPI with PaddleOCR deep learning engine (PP-OCRv4), SQLite database (aiosqlite), and rule compliance checking.
2. **Frontend Service (`metrcheck-frontend`)**: Production React + TypeScript application built with Vite, served via an optimized Nginx Alpine image acting as a reverse proxy for `/api/` and `/uploads/`.

---

## 1. Prerequisites

- **Docker Desktop** (Windows / macOS) or **Docker Engine + Docker Compose** (Linux)
- **Hardware**: Standard x86_64 / ARM64 CPU (No GPU or CUDA required; inference runs on CPU)

---

## 2. Quickstart (2 Commands)

From the project root directory:

```bash
# 1. Build and start all services in the foreground
docker compose up --build
```

*(Optional: Run in detached mode in the background)*
```bash
docker compose up -d --build
```

To stop the services at any time:
```bash
docker compose down
```

---

## 3. Application URLs & Endpoints

| Component | URL | Purpose |
|---|---|---|
| **Web Application** | [http://localhost:8080](http://localhost:8080) | Full React UI (Dashboard, Multi-angle Analysis, History, Admin) |
| **API Health Check** | [http://localhost:8000/api/health](http://localhost:8000/api/health) | Backend status, OCR engine check & DB connectivity |
| **Interactive API Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger UI for exploring and testing API endpoints |
| **OpenAPI Schema** | [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json) | Raw OpenAPI JSON specification |

---

## 4. Default Login & Demonstration Accounts
 
In demonstration mode (`METRCHECK_DEMO_MODE=true`), operational demo accounts are seeded automatically:
 
| Username | Password | Role | Description |
|---|---|---|---|
| `officer` | `officer123` | `ENFORCEMENT_OFFICER` | Enforcement Officer (Analysis, penalty assessment, notices) |
| `audit` | `audit123` | `AUDIT_OFFICER` | Quality & Compliance Inspector (Technical verification) |
| `merchant` | `merchant123` | `MERCHANT_PUBLIC` | Demo Brand / Merchant (Pre-flight label self-audit) |
 
*System Administrators are provisioned securely via `python -m backend.scripts.bootstrap_admin` or `python -m backend.scripts.change_admin_credentials`. Admin passwords are never seeded or stored in plaintext.*

---

## 5. Data Persistence

All stateful data is persisted on the host filesystem under `./data/` (mounted into `/data` inside the backend container):

```
data/
├── metrc_check.db    # SQLite database (Users, Analyses, Audit History)
└── uploads/          # Uploaded product packaging images and evidence
```

- **Persistence**: Rebuilding or restarting containers preserves all previous analyses, history, and users.
- **Resetting State**: To reset the database and clear all uploads, stop the containers and delete the `./data` folder:
  ```bash
  docker compose down
  # Windows PowerShell:
  Remove-Item -Recurse -Force ./data
  # Linux / macOS:
  rm -rf ./data
  ```

---

## 6. Configuration & Environment Variables

Environment variables can be customized in `docker-compose.yml` or via a `.env` file at the project root:

| Variable | Default Value | Description |
|---|---|---|
| `SECRET_KEY` | `change-me-in-production-secure-key` | JWT token secret key for signing authentication tokens |
| `OCR_ENGINE` | `paddleocr` | OCR engine: `paddleocr` (PP-OCRv4 deep learning engine) |
| `LLM_API_KEY` | *(empty)* | Optional Google Gemini API key for hybrid LLM extraction |
| `UPLOAD_DIR` | `/data/uploads` | Absolute container path for media storage |
| `DATABASE_PATH` | `/data/metrc_check.db` | Absolute container path for SQLite database |
| `PYTHONUNBUFFERED` | `1` | Ensures real-time logging output from Python |

### Changing the Secret Key
Edit `docker-compose.yml` under the `backend.environment` section:
```yaml
environment:
  - SECRET_KEY=your-secure-random-secret-key-here
```

---

## 7. Troubleshooting

### Port Conflicts (Port 8080 or 8000 already in use)
If port 8080 or 8000 is occupied by another application on your host machine:
1. Open `docker-compose.yml`.
2. Change the host port mapping:
   - For frontend: `"8081:80"` (access at `http://localhost:8081`)
   - For backend: `"8001:8000"` (access at `http://localhost:8001`)

### OneDrive / Network Drive Disk Latency Note
If running the project from a directory synced with Microsoft OneDrive or a networked file share, SQLite file locking and disk I/O may encounter occasional latency.
- **Recommendation**: For optimal speed, run Docker from a local un-synced folder (e.g., `C:\projects\metrcheck` or your local home directory).

### Inspecting Logs
```bash
# View aggregated real-time logs
docker compose logs -f

# View backend logs only
docker compose logs -f backend

# View frontend / Nginx logs only
docker compose logs -f frontend
```
