from django.urls import path

from . import views

urlpatterns = [
    # Frontend pages
    path("", views.DashboardHomePage.as_view(), name="dashboard-home"),
]
