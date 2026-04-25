from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime, time as dt_time

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string

from .forms import (
    AppSettingUpdateForm,
    CreateAdminUserForm,
    FileUploadForm,
    FolderCreateForm,
    PermissionAssignmentForm,
    DeleteFolderForm,
    DeleteFileForm,
)

from accounts.enums import AccountStatus, UserRole
from accounts.models import User
from accounts.services import (
    approve_web_user,
    reject_web_user,
    set_new_password,
    soft_delete_user,
    disable_user_by_admin,
    mark_rejected_user_reregisterable,
)
from audittrail.models import AuditEvent, UserSessionJourney
from audittrail.services import create_audit_event
from settings_app.models import AppSetting
from storage_index.models import FileItem, Folder, FolderUserPermission
from storage_index.services import revoke_folder_permission_recursive


User = get_user_model()


def _current_query_without_page(request):
    query = request.GET.copy()
    query.pop('page', None)
    return query.urlencode()


def admin_required(view_func):
    @login_required
    def _wrapped(request, *args, **kwargs):
        if request.user.profile.role not in {UserRole.SUPER_ADMIN, UserRole.ADMIN_READONLY}:
            messages.error(request, 'Admin portal access denied.')
            return redirect('accounts:post_login_router')
        return view_func(request, *args, **kwargs)
    return _wrapped


def super_admin_required(view_func):
    @admin_required
    def _wrapped(request, *args, **kwargs):
        if request.user.profile.role != UserRole.SUPER_ADMIN:
            messages.error(request, 'Super admin privilege required.')
            return redirect('portal_admin:dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped


def can_manage_target_user(actor, target_user) -> bool:
    if actor.profile.role == UserRole.SUPER_ADMIN:
        return True
    if actor.profile.role == UserRole.ADMIN_READONLY:
        return target_user.profile.role != UserRole.SUPER_ADMIN
    return False


@admin_required
def dashboard(request):
    return render(request, 'portal_admin/dashboard.html', {
        'pending_count': User.objects.filter(profile__account_status=AccountStatus.PENDING_APPROVAL).count(),
        'web_users_count': User.objects.filter(profile__role=UserRole.WEB_USER).count(),
        'admin_users_count': User.objects.filter(
            profile__role__in=[UserRole.SUPER_ADMIN, UserRole.ADMIN_READONLY]
        ).count(),
        'folder_count': Folder.objects.filter(is_active=True).count(),
        'file_count': FileItem.objects.filter(is_active=True).count(),
    })


@admin_required
def approve_user(request, user_id):
    return approve_user_row(request, user_id)


@admin_required
def reject_user(request, user_id):
    return reject_user_row(request, user_id)


@admin_required
def approve_user_row(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if not can_manage_target_user(request.user, user):
        messages.error(request, 'You are not allowed to approve this user.')
        return redirect('portal_admin:user_list')

    approve_web_user(user, request.user, request=request)
    messages.success(request, 'User approved.')
    return redirect(f"{reverse('portal_admin:user_list')}?status={AccountStatus.PENDING_APPROVAL}")


@admin_required
def reject_user_row(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if not can_manage_target_user(request.user, user):
        messages.error(request, 'You are not allowed to reject this user.')
        return redirect('portal_admin:user_list')

    reject_web_user(user, request.user, request=request)
    messages.success(request, 'User rejected.')
    return redirect(f"{reverse('portal_admin:user_list')}?status={AccountStatus.PENDING_APPROVAL}")


@admin_required
def disable_user_row(request, user_id):
    user = get_object_or_404(User, pk=user_id)

    if not can_manage_target_user(request.user, user):
        messages.error(request, 'You are not allowed to disable this user.')
        return redirect('portal_admin:user_list')

    if user.profile.account_status != AccountStatus.APPROVED:
        messages.error(request, 'Only approved users can be disabled.')
        return redirect('portal_admin:user_list')

    disable_user_by_admin(user, request.user, request=request)
    messages.success(request, 'User disabled by admin.')
    return redirect(f"{reverse('portal_admin:user_list')}?status={AccountStatus.APPROVED}")


@admin_required
def delete_user_row(request, user_id):
    target_user = get_object_or_404(User, pk=user_id)

    if target_user == request.user:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('portal_admin:user_list')

    if not can_manage_target_user(request.user, target_user):
        messages.error(request, 'You are not allowed to delete this user.')
        return redirect('portal_admin:user_list')

    # WEB_USER delete must be confirmed via POST only
    if target_user.profile.role == UserRole.WEB_USER:
        if request.method != 'POST':
            messages.error(request, 'Invalid request method for deleting web user.')
            return redirect('portal_admin:user_list')

        confirm_value = request.POST.get('confirm_delete', '').strip().lower()
        if confirm_value != 'yes':
            messages.info(request, 'User delete cancelled.')
            return redirect('portal_admin:user_list')

    try:
        soft_delete_user(target_user, request.user, request=request)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('portal_admin:user_list')

    messages.success(request, f'User {target_user.email} deleted successfully.')
    return redirect(f"{reverse('portal_admin:user_list')}?status={AccountStatus.APPROVED}")


@admin_required
def reregister_user_row(request, user_id):
    user = get_object_or_404(User, pk=user_id)

    if not can_manage_target_user(request.user, user):
        messages.error(request, 'You are not allowed to change this user.')
        return redirect('portal_admin:user_list')

    if user.profile.role != UserRole.WEB_USER or user.profile.account_status != AccountStatus.REJECTED:
        messages.error(request, 'Only rejected web users can be marked for re-registration.')
        return redirect('portal_admin:user_list')

    mark_rejected_user_reregisterable(user, request.user, request=request)
    messages.success(request, 'User can now register again from the Register page.')
    return redirect(f"{reverse('portal_admin:user_list')}?status={AccountStatus.REJECTED}")


@admin_required
def user_list(request):
    selected_status = request.GET.get('status', AccountStatus.APPROVED)
    email_query = request.GET.get('email', '').strip()

    users = User.objects.select_related('profile').all()

    # Email search works independently
    if email_query:
        users = users.filter(email__icontains=email_query)
    else:
        if selected_status:
            users = users.filter(profile__account_status=selected_status)

    users = users.order_by('email')

    return render(request, 'portal_admin/user_list.html', {
        'users': users,
        'selected_status': selected_status,
        'email_query': email_query,
        'status_choices': AccountStatus.choices,
    })


@super_admin_required
def create_admin_user(request):
    form = CreateAdminUserForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email'].strip().lower()
        full_name = form.cleaned_data['full_name']
        role = form.cleaned_data['role']
        password = form.cleaned_data['password']

        existing_user = User.objects.filter(email=email).select_related('profile').first()

        if existing_user:
            if existing_user.profile.account_status == AccountStatus.DELETED or not existing_user.is_active:
                existing_user.is_active = True
                existing_user.is_staff = True
                existing_user.set_password(password)
                existing_user.save(update_fields=['is_active', 'is_staff', 'password'])

                existing_user.profile.full_name = full_name
                existing_user.profile.role = role
                existing_user.profile.account_status = AccountStatus.APPROVED
                existing_user.profile.enabled_by = request.user
                existing_user.profile.enabled_at = timezone.now()
                existing_user.profile.must_change_password = False
                existing_user.profile.set_password_expiry(90)
                existing_user.profile.save()

                create_audit_event(
                    user=request.user,
                    request=request,
                    action_type='USER_CREATED',
                    target_type='USER',
                    target_id=str(existing_user.id),
                    target_name=existing_user.email,
                    status='SUCCESS',
                    message='Deleted user restored as admin user.',
                )
                messages.success(request, f'Existing deleted user {existing_user.email} restored successfully.')
                return redirect('portal_admin:user_list')

            messages.error(request, f'User with email {email} already exists.')
            return render(request, 'portal_admin/form.html', {'form': form, 'title': 'Create Admin User'})

        user = User.objects.create_user(email=email, password=password)
        user.is_active = True
        user.is_staff = True
        user.save(update_fields=['is_active', 'is_staff'])

        user.profile.full_name = full_name
        user.profile.role = role
        user.profile.account_status = AccountStatus.APPROVED
        user.profile.enabled_by = request.user
        user.profile.enabled_at = timezone.now()
        user.profile.must_change_password = False
        user.profile.set_password_expiry(90)
        user.profile.save()

        create_audit_event(
            user=request.user,
            request=request,
            action_type='USER_CREATED',
            target_type='USER',
            target_id=str(user.id),
            target_name=user.email,
            status='SUCCESS',
            message='Admin user created.',
        )
        messages.success(request, 'Admin user created.')
        return redirect('portal_admin:user_list')

    return render(request, 'portal_admin/form.html', {'form': form, 'title': 'Create Admin User'})


@admin_required
def folder_list(request):
    folder_qs = Folder.objects.select_related('storage_root').filter(is_active=True).order_by(
        'storage_root__storage_type',
        'relative_path',
    )
    paginator = Paginator(folder_qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'portal_admin/folder_list.html', {
        'folders': page_obj.object_list,
        'page_obj': page_obj,
        'current_query': _current_query_without_page(request),
    })


@super_admin_required
def create_folder(request):
    if request.method == 'POST':
        form = FolderCreateForm(request.POST)
        if form.is_valid():
            storage_root = form.cleaned_data['storage_root']
            relative_path = form.cleaned_data['relative_path'].strip('/').strip()
            absolute_path = str(Path(storage_root.absolute_root_path) / relative_path)
            Path(absolute_path).mkdir(parents=True, exist_ok=True)

            parent = None
            parent_path = str(Path(absolute_path).parent)
            if parent_path != storage_root.absolute_root_path:
                parent = Folder.objects.filter(absolute_path=parent_path).first()

            Folder.objects.update_or_create(
                absolute_path=absolute_path,
                defaults={
                    'storage_root': storage_root,
                    'parent': parent,
                    'display_name': form.cleaned_data['display_name'],
                    'relative_path': relative_path,
                    'created_by': request.user,
                    'is_active': True,
                },
            )

            create_audit_event(
                user=request.user,
                request=request,
                action_type='FOLDER_CREATED',
                target_type='FOLDER',
                target_name=relative_path,
                status='SUCCESS',
                message='Folder created.',
            )

            messages.success(request, 'Folder created.')

            # Keep user on the same page with a fresh empty form
            form = FolderCreateForm()
            return render(request, 'portal_admin/form.html', {
                'form': form,
                'title': 'Create Folder',
            })
    else:
        form = FolderCreateForm()

    return render(request, 'portal_admin/form.html', {
        'form': form,
        'title': 'Create Folder',
    })


@admin_required
def upload_file(request):
    form = FileUploadForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        folder = form.cleaned_data['folder']
        uploaded_files = request.FILES.getlist('upload_file')

        if not uploaded_files:
            messages.error(request, 'Please select at least one file.')
            return render(request, 'portal_admin/form.html', {
                'form': form,
                'title': 'Upload File',
                'upload_max_bytes': settings.FILEPORTAL_UPLOAD_MAX_BYTES,
            })

        total_size = sum(f.size for f in uploaded_files)
        max_bytes = getattr(settings, 'FILEPORTAL_UPLOAD_MAX_BYTES', 10737418240)

        if total_size > max_bytes:
            messages.error(
                request,
                f'Total selected file size exceeds the allowed limit of {max_bytes // (1024 * 1024 * 1024)} GB.'
            )
            return render(request, 'portal_admin/form.html', {
                'form': form,
                'title': 'Upload File',
                'upload_max_bytes': max_bytes,
            })

        uploaded_count = 0

        for uploaded in uploaded_files:
            target_path = Path(folder.absolute_path) / uploaded.name

            with open(target_path, 'wb+') as fh:
                for chunk in uploaded.chunks():
                    fh.write(chunk)

            create_audit_event(
                user=request.user,
                request=request,
                action_type='FILE_UPLOADED',
                target_type='FILE',
                target_name=uploaded.name,
                status='SUCCESS',
                message='File uploaded by admin.',
            )
            uploaded_count += 1

        messages.success(
            request,
            f'{uploaded_count} file(s) uploaded successfully. The scanner will index them.'
        )
        return redirect('portal_admin:folder_list')

    return render(request, 'portal_admin/form.html', {
        'form': form,
        'title': 'Upload File',
        'upload_max_bytes': settings.FILEPORTAL_UPLOAD_MAX_BYTES,
    })


@admin_required
def delete_folder(request):
    form = DeleteFolderForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        folder = form.cleaned_data['folder']

        if folder.parent is None or folder.relative_path in {'', '.'}:
            messages.error(request, 'Root folders cannot be deleted.')
            return redirect('portal_admin:delete_folder')

        active_child_folders = Folder.objects.filter(parent=folder, is_active=True).count()
        active_files = FileItem.objects.filter(folder=folder, is_active=True).count()

        if active_child_folders > 0 or active_files > 0:
            messages.error(request, 'Folder is not empty. Delete or move all files/sub-folders first.')
            return redirect('portal_admin:delete_folder')

        try:
            if os.path.isdir(folder.absolute_path):
                os.rmdir(folder.absolute_path)
        except OSError as exc:
            messages.error(request, f'Could not delete folder from filesystem: {exc}')
            return redirect('portal_admin:delete_folder')

        folder.is_active = False
        folder.save(update_fields=['is_active', 'updated_at'])

        create_audit_event(
            user=request.user,
            request=request,
            action_type='FOLDER_DELETED',
            target_type='FOLDER',
            target_id=str(folder.id),
            target_name=folder.relative_path,
            status='SUCCESS',
            message='Folder deleted from filesystem and marked inactive in DB.',
        )

        messages.success(request, f'Folder deleted: {folder.relative_path}')
        return redirect('portal_admin:folder_list')

    return render(request, 'portal_admin/form.html', {'form': form, 'title': 'Delete Folder'})


@admin_required
def delete_file(request):
    form = DeleteFileForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        file_item = form.cleaned_data['file_item']

        try:
            if os.path.isfile(file_item.absolute_path):
                os.remove(file_item.absolute_path)
        except OSError as exc:
            messages.error(request, f'Could not delete file from filesystem: {exc}')
            return redirect('portal_admin:delete_file')

        file_item.is_active = False
        file_item.save(update_fields=['is_active', 'updated_at'])

        create_audit_event(
            user=request.user,
            request=request,
            action_type='FILE_DELETED',
            target_type='FILE',
            target_id=str(file_item.id),
            target_name=file_item.file_name,
            status='SUCCESS',
            message='File deleted from filesystem and marked inactive in DB.',
        )

        messages.success(request, f'File deleted: {file_item.file_name}')
        return redirect('portal_admin:folder_list')

    return render(request, 'portal_admin/form.html', {'form': form, 'title': 'Delete File'})


@admin_required
def permissions_view(request):
    form = PermissionAssignmentForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        perm, created = FolderUserPermission.objects.get_or_create(
            folder=form.cleaned_data['folder'],
            user=form.cleaned_data['user'],
            defaults={'created_by': request.user, 'permission_type': 'read'}
        )
        create_audit_event(
            user=request.user,
            request=request,
            action_type='PERMISSION_GRANTED',
            target_type='FOLDER',
            target_id=str(perm.folder.id),
            target_name=perm.folder.display_name,
            status='SUCCESS',
            message=f'Folder read permission granted to {perm.user.email}.',
        )
        messages.success(request, 'Permission assigned.')
        return redirect('portal_admin:permissions_view')

    search_email = request.GET.get('email', '').strip().lower()
    searched_user = None
    search_message = ''

    permissions_qs = FolderUserPermission.objects.select_related(
        'folder',
        'folder__storage_root',
        'user',
    ).order_by('user__email', 'folder__storage_root__storage_type', 'folder__relative_path')

    if search_email:
        searched_user = User.objects.filter(email=search_email).first()

        if searched_user:
            permissions_qs = permissions_qs.filter(user=searched_user)
            if not permissions_qs.exists():
                search_message = 'This user has no access to any of the folders and files.'
        else:
            permissions_qs = FolderUserPermission.objects.none()
            search_message = 'This user has no access to any of the folders and files.'

    paginator = Paginator(permissions_qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'portal_admin/permissions.html', {
        'form': form,
        'permissions': page_obj.object_list,
        'page_obj': page_obj,
        'current_query': _current_query_without_page(request),
        'search_email': search_email,
        'searched_user': searched_user,
        'search_message': search_message,
    })


@super_admin_required
def settings_view(request):
    setting, _ = AppSetting.objects.get_or_create(
        key='session_timeout_minutes',
        defaults={'value': '5'},
    )
    form = AppSettingUpdateForm(request.POST or None, instance=setting)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.updated_by = request.user
        obj.save()
        create_audit_event(
            user=request.user,
            request=request,
            action_type='APP_SETTING_CHANGED',
            target_type='SETTING',
            target_name=obj.key,
            status='SUCCESS',
            message=f'Setting updated to {obj.value}.',
        )
        messages.success(request, 'Setting updated.')
        return redirect('portal_admin:settings_view')
    return render(request, 'portal_admin/form.html', {'form': form, 'title': 'Settings'})


@admin_required
def unblock_user(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if not can_manage_target_user(request.user, user):
        messages.error(request, 'You are not allowed to unblock this user.')
        return redirect('portal_admin:user_list')

    profile = user.profile
    profile.failed_login_count = 0
    profile.blocked_until = None
    profile.security_blocked_until = None
    profile.account_status = AccountStatus.APPROVED
    profile.save(update_fields=[
        'failed_login_count',
        'blocked_until',
        'security_blocked_until',
        'account_status',
        'updated_at',
    ])

    create_audit_event(
        user=request.user,
        request=request,
        action_type='USER_UNBLOCKED',
        target_type='USER',
        target_id=str(user.id),
        target_name=user.email,
        status='SUCCESS',
        message='User manually unblocked by admin.',
    )
    messages.success(request, 'User unblocked.')
    return redirect(f"{reverse('portal_admin:user_list')}?status={AccountStatus.APPROVED}")


@admin_required
def enable_with_temp_password(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if not can_manage_target_user(request.user, user):
        messages.error(request, 'You are not allowed to enable this user.')
        return redirect('portal_admin:user_list')

    temp_password = get_random_string(
        10,
        allowed_chars='ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789@#$_-'
    )

    try:
        user.is_active = True
        user.is_staff = user.profile.role in {UserRole.SUPER_ADMIN, UserRole.ADMIN_READONLY}
        user.save(update_fields=['is_active', 'is_staff'])

        set_new_password(user, temp_password, changed_by=request.user, force_change=True, request=request)

        user.profile.account_status = AccountStatus.APPROVED
        user.profile.enabled_by = request.user
        user.profile.enabled_at = timezone.now()
        user.profile.must_change_password = True
        user.profile.save(update_fields=[
            'account_status',
            'enabled_by',
            'enabled_at',
            'must_change_password',
            'updated_at',
        ])

        create_audit_event(
            user=request.user,
            request=request,
            action_type='USER_ENABLED_TEMP_PASSWORD',
            target_type='USER',
            target_id=str(user.id),
            target_name=user.email,
            status='SUCCESS',
            message='Temporary password set and user enabled.',
        )
        messages.success(request, f'Temporary password set for {user.email}: {temp_password}')
    except ValidationError as exc:
        messages.error(request, f'Could not set temporary password: {exc}')
    except Exception as exc:
        messages.error(request, f'Unexpected error while enabling user: {exc}')

    return redirect(f"{reverse('portal_admin:user_list')}?status={AccountStatus.APPROVED}")


@admin_required
def revoke_folder_permission_view(request):
    permission_qs = FolderUserPermission.objects.select_related(
        'folder',
        'folder__storage_root',
        'user',
    ).order_by('user__email', 'folder__storage_root__storage_type', 'folder__relative_path')

    paginator = Paginator(permission_qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'portal_admin/revoke_permission.html', {
        'current_permissions': page_obj.object_list,
        'page_obj': page_obj,
        'current_query': _current_query_without_page(request),
    })


@admin_required
def revoke_permission_row(request, perm_id):
    perm = get_object_or_404(
        FolderUserPermission.objects.select_related('folder', 'user'),
        pk=perm_id,
    )

    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('portal_admin:revoke_folder_permission')

    folder = perm.folder
    user = perm.user

    deleted_count = revoke_folder_permission_recursive(folder, user)

    create_audit_event(
        user=request.user,
        request=request,
        action_type='PERMISSION_REVOKED',
        target_type='FOLDER_PERMISSION',
        target_id=str(folder.id),
        target_name=f'{user.email} -> {folder.display_name}',
        status='SUCCESS',
        message=f"Revoked permission from '{folder.relative_path}' for '{user.email}'. Removed {deleted_count} permission row(s).",
    )

    messages.success(
        request,
        f"Revoked permission for {user.email} from '{folder.relative_path}'. Removed {deleted_count} permission row(s)."
    )
    return redirect('portal_admin:revoke_folder_permission')


@admin_required
def audit_logs(request):
    logs_qs = AuditEvent.objects.select_related('user').all().order_by('-created_at')

    trace_id_query = request.GET.get('trace_id', '').strip()

    search_date = request.GET.get('search_date', '').strip()

    from_date = request.GET.get('from_date', '').strip()
    from_time = request.GET.get('from_time', '').strip()
    to_date = request.GET.get('to_date', '').strip()
    to_time = request.GET.get('to_time', '').strip()

    if trace_id_query:
        logs_qs = logs_qs.filter(trace_id__icontains=trace_id_query)

    try:
        if search_date:
            start_dt = timezone.make_aware(
                datetime.combine(datetime.fromisoformat(search_date).date(), dt_time(0, 0, 0))
            )
            end_dt = timezone.make_aware(
                datetime.combine(datetime.fromisoformat(search_date).date(), dt_time(23, 59, 59))
            )
            logs_qs = logs_qs.filter(created_at__gte=start_dt, created_at__lte=end_dt)

        elif from_date or to_date:
            if from_date:
                start_time = dt_time.fromisoformat(from_time) if from_time else dt_time(0, 0, 0)
                start_dt = timezone.make_aware(
                    datetime.combine(datetime.fromisoformat(from_date).date(), start_time)
                )
                logs_qs = logs_qs.filter(created_at__gte=start_dt)

            if to_date:
                end_time = dt_time.fromisoformat(to_time) if to_time else dt_time(23, 59, 59)
                end_dt = timezone.make_aware(
                    datetime.combine(datetime.fromisoformat(to_date).date(), end_time)
                )
                logs_qs = logs_qs.filter(created_at__lte=end_dt)

    except ValueError:
        messages.error(request, 'Invalid date/time input.')

    paginator = Paginator(logs_qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'portal_admin/audit_logs.html', {
        'logs': page_obj.object_list,
        'page_obj': page_obj,
        'current_query': _current_query_without_page(request),
        'trace_id_query': trace_id_query,
        'search_date': search_date,
        'from_date': from_date,
        'from_time': from_time,
        'to_date': to_date,
        'to_time': to_time,
    })


@admin_required
def journey_detail(request, trace_id):
    journey = get_object_or_404(UserSessionJourney, trace_id=trace_id)
    logs = AuditEvent.objects.filter(trace_id=trace_id).order_by('created_at')
    return render(request, 'portal_admin/journey_detail.html', {
        'journey': journey,
        'logs': logs,
    })
