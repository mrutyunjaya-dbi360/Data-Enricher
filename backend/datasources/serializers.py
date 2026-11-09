from rest_framework import serializers
from urllib.parse import urlparse
from .models import Datasource
from .crypto import encrypt, decrypt
from .ssrf import assert_public_mongo_uri, SSRFBlocked


def mask_uri(uri: str) -> str:
    if not uri:
        return ""
    try:
        p = urlparse(uri if "://" in uri else "mongodb://" + uri)
        user = p.username or ""
        host = p.hostname or ""
        if user:
            user_masked = user[:1] + "***" if len(user) > 1 else "***"
            return f"{p.scheme}://{user_masked}:***@{host}/..."
        return f"{p.scheme}://{host}/..."
    except Exception:
        return "***"


class DatasourceSerializer(serializers.ModelSerializer):
    uri_masked = serializers.SerializerMethodField()
    mongo_uri = serializers.CharField(write_only=True, required=False)
    master_uri = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    owner_email = serializers.CharField(source="owner.email", read_only=True)

    class Meta:
        model = Datasource
        fields = [
            "id", "label", "db_name", "col_name", "field_mapping", "status",
            "uri_masked", "mongo_uri", "master_uri", "owner", "owner_email",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "owner", "uri_masked", "owner_email", "created_at", "updated_at"]

    def get_uri_masked(self, obj):
        try:
            return mask_uri(decrypt(bytes(obj.encrypted_uri)))
        except Exception:
            return "***"

    def validate(self, data):
        mongo_uri = data.get("mongo_uri")
        if mongo_uri is None and self.instance is None:
            raise serializers.ValidationError({"mongo_uri": "Required"})
        if mongo_uri:
            try:
                assert_public_mongo_uri(mongo_uri)
            except SSRFBlocked as e:
                raise serializers.ValidationError({"mongo_uri": str(e)})
        master = data.get("master_uri")
        if master:
            try:
                assert_public_mongo_uri(master)
            except SSRFBlocked as e:
                raise serializers.ValidationError({"master_uri": str(e)})
        return data

    def create(self, validated):
        request = self.context["request"]
        uri = validated.pop("mongo_uri")
        master = validated.pop("master_uri", None) or None
        ds = Datasource(
            tenant=request.user.tenant,
            owner=request.user,
            created_by=request.user,
            encrypted_uri=encrypt(uri),
            encrypted_master_uri=encrypt(master) if master else None,
            **validated,
        )
        ds.save()
        return ds

    def update(self, instance, validated):
        uri = validated.pop("mongo_uri", None)
        master = validated.pop("master_uri", None)
        for k, v in validated.items():
            setattr(instance, k, v)
        if uri is not None:
            instance.encrypted_uri = encrypt(uri)
        if master is not None:
            instance.encrypted_master_uri = encrypt(master) if master else None
        instance.save()
        return instance
