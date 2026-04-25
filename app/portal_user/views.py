from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.enums import UserRole
from accounts.forms import ForcedPasswordResetForm, PasswordChangeWithOtpForm
from accounts.models import OtpCode
from accounts.services import create_otp, set_new_password, verify_otp
from audittrail.services import create_audit_event
from storage_index.models import FileItem, Folder, FolderUserPermission


def web_user_required(view_func):
    @login_required
    def _wrapped(request, *args, **kwargs):
        if request.user.profile.role != UserRole.WEB_USER:
            return redirect('accounts:post_login_router')
        return view_func(request, *args, **kwargs)
    return _wrapped


def portal_account_required(view_func):
    @login_required
    def _wrapped(request, *args, **kwargs):
        if request.user.profile.role not in {UserRole.WEB_USER, UserRole.SUPER_ADMIN, UserRole.ADMIN_READONLY}:
            return redirect('accounts:post_login_router')
        return view_func(request, *args, **kwargs)
    return _wrapped


def _get_folder_ancestors(folder: Folder):
    ancestors = []
    current = folder
    while current is not None:
        ancestors.append(current)
        current = current.parent
    return ancestors


def _can_access_folder(user, folder: Folder) -> bool:
    ancestors = _get_folder_ancestors(folder)
    return FolderUserPermission.objects.filter(
        folder__in=ancestors,
        user=user,
        permission_type='read',
    ).exists()


@web_user_required
def dashboard(request):
    direct_permission_folder_ids = FolderUserPermission.objects.filter(
        user=request.user,
        permission_type='read',
    ).values_list('folder_id', flat=True)

    folders = Folder.objects.filter(
        is_active=True,
        id__in=direct_permission_folder_ids,
    ).select_related('storage_root', 'parent').distinct().order_by('storage_root__storage_type', 'relative_path')

    return render(request, 'portal_user/dashboard.html', {'folders': folders})


@web_user_required
def folder_detail(request, folder_id):
    folder = get_object_or_404(Folder, pk=folder_id, is_active=True)

    if not _can_access_folder(request.user, folder):
        create_audit_event(
            user=request.user,
            request=request,
            action_type='FOLDER_ACCESS_DENIED',
            target_type='FOLDER',
            target_id=str(folder.id),
            target_name=folder.display_name,
            status='DENIED',
            message='User attempted unauthorized folder access.',
        )
        from notifications.tasks import send_admin_alert_email_task
        send_admin_alert_email_task.delay(
            'Unauthorized folder access attempt',
            f'User {request.user.email} attempted unauthorized folder access: {folder.display_name}'
        )
        messages.error(request, 'You do not have access to that folder.')
        return redirect('portal_user:dashboard')

    child_folders = folder.children.filter(is_active=True).order_by('display_name')
    visible_child_folders = [child for child in child_folders if _can_access_folder(request.user, child)]

    create_audit_event(
        user=request.user,
        request=request,
        action_type='FOLDER_ACCESS',
        target_type='FOLDER',
        target_id=str(folder.id),
        target_name=folder.display_name,
        status='SUCCESS',
        message='Folder opened.',
    )

    return render(request, 'portal_user/folder_detail.html', {
        'folder': folder,
        'child_folders': visible_child_folders,
        'files': folder.files.filter(is_active=True).order_by('file_name'),
    })


@web_user_required
def download_file(request, file_id):
    file_item = get_object_or_404(FileItem, pk=file_id, is_active=True)
    folder = file_item.folder

    if not _can_access_folder(request.user, folder):
        create_audit_event(
            user=request.user,
            request=request,
            action_type='FILE_DOWNLOAD_DENIED',
            target_type='FILE',
            target_id=str(file_item.id),
            target_name=file_item.file_name,
            status='DENIED',
            message='User attempted unauthorized file download.',
        )
        from notifications.tasks import send_admin_alert_email_task
        send_admin_alert_email_task.delay(
            'Unauthorized file download attempt',
            f'User {request.user.email} attempted unauthorized file download: {file_item.file_name}'
        )
        raise Http404('Not found')

    storage_root = folder.storage_root
    root_path = storage_root.absolute_root_path.rstrip('/')
    full_path = file_item.absolute_path

    if not full_path.startswith(root_path + '/'):
        raise Http404('Invalid file mapping')

    relative_part = full_path[len(root_path):].lstrip('/')

    if storage_root.storage_type == 'local':
        internal_path = f"{settings.PROTECTED_NGINX_PREFIX}/local/{relative_part}"
    elif storage_root.storage_type == 'nas':
        internal_path = f"{settings.PROTECTED_NGINX_PREFIX}/nas/{relative_part}"
    else:
        raise Http404('Unknown storage type')

    create_audit_event(
        user=request.user,
        request=request,
        action_type='FILE_DOWNLOAD_REQUEST',
        target_type='FILE',
        target_id=str(file_item.id),
        target_name=file_item.file_name,
        status='SUCCESS',
        message='File download requested.',
    )

    response = HttpResponse()
    response['Content-Type'] = 'application/octet-stream'
    response['Content-Disposition'] = f'attachment; filename="{file_item.file_name}"'
    response['X-Accel-Redirect'] = internal_path
    response['X-Accel-Buffering'] = 'no'

    create_audit_event(
        user=request.user,
        request=request,
        action_type='FILE_DOWNLOAD_STARTED',
        target_type='FILE',
        target_id=str(file_item.id),
        target_name=file_item.file_name,
        status='SUCCESS',
        message='File download started via X-Accel-Redirect.',
    )
    return response


@portal_account_required
def profile_view(request):
    questions = request.user.security_answers.select_related('question').all()
    return render(request, 'portal_user/profile.html', {'questions': questions})


@portal_account_required
def change_password(request):
    if request.method == 'GET':
        create_otp(request.user, OtpCode.OTP_PASSWORD_CHANGE, request=request)

    form = PasswordChangeWithOtpForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid() and verify_otp(request.user, OtpCode.OTP_PASSWORD_CHANGE, form.cleaned_data['otp'], request=request):
        set_new_password(request.user, form.cleaned_data['new_password'])
        messages.success(request, 'Password changed. Please log in again.')
        from django.contrib.auth import logout
        logout(request)
        return redirect('accounts:login_password')

    return render(request, 'portal_user/form.html', {'form': form, 'title': 'Change Password'})


@login_required
def forced_password_reset(request):
    form = ForcedPasswordResetForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        set_new_password(request.user, form.cleaned_data['new_password'])
        request.user.profile.must_change_password = False
        request.user.profile.save(update_fields=['must_change_password', 'updated_at'])
        from django.contrib.auth import logout
        logout(request)
        messages.success(request, 'Password changed. Log in again with your new password and OTP.')
        return redirect('accounts:login_password')
    return render(request, 'portal_user/form.html', {'form': form, 'title': 'Forced Password Reset'})
