# Secure File Portal

Production-ready Django starter for a secure file sharing portal with:
- Email-only login
- OTP 2FA for admin and web users
- Multiple super admins
- Read-only admin users
- Self-registration + admin approval for web users
- Password expiry and password history
- Security questions + unlock flow
- Audit trail with per-session trace ID
- Protected downloads via Nginx `X-Accel-Redirect`
- Local + NAS storage indexing
- Docker Compose deployment

## Quick start

1. Copy `.env.example` to `.env` and fill values.
2. Put your TLS cert/key under `nginx/certs/` or replace Nginx config with your own cert management.
3. Build and start:
   ```bash
   docker compose up --build -d
   ```
4. Run migrations and create initial data:
   ```bash
   docker compose exec web python manage.py makemigrations accounts audittrail notifications settings_app storage_index portal_admin portal_user
   docker compose exec web python manage.py migrate
   docker compose exec web python manage.py seed_security_questions
   docker compose exec web python manage.py create_initial_superadmin
   ```
5. Collect static:
   ```bash
   docker compose exec web python manage.py collectstatic --noinput
   ```

## Default storage roots
- Local: `/srv/fileportal/local`
- NAS: `/srv/fileportal/nas`

These are bind-mounted from the host via Docker Compose.

## Important notes
- Protected files are never exposed directly from Django or public Nginx URLs.
- Downloads are authorized in Django, then served through Nginx internal redirect.
- OTP expiry defaults to 2 minutes.
- OTP max attempts defaults to 3.
- Session timeout defaults to 5 minutes and is DB-configurable.
- Unauthorized access attempts are both logged in DB and can trigger admin email alerts.

## What is already implemented in this starter
- Core data model
- Registration / approval / login / OTP / password-expiry flows
- Audit trail + trace id
- Admin portal permissions (super admin vs readonly admin)
- Web user portal with ACL folder browsing
- File indexing scanner
- Celery tasks for mail, reminders, cleanup, and scans
- Middleware for inactivity timeout

## What you should still harden or extend before internet-facing production
- Replace self-signed/test TLS handling with your enterprise cert workflow.
- Add antivirus / file type screening if required.
- Add rate limiting at Nginx or WAF level.
- Add SIEM forwarding if you need off-box audit duplication.
- Review Office365 SMTP and sender policy in your tenant.
