# Secure File Portal — Admin / Operator Guide

## 1. Purpose
This guide explains how administrators and operators deploy, manage, and support the Secure File Portal.

## 2. Platform Overview
Main components:
- Django web app
- PostgreSQL database
- Redis
- Celery worker
- Celery Beat
- Nginx reverse proxy

Main storage roots:
- `LOCAL_STORAGE_ROOT=/deployment/local`
- `NAS_STORAGE_ROOT=/deployment/nas`

The portal indexes folders and files from these storage roots into the database.

## 3. Main Admin URLs
- Admin Dashboard: `/admin-portal/`
- Users: `/admin-portal/users/`
- Create Admin User: `/admin-portal/create-admin/`
- Folders: `/admin-portal/folders/`
- Create Folder: `/admin-portal/folders/create/`
- Upload File: `/admin-portal/files/upload/`
- Delete Folder: `/admin-portal/folders/delete/`
- Delete File: `/admin-portal/files/delete/`
- Grant Folder Permissions: `/admin-portal/permissions/`
- Revoke Folder Permissions: `/admin-portal/permissions/revoke/`
- Audit Logs: `/admin-portal/logs/`

## 4. Roles
### Super Admin
Can:
- access full admin portal
- create admin users
- approve and reject registrations
- disable, enable, unblock, or delete users
- manage folders and files
- grant and revoke permissions
- review audit logs

### Admin Read-only
Operationally limited compared with Super Admin, but review actual implementation before production hardening because some management actions may still be available depending on current code.

### Web User
Can:
- register
- log in with OTP
- access only authorized folders/files
- manage own profile and password

## 5. First-Time Bootstrap
Typical startup behavior of the web service:
1. wait for DB
2. apply migrations
3. collect static files
4. seed security questions
5. create initial superadmin
6. start Gunicorn

If needed, manually bootstrap the initial admin:
```bash
podman-compose exec web python manage.py create_initial_superadmin
```

## 6. User Management
Open **Users** page to manage accounts.

Supported operational flows commonly include:
- approve pending users
- reject pending users
- disable approved users
- unblock blocked users
- set temporary password when enabling a user again
- soft-delete users

For web-user delete flow, the portal can show a confirmation popup and remove folder permissions along with delete.

## 7. Account Status Guidance
- `PENDING_APPROVAL`: awaiting admin action
- `APPROVED`: active
- `BLOCKED`: login failure block
- `SECURITY_BLOCKED`: unlock/security failure block
- `DISABLED_PASSWORD_EXPIRED`: password reset required
- `DISABLED_ADMIN`: manually disabled by admin
- `REJECTED`: registration rejected
- `DELETED`: soft deleted

## 8. Folder Management
The **Folders** page shows folder records from the database, not directly from disk.

This means:
- folders must exist on disk
- storage roots must exist in DB
- scan/index process must populate `Folder` and `FileItem` tables

### Create Folder
- creates the directory in the storage root
- creates or updates DB folder record
- writes audit log

### Upload File
- uploads file(s) to selected folder
- large upload behavior depends on Nginx, Django, and container storage settings

### Delete Folder
- only deletes eligible non-root folders
- folder must be empty
- DB record is marked inactive

### Delete File
- removes file from filesystem
- marks DB file record inactive

## 9. Storage Roots and Scanning
If the DB is recreated, folders may disappear from the portal even though they still exist on disk.

Why:
- Folders page reads from `Folder` table
- not from raw filesystem listing

### Ensure storage roots exist
Typical roots:
- `/deployment/local`
- `/deployment/nas`

### Manual scan example
```bash
podman-compose exec web python manage.py shell -c "
from storage_index.models import StorageRoot
from storage_index.services import scan_storage_root
for root in StorageRoot.objects.filter(is_active=True):
    scan_storage_root(root)
print('Scan complete')
"
```

## 10. Permission Management
### Grant Folder Permissions
Use **Grant Folder Permissions** to assign a folder to a user.

### Revoke Folder Permissions
Use **Revoke Folder Permissions** to remove folder access.

Important:
- portal permission model is DB-driven
- inherited or recursive behavior depends on current permission logic
- deleting a web user can also remove their folder permissions if configured that way

## 11. Audit Logs
The **Audit Logs** page lets you review:
- time
- trace ID
- user
- action
- status
- message

Trace IDs are useful for following a single user session journey from login to logout.

## 12. Email / OTP Operations
The portal uses Celery tasks for:
- OTP emails
- admin alert emails
- password expiry reminders
- simple notification emails

### Recommended SMTP submission config
```env
EMAIL_HOST=smtp.office365.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your_mailbox@example.com
EMAIL_HOST_PASSWORD='your_password_or_app_password'
DEFAULT_FROM_EMAIL=your_mailbox@example.com
```

### Important note
Using `*.mail.protection.outlook.com` is not a direct substitute for authenticated SMTP submission unless a proper Exchange Online relay connector is configured.

## 13. Container / Runtime Notes
Typical services:
- `db`
- `redis`
- `web`
- `celery`
- `celery-beat`
- `nginx`

### Check service status
```bash
podman-compose ps
```

### Tail logs
```bash
podman-compose logs --tail=100 web
podman-compose logs --tail=100 celery
podman-compose logs --tail=100 celery-beat
podman-compose logs --tail=100 nginx
```

## 14. Large Upload Operational Notes
Large uploads depend on all of these:
- browser-side validation
- Django upload checks
- Nginx `client_max_body_size`
- Nginx `client_body_temp_path`
- container storage availability
- Gunicorn timeout

Recommended patterns:
- keep upload limit in `.env`
- keep Nginx limit slightly above app limit
- keep temp upload path on large storage
- avoid container overlay exhaustion under `/var`

## 15. Podman Storage Recommendation
Do not keep Podman storage on a tiny `/var` filesystem if the portal handles large files.

Recommended:
- move Podman `graphroot` to a larger storage path such as `/deployment/containers/storage`

## 16. Static Files
When adding logos or other portal images:
- keep them in a Django app static path, for example:
  - `app/accounts/static/images/fiftytwo_logo.png`
- then run `collectstatic`

## 17. Useful Operational Commands
### Rebuild and restart
```bash
cd /deployment/Application/fileportal_prod
podman-compose up -d --build
```

### Collect static
```bash
podman-compose exec web python manage.py collectstatic --noinput
```

### Create initial superadmin
```bash
podman-compose exec web python manage.py create_initial_superadmin
```

### Check storage root / folder counts
```bash
podman-compose exec web python manage.py shell -c "
from storage_index.models import StorageRoot, Folder, FileItem
print('StorageRoot count =', StorageRoot.objects.count())
print('Folder count =', Folder.objects.count())
print('FileItem count =', FileItem.objects.count())
"
```

## 18. Common Troubleshooting
### Cannot log in with expected admin
- verify initial admin exists
- rerun `create_initial_superadmin` if needed
- verify DB persistence

### Folders do not appear in portal
- verify storage roots exist in DB
- run manual scan
- check Celery and beat

### OTP task received but email not delivered
- verify SMTP config
- tail celery logs during OTP trigger
- test submission host, port, TLS, and credentials

### Upload fails with `413 Request Entity Too Large`
- raise Nginx `client_max_body_size`
- ensure browser-side validation is present

### Upload fails with temp file or no-space errors
- verify `client_body_temp_path`
- verify container and host storage free space
- verify Podman storage location

### `podman-compose down` fails due to storage/database errors
- check `/var` usage
- check Podman storage location
- move Podman graphroot to larger storage if needed

## 19. Cleanup / Code Maintenance Guidance
Periodically review the codebase for:
- old unused templates
- duplicate admin action helpers
- orphan forms or services
- configs no longer used

Do cleanup carefully and verify routes, templates, and runtime behavior before removal.
