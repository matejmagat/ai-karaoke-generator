# Frontend integration

The React app submits a full-mix audio file to Django. Django delegates separation and alignment to `lyrics-align-service`, imports the generated instrumental, vocals, and SRT files, and exposes them to the player.

## Local setup

### 1. Lyrics alignment service — port 8001

```bash
cd lyrics-align-service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set GENIUS_ACCESS_TOKEN in .env when the lyrics pipeline requires it.
uvicorn src.api.main:app --host 127.0.0.1 --port 8001 --reload
```

Confirm `http://localhost:8001/health` returns a successful response.

### 2. Django API — port 8000

```bash
cd karaoke-gen-service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
LYRICS_ALIGN_SERVICE_URL=http://localhost:8001 python manage.py runserver 8000
```

The development configuration permits `http://localhost:3000` through Django CORS. Swagger is available at `http://localhost:8000/api/docs/`.

### 3. React app — port 3000

```bash
cd karaoke-gen-frontend
cp .env.example .env
npm install
npm start
```

Register or sign in, enter title, artist, and a language code, choose an MP3/WAV full mix, and start generation. The app polls every two seconds and loads the generated media when processing completes.

## Configuration

| Variable | Purpose | Development default |
|---|---|---|
| `REACT_APP_API_BASE_URL` | API and media origin used by React | `http://localhost:8000` |
| `CORS_ALLOWED_ORIGINS` | Comma-separated browser origins allowed by Django | `http://localhost:3000` |
| `LYRICS_ALIGN_SERVICE_URL` | Downstream separation/alignment service | `http://localhost:8001` |
| `DJANGO_SECRET_KEY` | Django signing secret | Required in production |
| `DJANGO_DEBUG` | Enables development behavior and local media routes | `True` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated API hostnames | `localhost,127.0.0.1` |
| `MEDIA_ROOT` | Generated media storage path | `media` |
| `MEDIA_URL` | Public generated-media URL prefix | `/media/` |

## Production checklist

- Set `DJANGO_DEBUG=False`, generate a unique `DJANGO_SECRET_KEY`, and set explicit `DJANGO_ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS`.
- Put `MEDIA_ROOT` on persistent shared storage and serve `MEDIA_URL` through a reverse proxy or object storage/CDN; Django's debug media helper is development-only.
- Replace the in-process `ThreadPoolExecutor` importer with Celery or RQ backed by Redis/RabbitMQ so jobs survive restarts and work across multiple web workers.
- Prefer an HttpOnly, Secure refresh-token cookie and a short-lived access token when hardening authentication; local storage is used here for demo session restoration.
- Terminate TLS at the reverse proxy and route the frontend, `/api/`, and `/media/` under controlled public origins.
