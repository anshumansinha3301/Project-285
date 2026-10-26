from django.urls import path

from . import views

urlpatterns = [
    path(
        "connections/test/",
        views.test_connection,
        name="test-connection",
    ),
    path(
        "connections/",
        views.create_connection,
        name="create-connection",
    ),
    path(
        "connections/<int:connection_id>/tables/",
        views.connection_tables,
        name="connection-tables",
    ),
    path(
        "connections/<int:connection_id>/extract/",
        views.extract_table,
        name="extract-table",
    ),
    path(
        "jobs/<uuid:job_id>/",
        views.job_status,
        name="job-status",
    ),
]
