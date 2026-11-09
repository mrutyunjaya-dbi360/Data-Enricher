from django.urls import path
from . import views

urlpatterns = [
    path("report", views.JobReportView.as_view()),
    path("report/docs", views.JobReportDocsView.as_view()),
    path("cost", views.JobCostView.as_view()),
    path("cost/timeseries", views.JobCostTimeseriesView.as_view()),
    path("quality", views.JobQualityView.as_view()),
    path("quality/docs", views.JobQualityDocsView.as_view()),
]
