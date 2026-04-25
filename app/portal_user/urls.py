from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('folders/<int:folder_id>/', views.folder_detail, name='folder_detail'),
    path('download/<int:file_id>/', views.download_file, name='download_file'),
    path('profile/', views.profile_view, name='profile'),
    path('password/change/', views.change_password, name='change_password'),
    path('password/forced/', views.forced_password_reset, name='forced_password_reset'),
]
