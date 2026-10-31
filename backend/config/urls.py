from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, HttpResponseServerError, JsonResponse
from django.urls import include, path, re_path

from .health import health


def spa(request):
    """Catch-all: serve the built React app so client-side routes survive a refresh."""
    index = settings.FRONTEND_DIST / "index.html"
    if not index.is_file():
        return JsonResponse({"detail": "Frontend not built. Run `npm run build` or use the Vite dev server."}, status=404)
    return FileResponse(open(index, "rb"), content_type="text/html")


def api_not_found(request):
    """Unknown /api/ paths answer like the rest of the API (JSON), not with an HTML page."""
    return JsonResponse({"detail": "Not found."}, status=404)


def server_error(request):
    """handler500 (DEBUG=false): JSON for the API so the SPA can show its error toast; never a stack trace."""
    if request.path.startswith("/api/"):
        return JsonResponse({"detail": "Server error. It has been logged; please try again."}, status=500)
    return HttpResponseServerError("<h1>Server error</h1>")


handler500 = server_error

urlpatterns = [
    path("admin/", admin.site.urls),
    re_path(r"^api/healthz/?$", health),
    path("api/", include("apps.core.accounts.urls")),
    path("api/", include("apps.core.catalog.urls")),
    path("api/", include("apps.core.subscriptions.urls")),
    path("api/", include("apps.core.billing.urls")),
    path("api/", include("apps.finance.discounts.urls")),
    path("api/", include("apps.finance.payments.urls")),
    path("api/", include("apps.finance.notifications.urls")),
    path("api/", include("apps.finance.dashboard.urls")),
    re_path(r"^api/(?:.*/)?$", api_not_found),  # slash-terminated only, so APPEND_SLASH still redirects /api/plans -> /api/plans/
    re_path(r"^(?!api/|admin/|static/).*$", spa),
]
