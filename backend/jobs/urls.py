from django.urls import path
from . import views

urlpatterns = [
    path("", views.JobListCreateView.as_view()),
    path("<uuid:pk>", views.JobDetailView.as_view()),
    path("<uuid:pk>/cancel", views.JobCancelView.as_view()),
    path("<uuid:pk>/resume", views.JobResumeView.as_view()),
    path("<uuid:pk>/stream", views.JobStreamView.as_view()),
]
