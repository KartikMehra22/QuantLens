"""Isolate migration tests in disposable schemas of an explicitly named test database."""

from contextlib import contextmanager
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema


def validated_test_url(value):
    url = make_url(value)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith("_test"):
        raise ValueError("QUANTLENS_TEST_DATABASE_URL must point to a PostgreSQL database ending in _test.")
    return url


@contextmanager
def migration_engine(test_url):
    url = validated_test_url(test_url)
    schema = f"ql_migrations_{uuid4().hex}"
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    scoped = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        yield scoped
    finally:
        scoped.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()
