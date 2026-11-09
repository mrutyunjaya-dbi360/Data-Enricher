from django.urls import path
from . import views

urlpatterns = [
    path("", views.DatasourceListCreateView.as_view()),
    path("<uuid:pk>", views.DatasourceDetailView.as_view()),
]
