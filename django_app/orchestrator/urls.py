from django.contrib import admin
from django.urls import path, include
from apps.users.views import root_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", root_view, name="root"),
    path("accounts/", include("allauth.urls")),
    path("users/", include("apps.users.urls")),
    path("api/", include("apps.api.urls")),
]
