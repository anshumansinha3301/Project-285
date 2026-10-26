import csv
import os
import tempfile

import boto3
import psycopg2

from django.conf import settings
from django.utils import timezone
from psycopg2 import sql

from .models import IngestionJob
from .security import decrypt_password


def open_source_connection(config):
    """Connect to a configured PostgreSQL source."""
    password = decrypt_password(config.encrypted_password)

    return psycopg2.connect(
        host=config.host,
        port=config.port,
        dbname=config.database_name,
        user=config.username,
        password=password,
        connect_timeout=5,
        sslmode="require",
        application_name="AstraLab-Ingestion",
    )


def test_connection_details(data):
    """Test credentials before storing a connection."""
    connection = psycopg2.connect(
        host=data["host"],
        port=data["port"],
        dbname=data["database_name"],
        user=data["username"],
        password=data["password"],
        connect_timeout=5,
        sslmode="require",
        application_name="AstraLab-Ingestion",
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone()[0] == 1
    finally:
        connection.close()


def list_source_tables(config):
    """Return tables from the public schema."""
    connection = open_source_connection(config)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            )
            return [row[0] for row in cursor.fetchall()]
    finally:
        connection.close()


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
    )


def extract_table_to_raw(job):
    """
    Export one public-schema table to CSV and upload it to
    the configured S3-compatible Raw Zone.
    """
    job.status = IngestionJob.Status.RUNNING
    job.error_message = ""
    job.save(update_fields=["status", "error_message"])

    source = None

    try:
        source = open_source_connection(job.connection)

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            suffix=".csv",
            delete=False,
        ) as temp:
            temp_path = temp.name

        try:
            with source.cursor() as cursor:
                query = sql.SQL(
                    "SELECT * FROM {}.{}"
                ).format(
                    sql.Identifier("public"),
                    sql.Identifier(job.table_name),
                )
                cursor.execute(query)

                writer = csv.writer(temp)
                writer.writerow(
                    [column.name for column in cursor.description]
                )

                while True:
                    rows = cursor.fetchmany(1000)
                    if not rows:
                        break
                    writer.writerows(rows)
                    job.rows_extracted += len(rows)

            object_key = (
                f"raw/postgresql/{job.connection_id}/"
                f"{job.id}/{job.table_name}.csv"
            )

            _s3_client().upload_file(
                temp_path,
                settings.S3_BUCKET,
                object_key,
                ExtraArgs={"ContentType": "text/csv"},
            )

            job.raw_object_key = object_key
            job.status = IngestionJob.Status.SUCCESS

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    except Exception:
        # Do not return connection strings, passwords, or
        # internal exception details to the API caller.
        job.status = IngestionJob.Status.FAILED
        job.error_message = (
            "Extraction failed. Check service logs for details."
        )

    finally:
        if source is not None:
            source.close()

        job.completed_at = timezone.now()
        job.save(update_fields=[
            "status",
            "error_message",
            "raw_object_key",
            "rows_extracted",
            "completed_at",
        ])

    return job
