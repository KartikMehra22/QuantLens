from alembic import context

from app import models  # noqa: F401
from app.config import settings
from app.database import Base, engine


def run(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(url=settings.database_url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    supplied = context.config.attributes.get("connection")
    if supplied is not None:
        run(supplied)
    else:
        with engine.connect() as connection:
            run(connection)
