#!/bin/sh
set -e

echo "[celery-beat] waiting for database..."
while ! nc -z db 5432; do
  sleep 1
done

echo "[celery-beat] waiting for redis..."
while ! nc -z redis 6379; do
  sleep 1
done

echo "[celery-beat] starting beat..."
exec celery -A config beat -l info
