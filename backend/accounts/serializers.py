from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils import timezone
from .models import User, Tenant


class UserSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    monthly_budget = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "full_name", "role", "status", "tenant", "tenant_name",
            "email_verified_at", "created_at", "monthly_budget",
        ]
        read_only_fields = fields

    def get_monthly_budget(self, obj):
        from django.conf import settings
        return getattr(settings, "TENANT_MONTHLY_BUDGET_USD", 50)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data["email"].lower().strip()
        user = authenticate(username=email, password=data["password"])
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        if user.status == "deactivated":
            raise serializers.ValidationError("Account deactivated")
        if not user.is_active:
            raise serializers.ValidationError("Account inactive")
        data["user"] = user
        return data


class AdminCreateUserSerializer(serializers.Serializer):
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    role = serializers.ChoiceField(choices=["admin", "member"], default="member")
    password = serializers.CharField(required=False, allow_blank=True, write_only=True)

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value


class AdminUpdateUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["full_name", "role"]
