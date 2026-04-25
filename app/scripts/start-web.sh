#!/bin/sh
set -e

echo "[web] waiting for database..."
while ! nc -z db 5432; do
  sleep 1
done

echo "[web] applying migrations..."
python manage.py migrate --noinput

echo "[web] collecting static files..."
python manage.py collectstatic --noinput

echo "[web] seeding security questions..."
python manage.py seed_security_questions || true

echo "[web] creating initial superadmin..."
python manage.py create_initial_superadmin || true

echo "[web] starting gunicorn..."
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 600 --graceful-timeout 600
