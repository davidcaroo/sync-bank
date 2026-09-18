from routers.contactos import ContactPayload, _split_person_name, _to_alegra_payload


def _person(name: str, kind: str = "PERSON_ENTITY") -> ContactPayload:
    return ContactPayload(name=name, kind_of_person=kind, identification="1002307072")


def test_natural_person_gets_name_object():
    data = _to_alegra_payload(_person("DAVID ALFREDO CARO MORALES"))
    assert data["nameObject"] == {
        "firstName": "DAVID",
        "secondName": "ALFREDO",
        "lastName": "CARO",
        "secondLastName": "MORALES",
    }


def test_legal_entity_has_no_name_object():
    data = _to_alegra_payload(_person("ACME SAS", kind="LEGAL_ENTITY"))
    assert "nameObject" not in data


def test_existing_name_object_is_reused_when_name_is_unchanged():
    existing = {
        "nameObject": {
            "firstName": "María",
            "secondName": "de los Ángeles",
            "lastName": "Pérez",
        }
    }
    data = _to_alegra_payload(_person("maría de los ángeles pérez"), existing)
    assert data["nameObject"] == existing["nameObject"]


def test_renamed_person_is_split_again():
    existing = {"nameObject": {"firstName": "JUAN", "lastName": "PEREZ"}}
    data = _to_alegra_payload(_person("JUAN GOMEZ"), existing)
    assert data["nameObject"] == {"firstName": "JUAN", "lastName": "GOMEZ"}


def test_short_names_do_not_crash():
    assert _split_person_name("") == {}
    assert _split_person_name("CHER") == {"firstName": "CHER"}
