from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('', RedirectView.as_view(pattern_name='accounts:post_login_router', permanent=False)),
    path('auth/', include(('accounts.urls', 'accounts'), namespace='accounts')),
    path('admin-portal/', include(('portal_admin.urls', 'portal_admin'), namespace='portal_admin')),
    path('portal/', include(('portal_user.urls', 'portal_user'), namespace='portal_user')),
]
