import pytest
from fastapi import HTTPException
from psycopg.errors import UniqueViolation
from pydantic import ValidationError

from routers import config as config_router
from routers.config import ConfigCuentaCreate, ConfigCuentaUpdate

CURRENT = {
    "id": "c1",
    "nit_proveedor": "901209021",
    "nombre_proveedor": "DEVISAB",
    "id_cuenta_alegra": "5105",
    "id_centro_costo_alegra": "12",
    "auto_causar": True,
    "activo": True,
    "source": "historical",
}


@pytest.fixture
def repo(monkeypatch):
    calls = {}

    def create(payload):
        calls["create"] = payload
        return {"id": "new", **payload}

    def update(config_id, payload):
        calls["update"] = payload
        return {**CURRENT, **payload}

    monkeypatch.setattr(config_router, "repo_create_config_cuenta", create)
    monkeypatch.setattr(config_router, "repo_update_config_cuenta", update)
    monkeypatch.setattr(
        config_router, "repo_get_config_cuenta_by_id", lambda config_id: dict(CURRENT)
    )
    return calls


@pytest.mark.asyncio
async def test_create_only_sends_supported_fields_and_marks_rule_manual(repo):
    await config_router.create_config_cuenta(
        ConfigCuentaCreate(
            nit_proveedor="900.123.456-7",
            nombre_proveedor="Nitido",
            id_cuenta_alegra="5105",
            id_centro_costo_alegra="",
        )
    )

    assert repo["create"] == {
        "nit_proveedor": "9001234567",
        "nombre_proveedor": "Nitido",
        "id_cuenta_alegra": "5105",
        "id_centro_costo_alegra": None,
        "auto_causar": False,
        "activo": True,
        "source": "manual",
        "confianza": 1,
    }


def test_create_requires_an_account():
    with pytest.raises(ValidationError):
        ConfigCuentaCreate(nit_proveedor="900123456", id_cuenta_alegra="   ")


def test_unsupported_retention_fields_are_ignored_by_the_model():
    payload = ConfigCuentaCreate(
        nit_proveedor="900123456", id_cuenta_alegra="5105", id_retefuente="9"
    )
    assert "id_retefuente" not in payload.model_dump()


@pytest.mark.asyncio
async def test_autocausation_requires_account_and_cost_center(repo):
    with pytest.raises(HTTPException) as exc:
        await config_router.create_config_cuenta(
            ConfigCuentaCreate(
                nit_proveedor="900123456", id_cuenta_alegra="5105", auto_causar=True
            )
        )
    assert exc.value.status_code == 422
    assert "create" not in repo


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        {"id_cuenta_alegra": "5199"},
        {"id_centro_costo_alegra": "99"},
        {"nit_proveedor": "800000002"},
    ],
)
async def test_changing_classification_revokes_autocausation(repo, change):
    await config_router.update_config_cuenta("c1", ConfigCuentaUpdate(**change))

    assert repo["update"]["auto_causar"] is False
    assert repo["update"]["source"] == "manual"


@pytest.mark.asyncio
async def test_changing_classification_can_grant_autocausation_explicitly(repo):
    await config_router.update_config_cuenta(
        "c1", ConfigCuentaUpdate(id_cuenta_alegra="5199", auto_causar=True)
    )

    assert repo["update"]["auto_causar"] is True


@pytest.mark.asyncio
async def test_unrelated_edit_keeps_autocausation_and_takes_over_the_rule(repo):
    await config_router.update_config_cuenta(
        "c1", ConfigCuentaUpdate(nombre_proveedor="DEVISAB S.A.S.")
    )

    assert "auto_causar" not in repo["update"]
    assert repo["update"]["source"] == "manual"
    assert repo["update"]["confianza"] == 1


@pytest.mark.asyncio
async def test_clearing_the_cost_center_of_an_autocausation_rule_is_rejected(repo):
    with pytest.raises(HTTPException) as exc:
        await config_router.update_config_cuenta(
            "c1", ConfigCuentaUpdate(id_centro_costo_alegra="", auto_causar=True)
        )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_update_of_unknown_rule_is_404(monkeypatch):
    monkeypatch.setattr(
        config_router, "repo_get_config_cuenta_by_id", lambda config_id: None
    )
    with pytest.raises(HTTPException) as exc:
        await config_router.update_config_cuenta("nope", ConfigCuentaUpdate())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_nit_is_409_not_500(monkeypatch):
    def duplicate(payload):
        raise UniqueViolation("duplicate key")

    monkeypatch.setattr(config_router, "repo_create_config_cuenta", duplicate)
    with pytest.raises(HTTPException) as exc:
        await config_router.create_config_cuenta(
            ConfigCuentaCreate(nit_proveedor="900123456", id_cuenta_alegra="5105")
        )
    assert exc.value.status_code == 409
