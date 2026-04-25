#!/usr/bin/env bash
set -euo pipefail

python manage.py makemigrations accounts audittrail notifications settings_app storage_index portal_admin portal_user --noinput || true
python manage.py migrate --noinput
python manage.py collectstatic --noinput
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 300
