from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/admin/", include("accounts.admin_urls")),
    path("api/datasources/", include("datasources.urls")),
    path("api/datasources", include("datasources.urls")),
    path("api/jobs/", include("jobs.urls")),
    path("api/jobs", include("jobs.urls")),
    path("api/jobs/<uuid:pk>/", include("metrics.job_urls")),
    path("api/metrics/", include("metrics.urls")),
]
