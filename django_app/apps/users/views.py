from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


def root_view(request):
    if request.user.is_authenticated:
        return redirect(getattr(settings, "LOGIN_REDIRECT_URL", "/users/home/"))
    return redirect("/accounts/login/")


@login_required
def home(request):
    return render(request, "index.html")


@login_required
def access_pending(request):
    return render(request, "users/access_pending.html")


@login_required
def access_denied(request):
    return render(request, "users/access_denied.html")

def login_denied(request):
    return render(request, "login_denied.html")
