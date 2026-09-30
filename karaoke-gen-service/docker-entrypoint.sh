#!/bin/sh
set -e

if [ "${DJANGO_MIGRATE_ON_START:-true}" = "true" ]; then
    python manage.py migrate --noinput
fi

if [ "${DJANGO_COLLECTSTATIC_ON_START:-true}" = "true" ]; then
    python manage.py collectstatic --noinput --verbosity 0
fi

exec "$@"
