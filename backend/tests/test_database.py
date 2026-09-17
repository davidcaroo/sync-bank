def test_database_url_is_configured():
    from config import settings

    assert settings.DATABASE_URL.startswith("postgresql://")
