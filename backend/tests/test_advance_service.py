import asyncio

import pytest

from services import advance_service

TEMPLATE = "01H9QVH1E1XM7394S2K2HZDVJW"


def bill(bill_id, number, date, balance, status="open"):
    return {
        "id": str(bill_id),
        "numberTemplate": {"fullNumber": number},
        "date": date,
        "total": balance,
        "balance": balance,
        "totalPaid": 0,
        "status": status,
    }


def advance(adv_id, available, date="2026-09-18"):
    return {"idGlobal": adv_id, "idAdvance": adv_id, "amountAvailable": available, "date": date}


class Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


class FakeAlegra:
    """Just enough of Alegra: open bills, advances with balance, and the apply call."""

    def __init__(self, bills, advances, post_status=200):
        self.bills = {b["id"]: b for b in bills}
        self.advances = advances
        self.post_status = post_status
        self.posts = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, params=None, headers=None):
        if url.endswith("/advances-applied"):
            return Response(200, self.advances)
        if url.endswith("/bills"):
            start = int(params.get("start", 0))
            ordered = sorted(self.bills.values(), key=lambda b: (b["date"], b["id"]), reverse=True)
            return Response(200, ordered[start : start + 30])
        bill_id = url.rsplit("/", 1)[1]
        return Response(200, self.bills[bill_id])

    async def post(self, url, json=None, headers=None):
        bill_id = url.split("/bills/")[1].split("/")[0]
        self.posts.append((bill_id, json))
        if self.post_status == 200:
            target = self.bills[bill_id]
            target.update(status="closed", balance=0, totalPaid=target["total"])
            for item in json["advances"]:
                for adv in self.advances:
                    if adv["idGlobal"] == item["idGlobal"]:
                        adv["amountAvailable"] -= float(item["amount"])
            return Response(200, {"code": 200, "message": []})
        return Response(self.post_status, {"code": 36309, "message": "boom"})


@pytest.fixture
def alegra(monkeypatch):
    holder = {}
    alerts = []

    def install(bills, advances, post_status=200):
        fake = FakeAlegra(bills, advances, post_status)
        holder["fake"] = fake
        monkeypatch.setattr(advance_service.httpx, "AsyncClient", lambda **kw: fake)
        return fake

    async def provider(client, nit):
        return {"id": "1152"}

    async def notify(key, subject, body):
        alerts.append((key, subject, body))

    monkeypatch.setattr(advance_service.alegra_service, "find_provider_contact_by_nit", provider)
    monkeypatch.setattr(advance_service, "notify", notify)
    monkeypatch.setattr(advance_service.settings, "AUTO_ADVANCE_NITS", "901209021")
    monkeypatch.setattr(advance_service.settings, "AUTO_ADVANCE_MODE", "on")
    monkeypatch.setattr(advance_service.settings, "ADVANCE_NUMBER_TEMPLATE_ID", TEMPLATE)
    monkeypatch.setattr(advance_service.settings, "MIN_ISSUE_DATE", "2026-09-01")
    monkeypatch.setattr(advance_service, "_today", lambda: "2026-10-07")
    install.alerts = alerts
    return install


def test_plan_pays_oldest_bills_first_and_stops_at_the_first_one_that_does_not_fit():
    bills = [
        bill(3, "C", "2026-10-03", 13900),
        bill(1, "A", "2026-10-01", 13900),
        bill(2, "B", "2026-10-02", 13900),
    ]

    plan, short = advance_service.plan_allocations(bills, [advance("X", 30000)])

    assert [p["number"] for p in plan] == ["A", "B"]
    assert [s["number"] for s in short] == ["C"]


def test_plan_can_split_a_bill_across_advances_oldest_advance_first():
    bills = [bill(1, "A", "2026-10-01", 24400)]
    advances = [advance("NEW", 10000, "2026-09-25"), advance("OLD", 20000, "2026-09-01")]

    plan, short = advance_service.plan_allocations(bills, advances)

    assert short == []
    assert plan[0]["allocations"] == [
        {"idGlobal": "OLD", "amount": 20000},
        {"idGlobal": "NEW", "amount": 4400},
    ]


def test_plan_never_applies_a_partial_amount():
    plan, short = advance_service.plan_allocations(
        [bill(1, "A", "2026-10-01", 13900)], [advance("X", 5000)]
    )

    assert plan == [] and short[0]["number"] == "A"


@pytest.mark.asyncio
async def test_a_real_run_posts_exactly_what_the_alegra_screen_sends(alegra):
    fake = alegra([bill(5779, "FEUU2394311", "2026-10-06", 13900)], [advance("95270744", 31400)])

    summary = await advance_service.run(dry_run=False)

    assert fake.posts == [
        (
            "5779",
            {
                "advances": [
                    {
                        "idGlobal": "95270744",
                        "amount": "13900",
                        "date": "2026-10-07",
                        "journal": {"numberTemplate": {"id": TEMPLATE}},
                    }
                ]
            },
        )
    ]
    assert summary["applied"][0]["number"] == "FEUU2394311"
    assert fake.bills["5779"]["status"] == "closed"
    assert alegra.alerts == []


@pytest.mark.asyncio
async def test_running_twice_never_pays_a_bill_twice(alegra):
    fake = alegra([bill(1, "A", "2026-10-01", 13900)], [advance("X", 50000)])

    await advance_service.run(dry_run=False)
    await advance_service.run(dry_run=False)

    assert len(fake.posts) == 1


@pytest.mark.asyncio
async def test_a_dry_run_changes_nothing_and_sends_no_alert(alegra):
    fake = alegra([bill(1, "A", "2026-10-01", 13900)], [advance("X", 100)])

    summary = await advance_service.run(dry_run=True)

    assert fake.posts == [] and alegra.alerts == []
    assert summary["dry_run"] is True and summary["shortfall"][0]["number"] == "A"


@pytest.mark.asyncio
async def test_not_enough_advance_pays_what_it_can_and_alerts_to_top_it_up(alegra):
    fake = alegra(
        [bill(1, "A", "2026-10-01", 13900), bill(2, "B", "2026-10-02", 13900)],
        [advance("X", 20000)],
    )

    summary = await advance_service.run(dry_run=False)

    assert [p[0] for p in fake.posts] == ["1"]
    assert summary["shortfall"][0]["number"] == "B"
    assert len(alegra.alerts) == 1 and alegra.alerts[0][0] == "anticipo-insuficiente"
    assert "13900" in alegra.alerts[0][2]


@pytest.mark.asyncio
async def test_bills_older_than_the_minimum_issue_date_are_left_alone(alegra):
    fake = alegra([bill(1, "OLD", "2026-08-15", 13900)], [advance("X", 50000)])

    summary = await advance_service.run(dry_run=False)

    assert fake.posts == [] and summary["applied"] == [] and summary["shortfall"] == []


@pytest.mark.asyncio
async def test_a_rejected_apply_is_reported_and_stops_the_run(alegra):
    fake = alegra(
        [bill(1, "A", "2026-10-01", 13900), bill(2, "B", "2026-10-02", 13900)],
        [advance("X", 50000)],
        post_status=400,
    )

    summary = await advance_service.run(dry_run=False)

    assert len(fake.posts) == 1
    assert summary["errors"] and alegra.alerts[0][0] == "anticipo-error:1"


@pytest.mark.asyncio
async def test_the_scheduled_run_does_nothing_unless_the_mode_is_on(alegra, monkeypatch):
    fake = alegra([bill(1, "A", "2026-10-01", 13900)], [advance("X", 50000)])
    monkeypatch.setattr(advance_service.settings, "AUTO_ADVANCE_MODE", "off")

    await advance_service.run_scheduled()

    assert fake.posts == []


@pytest.mark.asyncio
async def test_the_scheduled_run_in_simulation_mode_never_writes(alegra, monkeypatch):
    fake = alegra([bill(1, "A", "2026-10-01", 13900)], [advance("X", 50000)])
    monkeypatch.setattr(advance_service.settings, "AUTO_ADVANCE_MODE", "dry_run")

    await advance_service.run_scheduled()

    assert fake.posts == []


@pytest.mark.asyncio
async def test_without_configured_nits_nothing_happens(alegra, monkeypatch):
    fake = alegra([bill(1, "A", "2026-10-01", 13900)], [advance("X", 50000)])
    monkeypatch.setattr(advance_service.settings, "AUTO_ADVANCE_NITS", "")

    summary = await advance_service.run(dry_run=False)

    assert fake.posts == [] and summary["applied"] == []


@pytest.mark.asyncio
async def test_a_request_to_run_only_schedules_work_when_the_mode_is_on(monkeypatch):
    started = []

    async def fake_run_scheduled():
        started.append(1)

    monkeypatch.setattr(advance_service, "run_scheduled", fake_run_scheduled)

    monkeypatch.setattr(advance_service.settings, "AUTO_ADVANCE_MODE", "off")
    advance_service.request_run()
    await asyncio.sleep(0)
    assert started == []

    monkeypatch.setattr(advance_service.settings, "AUTO_ADVANCE_MODE", "on")
    advance_service.request_run()
    await asyncio.sleep(0.01)
    assert started == [1]


@pytest.mark.asyncio
async def test_the_manual_endpoint_simulates_by_default_and_writes_only_when_on(monkeypatch):
    from fastapi import HTTPException

    from routers.facturas import ejecutar_anticipos

    calls = []

    async def fake_run(*, dry_run):
        calls.append(dry_run)
        return {"dry_run": dry_run}

    monkeypatch.setattr("routers.facturas.advance_service.run", fake_run)

    monkeypatch.setattr(advance_service.settings, "AUTO_ADVANCE_MODE", "off")
    assert await ejecutar_anticipos() == {"dry_run": True}
    with pytest.raises(HTTPException) as exc:
        await ejecutar_anticipos(simulacro=False)
    assert exc.value.status_code == 409

    monkeypatch.setattr(advance_service.settings, "AUTO_ADVANCE_MODE", "on")
    assert await ejecutar_anticipos(simulacro=False) == {"dry_run": False}
    assert calls == [True, False]


@pytest.mark.asyncio
async def test_a_successful_causation_asks_for_the_advance_to_be_applied(monkeypatch):
    from tests.test_factura_service import _causacion_service, _CausacionFakes, _item

    requested = []
    monkeypatch.setattr(advance_service, "request_run", lambda: requested.append(1))
    fakes = _CausacionFakes([_item(centro_costo_alegra="12")])
    service = _causacion_service(fakes, monkeypatch)

    await service.causar_factura("f1", {})

    assert requested == [1]
