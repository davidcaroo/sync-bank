import pytest

from services import supabase_service


def test_resolve_supabase_server_key_prefers_service_key(monkeypatch):
    monkeypatch.setattr(supabase_service.settings, "SUPABASE_SERVICE_KEY", "service-key")
    monkeypatch.setattr(supabase_service.settings, "SUPABASE_KEY", "legacy-key")
    monkeypatch.setattr(supabase_service.settings, "SUPABASE_REQUIRE_SERVICE_KEY", True)

    key = supabase_service._resolve_supabase_server_key()

    assert key == "service-key"


def test_resolve_supabase_server_key_requires_service_key_when_strict(monkeypatch):
    monkeypatch.setattr(supabase_service.settings, "SUPABASE_SERVICE_KEY", None)
    monkeypatch.setattr(supabase_service.settings, "SUPABASE_KEY", "legacy-key")
    monkeypatch.setattr(supabase_service.settings, "SUPABASE_REQUIRE_SERVICE_KEY", True)

    with pytest.raises(RuntimeError):
        supabase_service._resolve_supabase_server_key()


def test_resolve_supabase_server_key_allows_legacy_fallback_when_not_strict(monkeypatch):
    monkeypatch.setattr(supabase_service.settings, "SUPABASE_SERVICE_KEY", None)
    monkeypatch.setattr(supabase_service.settings, "SUPABASE_KEY", "legacy-key")
    monkeypatch.setattr(supabase_service.settings, "SUPABASE_REQUIRE_SERVICE_KEY", False)

    key = supabase_service._resolve_supabase_server_key()

    assert key == "legacy-key"
