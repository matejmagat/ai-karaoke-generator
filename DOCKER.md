# Running with Docker

The whole stack runs with Docker Compose: PostgreSQL, the Django API, the FastAPI
lyrics-alignment service, and an nginx container that serves the React build and
proxies the API.

```
browser ──► nginx :8080 (karaoke-gen-frontend)
              ├── /               React build (SPA fallback)
              ├── /api/, /admin/  ──► karaoke-gen-service :8000 (gunicorn) ──► db (PostgreSQL)
              ├── /media/         generated stems + SRT  (shared `media` volume)      │
              └── /django-static/ admin/Swagger assets   (shared volume)              ▼
                                                        lyrics-align-service :8001 (Demucs + WhisperX)
```

Only nginx is published on the host. The API, aligner, and database are reachable
only on the Compose network.

## Quick start

```bash
cp .env.docker.example .env
# Edit .env: set GENIUS_ACCESS_TOKEN and DJANGO_SECRET_KEY
#   python -c "import secrets; print(secrets.token_urlsafe(50))"

# CPU
docker compose up --build

# NVIDIA GPU (needs the NVIDIA driver + NVIDIA Container Toolkit)
docker compose -f compose.yaml -f compose.gpu.yaml up --build
```

Open <http://localhost:8080>, register, and generate a song. Swagger is at
<http://localhost:8080/api/docs/> and the Django admin at <http://localhost:8080/admin/>.

Create an admin user:

```bash
docker compose exec karaoke-gen-service python manage.py createsuperuser
```

The first generation downloads the Demucs, WhisperX, and alignment model weights
into the `model-cache` volume, so it takes noticeably longer than later runs.

## Services

| Service | Image | Notes |
|---|---|---|
| `karaoke-gen-frontend` | `node:20` build → `nginx:1.27-alpine` | Built with `REACT_APP_API_BASE_URL=""`, so the app calls the API on its own origin. |
| `karaoke-gen-service` | `python:3.12-slim` + gunicorn | Runs `migrate` and `collectstatic` on start. One worker with 8 threads, because song imports run on an in-process thread pool. |
| `lyrics-align-service` | `python:3.11-slim` + PyTorch 2.8 | `TORCH_VARIANT=cpu` (default) or `cu128`. A single uvicorn worker; jobs are held in memory and the pipeline runs one at a time. |
| `db` | `postgres:17-alpine` | Django switches to PostgreSQL when `POSTGRES_DB` is set; otherwise it keeps using SQLite. |

## Volumes

| Volume | Contents |
|---|---|
| `postgres-data` | Database |
| `media` | Uploaded/generated audio and SRT files (read-only in nginx) |
| `django-static` | `collectstatic` output (read-only in nginx) |
| `model-cache` | Hugging Face, torch hub, and NLTK caches (`HF_HOME`, `TORCH_HOME`, `NLTK_DATA`) |
| `align-runtime` | Aligner job working directories |

`docker compose down` keeps the data; `docker compose down -v` deletes it, including the downloaded models.

## Configuration

Compose reads `.env` from the repository root (template: `.env.docker.example`).

| Variable | Default | Purpose |
|---|---|---|
| `APP_PORT` | `8080` | Host port for nginx |
| `GENIUS_ACCESS_TOKEN` | required | Genius API token used by the aligner |
| `DJANGO_SECRET_KEY` | required | Django signing key |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,karaoke-gen-service` | Add your LAN IP or domain to reach the app from other devices |
| `CORS_ALLOWED_ORIGINS` / `CSRF_TRUSTED_ORIGINS` | `http://localhost:8080` | Public origin(s) used by the browser |
| `DJANGO_SECURE_PROXY_SSL_HEADER` | `False` | Set `True` behind a TLS-terminating proxy that sends `X-Forwarded-Proto` |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | `karaoke` | Database credentials |
| `TORCH_VARIANT` | `cpu` | PyTorch wheel index for the aligner; `compose.gpu.yaml` sets `cu128` |
| `REACT_APP_API_BASE_URL` | empty | Build-time API origin; leave empty for same-origin behind nginx |
| `NGINX_CLIENT_MAX_BODY_SIZE` | `200m` | Upload size limit |

## Useful commands

```bash
docker compose logs -f lyrics-align-service     # watch the pipeline
docker compose exec karaoke-gen-service python manage.py test
docker compose build --no-cache lyrics-align-service
```

## Known limitations

- Jobs in progress are lost if `karaoke-gen-service` or `lyrics-align-service` restarts, because both track work in-process. Moving imports to Celery/RQ with Redis (see the production checklist in `INTEGRATION.md`) would remove this.
- On CPU, WhisperX uses `int8` and a full song can take several minutes; the GPU override is recommended for regular use.
- TLS is not configured; put a reverse proxy (Caddy, Traefik, nginx) in front of port 8080 for public deployments.
