# syntax=docker/dockerfile:1

# Django REST API: authentication, catalog, libraries, and generation jobs.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_DEBUG=False \
    MEDIA_ROOT=/data/media \
    STATIC_URL=/django-static/ \
    STATIC_ROOT=/data/static \
    SQLITE_PATH=/data/db/db.sqlite3

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data/media /data/static /data/db \
    && chown -R app:app /app /data

COPY --chown=app:app . .

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/admin/login/', timeout=4)"

ENTRYPOINT ["./docker-entrypoint.sh"]

# One process with several threads: song imports run on an in-process
# ThreadPoolExecutor, so a single long-lived worker keeps them alive and
# avoids jobs being orphaned by worker recycling.
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "1", \
     "--threads", "8", \
     "--timeout", "300", \
     "--access-logfile", "-"]
