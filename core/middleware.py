from core.models import SiteSettings
from django.http import HttpResponse
from django.shortcuts import render


class MaintenanceModeMiddleware:
    """Middleware to handle maintenance mode"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if maintenance mode is enabled
        try:
            settings = SiteSettings.objects.first()
            if settings and settings.maintenance_mode:
                # Allow admin users to access the site
                if request.user.is_authenticated and (
                    request.user.is_staff or request.user.is_superuser
                ):
                    response = self.get_response(request)
                    return response

                # Allow access to admin URLs
                if request.path.startswith("/admin/"):
                    response = self.get_response(request)
                    return response

                # Show maintenance page for everyone else
                return render(request, "maintenance.html", status=503)

        except Exception:
            # If there's an error checking settings, allow normal operation
            pass

        response = self.get_response(request)
        return response
