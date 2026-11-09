import secrets
import string
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from .models import User, Tenant
from .serializers import (
    UserSerializer, LoginSerializer, AdminCreateUserSerializer, AdminUpdateUserSerializer,
)
from .permissions import IsAdmin


def _tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh), "user": UserSerializer(user).data}


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ser = LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return Response(_tokens_for(ser.validated_data["user"]))


class RefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        from rest_framework_simplejwt.views import TokenRefreshView
        return TokenRefreshView.as_view()(request._request)


class LogoutView(APIView):
    def post(self, request):
        try:
            token = RefreshToken(request.data.get("refresh"))
            token.blacklist()
        except Exception:
            pass
        return Response({"detail": "ok"})


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class AdminUserListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        qs = User.objects.filter(tenant=request.user.tenant).order_by("-created_at")
        return Response(UserSerializer(qs, many=True).data)

    def post(self, request):
        ser = AdminCreateUserSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        password = data.get("password") or "".join(
            secrets.choice(string.ascii_letters + string.digits) for _ in range(16)
        )
        user = User.objects.create_user(
            email=data["email"],
            password=password,
            full_name=data.get("full_name", ""),
            role=data.get("role", "member"),
            tenant=request.user.tenant,
            status="active",
            email_verified_at=timezone.now(),
            created_by=request.user,
        )
        out = UserSerializer(user).data
        out["generated_password"] = password
        return Response(out, status=status.HTTP_201_CREATED)


class AdminUserDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def patch(self, request, pk):
        try:
            user = User.objects.get(pk=pk, tenant=request.user.tenant)
        except User.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        ser = AdminUpdateUserSerializer(user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(UserSerializer(user).data)


class AdminDeactivateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk, tenant=request.user.tenant)
        except User.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        user.status = "deactivated"
        user.deactivated_by = request.user
        user.save(update_fields=["status", "deactivated_by", "updated_at"])
        from jobs.models import Job
        Job.objects.filter(datasource_owner=user, status="queued").update(status="cancelled")
        return Response(UserSerializer(user).data)


class AdminActivateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk, tenant=request.user.tenant)
        except User.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        user.status = "active"
        user.deactivated_by = None
        user.save(update_fields=["status", "deactivated_by", "updated_at"])
        return Response(UserSerializer(user).data)


class AdminResetPasswordView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk, tenant=request.user.tenant)
        except User.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        password = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
        user.set_password(password)
        user.save()
        return Response({"generated_password": password, "user": UserSerializer(user).data})
