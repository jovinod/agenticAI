import os

import psycopg
from azure.identity import DefaultAzureCredential
from sqlmodel import create_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:devpassword@localhost:5433/alpha"
)
DATABASE_HOST = os.environ.get("DATABASE_HOST")
DATABASE_NAME = os.environ.get("DATABASE_NAME", "alpha")
DATABASE_USER = os.environ.get("DATABASE_USER", "")
PG_TOKEN_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"

if DATABASE_HOST:
    _pg_credential = DefaultAzureCredential()

    def _get_pg_connection() -> psycopg.Connection:
        token = _pg_credential.get_token(PG_TOKEN_SCOPE).token
        return psycopg.connect(
            host=DATABASE_HOST,
            dbname=DATABASE_NAME,
            user=DATABASE_USER,
            password=token,
            sslmode="require",
        )

    engine = create_engine("postgresql+psycopg://", creator=_get_pg_connection)
else:
    engine = create_engine(DATABASE_URL)
