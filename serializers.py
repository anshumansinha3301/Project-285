from rest_framework import serializers

from .models import DatabaseConnection, IngestionJob


class ConnectionInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    host = serializers.CharField(max_length=255)
    port = serializers.IntegerField(min_value=1, max_value=65535)
    database_name = serializers.CharField(max_length=100)
    username = serializers.CharField(max_length=100)
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )


class ConnectionResponseSerializer(serializers.ModelSerializer):
    password = serializers.SerializerMethodField()

    class Meta:
        model = DatabaseConnection
        fields = [
            "id",
            "name",
            "host",
            "port",
            "database_name",
            "username",
            "password",
            "created_at",
        ]

    def get_password(self, obj):
        return "********"


class ExtractRequestSerializer(serializers.Serializer):
    table_name = serializers.RegexField(
        regex=r"^[A-Za-z_][A-Za-z0-9_]{0,62}$",
        max_length=63,
    )


class IngestionJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = IngestionJob
        fields = [
            "id",
            "table_name",
            "status",
            "raw_object_key",
            "rows_extracted",
            "error_message",
            "created_at",
            "completed_at",
        ]
        read_only_fields = fields
