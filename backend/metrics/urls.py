from django.urls import path
from . import views

urlpatterns = [
    path("report/summary", views.ReportSummaryView.as_view()),
    path("cost/summary", views.CostSummaryView.as_view()),
    path("quality/summary", views.QualitySummaryView.as_view()),
    path("users", views.UsersMetricsView.as_view()),
    path("users/<uuid:pk>", views.UserMetricsDetailView.as_view()),
    path("users/<uuid:pk>/datasources", views.UserDatasourcesMetricsView.as_view()),
]
