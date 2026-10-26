from django.shortcuts import get_object_or_404
from django.db import transaction

from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import DatabaseConnection, IngestionJob
from .serializers import (
    ConnectionInputSerializer,
    ConnectionResponseSerializer,
    ExtractRequestSerializer,
    IngestionJobSerializer,
)
from .security import encrypt_password
from .services import (
    test_connection_details,
    list_source_tables,
    extract_table_to_raw,
)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def test_connection(request):
    serializer = ConnectionInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        connected = test_connection_details(serializer.validated_data)
        if connected:
            return Response({
                "success": True,
                "message": "PostgreSQL connection successful.",
            })
    except Exception:
        pass

    return Response(
        {
            "success": False,
            "message": "Connection failed. Verify the connection details.",
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_connection(request):
    serializer = ConnectionInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    # Verify the connection before saving its configuration.
    try:
        if not test_connection_details(data):
            return Response(
                {"message": "Connection test failed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    except Exception:
        return Response(
            {"message": "Connection test failed."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    connection = DatabaseConnection.objects.create(
        name=data["name"],
        owner=request.user,
        host=data["host"],
        port=data["port"],
        database_name=data["database_name"],
        username=data["username"],
        encrypted_password=encrypt_password(data["password"]),
    )

    return Response(
        ConnectionResponseSerializer(connection).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def connection_tables(request, connection_id):
    connection = get_object_or_404(
        DatabaseConnection,
        id=connection_id,
        owner=request.user,
    )

    try:
        tables = list_source_tables(connection)
        return Response({
            "connection_id": connection.id,
            "tables": tables,
        })
    except Exception:
        return Response(
            {"message": "Could not retrieve source tables."},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def extract_table(request, connection_id):
    connection = get_object_or_404(
        DatabaseConnection,
        id=connection_id,
        owner=request.user,
    )

    serializer = ExtractRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    table_name = serializer.validated_data["table_name"]

    try:
        if table_name not in list_source_tables(connection):
            return Response(
                {"message": "Table not found in public schema."},
                status=status.HTTP_404_NOT_FOUND,
            )
    except Exception:
        return Response(
            {"message": "Could not verify the source table."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    job = IngestionJob.objects.create(
        connection=connection,
        table_name=table_name,
        status=IngestionJob.Status.QUEUED,
    )

    # Simple synchronous implementation for initial development.
    job = extract_table_to_raw(job)

    response_status = (
        status.HTTP_201_CREATED
        if job.status == IngestionJob.Status.SUCCESS
        else status.HTTP_502_BAD_GATEWAY
    )
    return Response(
        IngestionJobSerializer(job).data,
        status=response_status,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def job_status(request, job_id):
    job = get_object_or_404(
        IngestionJob,
        id=job_id,
        connection__owner=request.user,
    )
    return Response(IngestionJobSerializer(job).data)
