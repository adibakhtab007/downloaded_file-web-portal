from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    path('users/', views.user_list, name='user_list'),
    path('users/<int:user_id>/approve/', views.approve_user_row, name='approve_user_row'),
    path('users/<int:user_id>/reject/', views.reject_user_row, name='reject_user_row'),
    path('users/<int:user_id>/disable/', views.disable_user_row, name='disable_user_row'),
    path('users/<int:user_id>/unblock/', views.unblock_user, name='unblock_user'),
    path('users/<int:user_id>/enable-temp-password/', views.enable_with_temp_password, name='enable_with_temp_password'),
    path('users/<int:user_id>/reregister/', views.reregister_user_row, name='reregister_user_row'),
    path('users/<int:user_id>/delete/', views.delete_user_row, name='delete_user_row'),

    path('create-admin/', views.create_admin_user, name='create_admin_user'),

    path('folders/', views.folder_list, name='folder_list'),
    path('folders/create/', views.create_folder, name='create_folder'),
    path('folders/delete/', views.delete_folder, name='delete_folder'),

    path('files/upload/', views.upload_file, name='upload_file'),
    path('files/delete/', views.delete_file, name='delete_file'),

    path('permissions/', views.permissions_view, name='permissions_view'),
    path('permissions/revoke/', views.revoke_folder_permission_view, name='revoke_folder_permission'),
    path('permissions/revoke/<int:perm_id>/', views.revoke_permission_row, name='revoke_permission_row'),

    path('settings/', views.settings_view, name='settings_view'),
    path('logs/', views.audit_logs, name='audit_logs'),
    path('journey/<str:trace_id>/', views.journey_detail, name='journey_detail'),
]
