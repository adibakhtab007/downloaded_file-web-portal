#!/bin/sh
set -e

echo "[celery] waiting for database..."
while ! nc -z db 5432; do
  sleep 1
done

echo "[celery] waiting for redis..."
while ! nc -z redis 6379; do
  sleep 1
done

echo "[celery] starting worker..."
exec celery -A config worker -l info
