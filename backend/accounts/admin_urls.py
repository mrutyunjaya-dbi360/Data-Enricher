from django.urls import path
from . import views

urlpatterns = [
    path("users", views.AdminUserListCreateView.as_view()),
    path("users/<uuid:pk>", views.AdminUserDetailView.as_view()),
    path("users/<uuid:pk>/deactivate", views.AdminDeactivateView.as_view()),
    path("users/<uuid:pk>/activate", views.AdminActivateView.as_view()),
    path("users/<uuid:pk>/reset-password", views.AdminResetPasswordView.as_view()),
]
