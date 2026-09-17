def test_database_url_is_configured():
    from config import settings

    assert settings.DATABASE_URL.startswith("postgresql://")


def test_pool_is_lazy_before_startup():
    from repositories import database

    assert database.pool.closed
