# Secure File Portal README

## 1. Purpose

This web portal is a secure file sharing and file access management system built with Django, PostgreSQL, Redis, Celery, and Nginx.

It is designed to provide:

- email-based login
- OTP-based authentication
- admin-controlled user approval
- folder-level access control for web users
- protected file downloads
- audit logging with Trace ID / journey tracking
- password expiry and password history control
- account unlock flow using security questions
- scheduled folder and file indexing from local and NAS storage

This README explains both:

1. how to deploy and operate the portal
2. how administrators and end users use the portal

---

## 2. High-Level Architecture

### Main components

- **Django web app**
  - authentication
  - admin portal
  - user portal
  - access control
  - audit trail
- **PostgreSQL**
  - application database
- **Redis**
  - Celery broker and result backend
- **Celery worker**
  - sends OTP email
  - sends reminders
  - performs cleanup tasks
  - runs storage scan tasks
- **Celery Beat**
  - scheduled jobs
- **Nginx**
  - HTTPS reverse proxy
  - static/media serving
  - protected download via internal redirect

### Main storage paths

The application uses two storage roots:

- `LOCAL_STORAGE_ROOT=/PATH/local`
- `NAS_STORAGE_ROOT=/PATH/nas`

These are mounted into the containers and scanned into the database.

---

## 3. Container Services

The project starts the following services:

- `db` → PostgreSQL 17
- `redis` → Redis 7
- `web` → Django + Gunicorn
- `celery` → background worker
- `celery-beat` → scheduler
- `nginx` → reverse proxy and static/protected file serving

### Runtime behavior of `web`

When the `web` container starts, it automatically:

1. waits for database
2. runs migrations
3. runs `collectstatic`
4. seeds security questions
5. runs `create_initial_superadmin`
6. starts Gunicorn

That means a basic initial bootstrap can be done automatically if `.env` is configured properly.

---

## 4. Main URLs

### Authentication

- Login: `/auth/login/`
- Register: `/auth/register/`
- OTP Verification: `/auth/otp/`
- Unlock Account: `/auth/unlock/`
- Unlock OTP: `/auth/unlock/otp/`
- Expired Password Reset: `/auth/password/expired/`
- Logout: `/auth/logout/`

### Admin Portal

- Dashboard: `/admin-portal/`
- Users: `/admin-portal/users/`
- Create Admin User: `/admin-portal/create-admin/`
- Folders: `/admin-portal/folders/`
- Create Folder: `/admin-portal/folders/create/`
- Delete Folder: `/admin-portal/folders/delete/`
- Upload File: `/admin-portal/files/upload/`
- Delete File: `/admin-portal/files/delete/`
- Grant Folder Permissions: `/admin-portal/permissions/`
- Revoke Folder Permissions: `/admin-portal/permissions/revoke/`
- Audit Logs: `/admin-portal/logs/`
- Journey Detail: `/admin-portal/journey/<trace_id>/`

### Web User Portal

- Dashboard: `/portal/`
- Folder Detail: `/portal/folders/<folder_id>/`
- Download File: `/portal/download/<file_id>/`
- Profile: `/portal/profile/`
- Change Password: `/portal/password/change/`
- Forced Password Reset: `/portal/password/forced/`

---

## 5. User Roles

The portal uses three functional roles.

### 5.1 Super Admin

Super Admin is the highest privileged role.

Main responsibilities:

- access full admin dashboard
- create admin users
- approve or reject web user registration
- disable, unblock, re-enable users with temporary password
- delete users
- create folders
- upload and delete files
- grant and revoke folder permissions
- view audit logs and journey details

### 5.2 Admin Read-only

Admin Read-only is a restricted admin role.

In principle this role is intended to be limited compared with Super Admin. However, you should review the current implementation carefully before production hardening, because some non-superadmin operational actions are still available through the current admin pages and views.

### 5.3 Web User

Web users are the normal end users of the portal.

Main responsibilities:

- self-register
- wait for admin approval
- log in with email + password + OTP
- browse only authorized folders
- download only authorized files
- manage profile and password
- use unlock flow when blocked

---

## 6. Account Statuses

Typical statuses used in the system:

- `PENDING_APPROVAL`
- `APPROVED`
- `BLOCKED`
- `SECURITY_BLOCKED`
- `DISABLED_PASSWORD_EXPIRED`
- `DISABLED_ADMIN`
- `REJECTED`
- `DELETED`

### Meaning summary

- **Pending Approval** → user registered, waiting for admin approval
- **Approved** → user can use the portal normally
- **Blocked** → login blocked because of wrong password attempts
- **Security Blocked** → unlock/security question flow failed, account blocked
- **Disabled - Password Expired** → password expired, account disabled until reset
- **Disabled by Admin** → admin manually disabled the account
- **Rejected** → registration was rejected by admin
- **Deleted** → account soft-deleted

---

## 7. Authentication Flow

### 7.1 Login flow

1. User opens login page
2. User enters email and password
3. If password is valid and account is allowed
4. OTP is created and emailed to the user
5. User enters OTP
6. Login completes successfully
7. User is routed to the correct portal based on role

### 7.2 Login protection

The portal includes:

- OTP verification
- failed login counting
- account block after repeated failures
- activity timeout middleware
- password expiry handling

### 7.3 Expired password flow

If the password is expired:

1. user enters valid email/password
2. portal does not complete login
3. OTP is sent
4. user is redirected to expired password reset page
5. user sets a new password
6. user logs in again

### 7.4 Account unlock flow

If the user is blocked:

1. open `/auth/unlock/`
2. enter email
3. answer three security questions
4. if answers are correct, OTP is sent
5. verify OTP
6. account is unlocked

If security answers fail, the account may become `SECURITY_BLOCKED`.

---

## 8. Registration Flow

### 8.1 Web user registration

A web user registers from `/auth/register/`.

Registration form includes:

- full name
- email
- password
- confirm password
- three different security questions
- three answers

### 8.2 After registration

- account is created in pending state
- admin must approve it from the Users page
- until approved, user cannot access the portal

---

## 9. Admin Portal Usage Guide

## 9.1 Admin Dashboard

The dashboard is the central entry point for administrators.

It provides quick navigation to:

- Users
- Folders
- Grant Folder Permissions
- Revoke Folder Permissions
- Audit Logs

It also shows summary counts such as:

- pending users
- web users
- admin users
- folders
- files

---

## 9.2 Users Page

Purpose:

- manage all registered users
- filter by status
- search by email
- approve, reject, disable, unblock, re-enable, delete

### Common actions

#### Approve a pending user

1. go to Users page
2. filter by `Pending Approval`
3. click `Approved`

#### Reject a pending user

1. go to Users page
2. filter by `Pending Approval`
3. click `Reject`

#### Disable an approved user

1. filter by `Approved`
2. click `Disabled`

#### Set temporary password / re-enable user

1. find blocked / expired / disabled user
2. click `Temp Password`
3. portal sets a new temporary password
4. user must change password after login

#### Delete a web user

For web users, delete includes confirmation logic and also removes folder permissions, so a recreated user does not inherit old access.

---

## 9.3 Create Admin User

Purpose:

- create Super Admin or Admin Read-only users

Typical flow:

1. open `Create Admin User`
2. enter full name
3. enter email
4. choose role
5. enter password
6. click `Create`

If the email previously existed in deleted state, the account may be restored depending on the current logic.

---

## 9.4 Folders Page

Purpose:

- view indexed folders from configured storage roots
- create folders
- upload files
- delete folders
- delete files

Important note:

The page reads folders from the **database index**, not directly from the filesystem.

So if folders exist on disk but not in the database, they will not appear until storage roots are scanned.

---

## 9.5 Create Folder

Purpose:

- create a new folder under a selected storage root

Flow:

1. go to Folders → `Create Folder`
2. choose storage root
3. enter display name
4. enter relative path
5. click `Create`

Current behavior keeps the user on the same page after creation and shows success on the same page.

---

## 9.6 Upload File

Purpose:

- upload one or multiple files into a selected folder

Current implementation supports:

- multi-file upload
- total upload limit controlled by `.env`
- client-side size validation popup
- server-side validation

### Upload limit

Controlled by:

- `FILEPORTAL_UPLOAD_MAX_BYTES`

Example for 10 GB:

```env
FILEPORTAL_UPLOAD_MAX_BYTES=10737418240
```

### Important infrastructure note

Large uploads require:

- correct Nginx `client_max_body_size`
- correct `client_body_temp_path`
- enough disk space for container storage and temp upload area

---

## 9.7 Delete Folder

Purpose:

- delete a folder from filesystem and mark it inactive in DB

Rules:

- root folders cannot be deleted
- folder must be empty first
- active child folders and files must be removed/moved first

---

## 9.8 Delete File

Purpose:

- remove a file from filesystem and mark it inactive in DB

---

## 9.9 Grant Folder Permissions

Purpose:

- assign folder access to users

Flow:

1. open `Grant Folder Permissions`
2. choose folder
3. choose user
4. click `Grant Read Access`

The user dropdown should only show allowed user statuses based on the current logic.

The page also supports:

- search by email
- current permissions list
- pagination

---

## 9.10 Revoke Folder Permissions

Purpose:

- revoke existing folder access

Flow:

1. open `Revoke Folder Permissions`
2. find permission row
3. click `Delete`

This removes the permission and may also revoke inherited subtree access depending on the path and recursive revoke logic.

---

## 9.11 Audit Logs

Purpose:

- review security and operational events
- filter by Trace ID
- search by date
- search by date/time range
- drill into journey details

### Trace ID

Trace ID groups actions within one session/journey so you can follow:

- login attempts
- OTP events
- user actions
- logout / end state

---

## 10. Web User Portal Usage Guide

## 10.1 Dashboard

Purpose:

- show only folders that the user is directly permitted to access

The dashboard lists authorized top-level or directly granted folders.

---

## 10.2 Folder Detail

Purpose:

- open a folder
- view visible child folders
- view files

Access is checked against granted folder permissions and folder ancestry.

If unauthorized access is attempted:

- access is denied
- audit event is created
- admin alert email can be sent

---

## 10.3 Download File

Purpose:

- securely download authorized files

The portal uses Django authorization plus Nginx protected internal redirect.

Files are not exposed directly as public file URLs.

---

## 10.4 Profile Page

Purpose:

- view user details
- see password expiry date
- change password

Profile typically shows:

- full name
- email
- password expiry time

---

## 10.5 Change Password

Purpose:

- change password with current password + OTP verification

Typical flow:

1. open profile
2. go to change password page
3. enter current password
4. enter new password
5. confirm new password
6. enter OTP
7. submit

---

## 10.6 Forced Password Reset

This page is used when the user must change password before continuing.

---

## 11. Email / OTP System

The portal uses Celery tasks to send:

- login OTP
- unlock OTP
- password reminders
- password expiry alerts
- generic emails
- admin alert emails

### Important SMTP note

If you use normal Microsoft 365 authenticated SMTP submission, use:

```env
EMAIL_HOST=smtp.office365.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your_mailbox@example.com
EMAIL_HOST_PASSWORD=your_password_or_app_password
DEFAULT_FROM_EMAIL=your_mailbox@example.com
```

Do **not** use port `22` for SMTP.

If you want passwordless sending through Microsoft 365 relay, use a proper Exchange Online relay/connector design with the correct relay host and port, normally port `25`, and only after mail-flow connector configuration is completed.

---

## 12. Environment Variables

Below are the important `.env` values.

### Django

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DJANGO_SUPERUSER_EMAIL`
- `DJANGO_SUPERUSER_FULL_NAME`
- `DJANGO_SUPERUSER_PASSWORD`

### Database

- `DATABASE_NAME`
- `DATABASE_USER`
- `DATABASE_PASSWORD`
- `DATABASE_HOST`
- `DATABASE_PORT`

### Redis / Celery

- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`

### Email

- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_USE_TLS`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `DEFAULT_FROM_EMAIL`

### Portal controls

- `FILEPORTAL_SESSION_TIMEOUT_MINUTES`
- `FILEPORTAL_OTP_EXPIRY_SECONDS`
- `FILEPORTAL_OTP_MAX_ATTEMPTS`
- `FILEPORTAL_UPLOAD_MAX_BYTES`
- `LOCAL_STORAGE_ROOT`
- `NAS_STORAGE_ROOT`
- `PROTECTED_NGINX_PREFIX`

---

## 13. First-Time Setup

## 13.1 Prepare host paths

Ensure these host paths exist:

```bash
mkdir -p /PATH/local
mkdir -p /PATH/nas
mkdir -p /PATH/nginx_client_temp
```

## 13.2 Configure `.env`

Create and populate `.env` with correct values.

## 13.3 Start the stack

Using Podman Compose:

```bash
cd /PATH/Application/fileportal_prod
podman-compose up -d --build
```

Using Docker Compose:

```bash
cd /PATH/Application/fileportal_prod
docker compose up -d --build
```

## 13.4 Verify containers

```bash
podman-compose ps
```

## 13.5 Verify application bootstrap

The `web` service will automatically:

- run migrations
- collect static
- seed security questions
- create initial superadmin

If needed, run manually:

```bash
podman-compose exec web python manage.py seed_security_questions
podman-compose exec web python manage.py create_initial_superadmin
```

---

## 14. Storage Root and Folder Scan

After a fresh database, your folders may not appear immediately even if they exist on disk.

That is because folders/files are shown from indexed DB records.

### Required conditions

1. `StorageRoot` records must exist
2. storage scan must run

### Scan job

Celery Beat schedules `scan-storage-roots` every 600 seconds.

### Manual scan if needed

```bash
podman-compose exec web python manage.py shell
```

Then run something like:

```python
from storage_index.models import StorageRoot
from storage_index.services import scan_storage_root

for root in StorageRoot.objects.filter(is_active=True):
    scan_storage_root(root)
```

---

## 15. Branding / Static Files

For auth-page assets like the logo, keep them inside the Django app static path, for example:

```bash
app/accounts/static/images/fiftytwo_logo.png
```

Then run:

```bash
podman-compose exec web python manage.py collectstatic --noinput
```

If the browser shows alt text instead of the logo, usually the file exists in source static path but was not collected into `staticfiles` yet.

---

## 16. Common Operational Commands

### Rebuild stack

```bash
podman-compose up -d --build
```

### Check web logs

```bash
podman-compose logs --tail=100 web
```

### Check Celery logs

```bash
podman-compose logs --tail=100 celery
podman-compose logs --tail=100 celery-beat
```

### Check Nginx logs

```bash
podman-compose logs --tail=100 nginx
```

### Open Django shell

```bash
podman-compose exec web python manage.py shell
```

### Collect static manually

```bash
podman-compose exec web python manage.py collectstatic --noinput
```

---

## 17. Common Troubleshooting

## 17.1 Login says “Invalid credentials” after rebuild

Possible cause:

- fresh database
- initial superadmin not created yet

Fix:

```bash
podman-compose exec web python manage.py create_initial_superadmin
```

---

## 17.2 OTP is logged as sent but email is not received

Check:

- `.env` email host/port
- mailbox credentials
- Celery worker logs
- Microsoft 365 SMTP/relay setup

Normal working SMTP submission example:

```env
EMAIL_HOST=smtp.office365.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your_mailbox@example.com
EMAIL_HOST_PASSWORD=your_password_or_app_password
DEFAULT_FROM_EMAIL=your_mailbox@example.com
```

---

## 17.3 Folders exist on disk but do not appear in the portal

Possible cause:

- fresh DB
- `StorageRoot` rows missing
- scan not run yet

Fix:

- ensure storage roots exist
- trigger manual scan
- verify Celery Beat and worker are running

---

## 17.4 Large file upload fails

Check:

- `FILEPORTAL_UPLOAD_MAX_BYTES`
- Nginx `client_max_body_size`
- Nginx `client_body_temp_path`
- free space on temp path
- Gunicorn timeout
- Podman container storage size

Recommended upload-related settings:

- app limit in `.env`
- Nginx slightly above app limit
- Gunicorn timeout aligned with Nginx

---

## 17.5 Podman storage fills `/var`

If `/var` is small and Podman storage lives under `/var/lib/containers`, container rebuilds and large workloads can fail.

Recommended long-term solution:

- move Podman graphroot to `/deployment/containers/storage`
- keep Nginx temp upload path on `/deployment/nginx_client_temp`

---

## 18. Security Notes

This portal already includes several good security controls:

- email-based authentication
- OTP verification
- password complexity
- password history checks
- password expiry
- account block / unlock controls
- session timeout middleware
- audit logging
- protected internal download flow

Before public internet exposure, still review:

- TLS certificate management
- reverse proxy hardening
- SMTP security and sender policy
- antivirus / content scanning if required
- external rate limiting / WAF
- off-box log forwarding if required
- least-privilege container runtime settings

---

## 19. Recommended Maintenance Routine

Daily / regular checks:

- verify web, celery, celery-beat, nginx containers are healthy
- verify OTP email works
- verify storage scans are running
- review audit logs
- review disk space on:
  - `/var`
  - `/deployment`
  - container storage
  - Nginx temp upload path

---

## 20. Final Notes

This portal is database-driven for users, permissions, audit logs, and storage indexing. That means filesystem state alone is not enough after a rebuild or DB reset.

Always remember these dependencies:

- user access depends on DB records
- folders shown in portal depend on indexed DB rows
- email/OTP depends on Celery + SMTP config
- file download depends on Django authorization + Nginx protected path

If you change infrastructure, mail flow, storage paths, or container storage, validate the portal again end to end.

---

## 21. Suggested Validation Checklist After Deployment

1. open login page
2. verify logo and static files load
3. log in as Super Admin
4. create Admin Read-only user
5. register a test Web User
6. approve the user from Users page
7. verify OTP delivery
8. verify folder scan is working
9. grant folder permission
10. log in as Web User
11. verify folder visibility and file download
12. verify audit log entries and Trace ID grouping
13. verify unlock flow
14. verify password change flow
15. verify large file upload behavior within configured limit

