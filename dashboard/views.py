import logging

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView

# Set up logging
logger = logging.getLogger(__name__)


class DashboardHomePage(TemplateView):
    """Serve the landing page directly from Django"""

    template_name = "dashboard/home.html"
