import os
from pathlib import Path

import psycopg
import pytest

from repositories.database import close_pool, open_pool


DATABASE_URL = os.environ["DATABASE_URL"]
SCHEMA = Path(__file__).parents[3] / "database" / "schema.sql"


@pytest.fixture(scope="session", autouse=True)
def database_session():
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        conn.execute("drop schema if exists public cascade")
        conn.execute("create schema public")
        conn.execute(SCHEMA.read_text(encoding="utf-8"))
    open_pool()
    yield
    close_pool()
