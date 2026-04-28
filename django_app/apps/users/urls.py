from django.urls import path
from .views import home, access_pending, access_denied, login_denied

urlpatterns = [
    path("home/", home, name="home"),
    path("access-pending/", access_pending, name="access_pending"),
    path("access-denied/", access_denied, name="access_denied"),
    path("login-denied/", login_denied, name="login_denied"),
]
