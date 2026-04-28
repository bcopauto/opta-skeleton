from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class AccessControlMiddleware:
    """
    Global access control middleware.

    Rules:
    - Anonymous users can access only public/auth routes
    - Authenticated users with access_enabled=False are redirected to pending page
    - Authenticated users with access_enabled=True can access protected routes
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        public_prefixes = [
            "/admin/",
            "/accounts/",
            "/static/",
            "/media/",
        ]

        public_exact_paths = {
            "/",
            reverse("access_pending"),
            reverse("access_denied"),
        }

        # Always allow public prefixes
        if any(path.startswith(prefix) for prefix in public_prefixes):
            return self.get_response(request)

        # Allow specific public paths
        if path in public_exact_paths:
            return self.get_response(request)

        user = request.user

        # Anonymous user -> send to login
        if not user.is_authenticated:
            return redirect("/accounts/login/")

        # Authenticated but not approved
        if not getattr(user, "access_enabled", False):
            pending_url = reverse("access_pending")
            denied_url = reverse("access_denied")

            if path not in {pending_url, denied_url}:
                return redirect(pending_url)

        return self.get_response(request)

        blocked_paths = [
            "/accounts/signup/",
            "/accounts/password/",
            "/accounts/email/",
        ]

        if any(path.startswith(p) for p in blocked_paths):
            return redirect("/")
