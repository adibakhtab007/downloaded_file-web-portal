from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginPasswordView.as_view(), name='login_password'),
    path('otp/', views.OtpVerifyView.as_view(), name='otp_verify'),
    path('logout/', views.logout_view, name='logout'),
    path('post-login-router/', views.post_login_router, name='post_login_router'),
    path('unlock/', views.UnlockAccountView.as_view(), name='unlock_account'),
    path('unlock/otp/', views.UnlockOtpView.as_view(), name='unlock_otp'),
    path('password/expired/', views.ExpiredPasswordResetView.as_view(), name='expired_password_reset'),
]
