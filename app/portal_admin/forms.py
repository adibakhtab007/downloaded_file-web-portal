from django import forms
from django.contrib.auth import get_user_model

from accounts.enums import UserRole, AccountStatus
from accounts.models import User
from storage_index.models import Folder, StorageRoot, FileItem
from settings_app.models import AppSetting

User = get_user_model()


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(d, initial) for d in data]
        return [single_file_clean(data, initial)]


class FolderPathChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        root_prefix = (obj.storage_root.storage_type or '').strip().lower()
        rel = (obj.relative_path or '').strip()

        if rel in {'', '.'}:
            return root_prefix or obj.storage_root.name

        return f'{root_prefix}/{rel}'


class FilePathChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        folder = obj.folder
        root_prefix = (folder.storage_root.storage_type or '').strip().lower()
        rel = (folder.relative_path or '').strip()

        if rel in {'', '.'}:
            return f'{root_prefix}/{obj.file_name}'

        return f'{root_prefix}/{rel}/{obj.file_name}'


class CreateAdminUserForm(forms.Form):
    full_name = forms.CharField(max_length=255)
    email = forms.EmailField()
    role = forms.ChoiceField(choices=[
        (UserRole.SUPER_ADMIN, 'Super Admin'),
        (UserRole.ADMIN_READONLY, 'Admin Readonly'),
    ])
    password = forms.CharField(widget=forms.PasswordInput)

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()


class FolderCreateForm(forms.Form):
    storage_root = forms.ModelChoiceField(queryset=StorageRoot.objects.filter(is_active=True))
    display_name = forms.CharField(max_length=255)
    relative_path = forms.CharField(max_length=1024, help_text='Path relative to the storage root, e.g. team/finance')


class FileUploadForm(forms.Form):
    folder = FolderPathChoiceField(
        queryset=Folder.objects.filter(is_active=True).select_related('storage_root').order_by('storage_root__storage_type', 'relative_path')
    )
    upload_file = MultipleFileField(
        widget=MultipleFileInput(attrs={'multiple': True}),
        label='Files',
        help_text='You can select multiple files. Total upload size must stay within the configured limit.',
    )


class DeleteFolderForm(forms.Form):
    folder = FolderPathChoiceField(
        queryset=Folder.objects.filter(is_active=True, parent__isnull=False).select_related('storage_root').order_by('storage_root__storage_type', 'relative_path'),
        label='Folder',
        help_text='Only sub-folders can be deleted. Root folders local/nas are excluded.',
    )


class DeleteFileForm(forms.Form):
    file_item = FilePathChoiceField(
        queryset=FileItem.objects.filter(is_active=True).select_related('folder', 'folder__storage_root').order_by('folder__storage_root__storage_type', 'relative_path'),
        label='File',
    )


class PermissionAssignmentForm(forms.Form):
    folder = FolderPathChoiceField(
        queryset=Folder.objects.filter(is_active=True)
        .select_related('storage_root')
        .order_by('storage_root__storage_type', 'relative_path'),
        widget=forms.Select(attrs={
            'size': 8,
            'style': 'width:100%; min-width:420px;'
        }),
        label='Folder',
    )
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(
            profile__role=UserRole.WEB_USER,
            profile__account_status__in=[
                AccountStatus.APPROVED,
                AccountStatus.BLOCKED,
                AccountStatus.SECURITY_BLOCKED,
                AccountStatus.DISABLED_PASSWORD_EXPIRED,
            ],
        )
        .select_related('profile')
        .order_by('email'),
        widget=forms.Select(attrs={
            'size': 8,
            'style': 'width:100%; min-width:320px;'
        }),
        label='User',
    )


class AppSettingUpdateForm(forms.ModelForm):
    class Meta:
        model = AppSetting
        fields = ['value']


class UserSoftDeleteForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.none(), label='User')

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)

        qs = User.objects.filter(
            profile__account_status=AccountStatus.APPROVED
        ).select_related('profile').order_by('email')

        if actor and actor.profile.role == UserRole.ADMIN_READONLY:
            qs = qs.exclude(profile__role=UserRole.SUPER_ADMIN)

        self.fields['user'].queryset = qs


class FolderPermissionRevokeForm(forms.Form):
    folder = FolderPathChoiceField(
        queryset=Folder.objects.filter(is_active=True).select_related('storage_root').order_by('storage_root__storage_type', 'relative_path'),
        label='Folder',
    )
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).select_related('profile').order_by('email'),
        label='User',
    )
