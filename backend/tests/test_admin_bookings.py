"""Isolated route tests: no production database or parking data is used."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
import app.main as main

@pytest.fixture
def client():
    try:
        with TestClient(main.app) as client:
            yield client
    finally:
        main.app.dependency_overrides.clear()

def account(role):
    return SimpleNamespace(id=8, username="operator", role=role)

def booking():
    return SimpleNamespace(id=42, user_id=7, slot_id=3, slot=SimpleNamespace(label="P-3"), vehicle="TEST CAR", started_at=datetime.now(timezone.utc)-timedelta(minutes=5), ended_at=None, amount_cents=None)

@pytest.mark.parametrize("path", ["/admin/dashboard", "/admin/bookings/42/checkout", "/admin/releases"])
def test_ordinary_user_denied(client, monkeypatch, path):
    main.app.dependency_overrides[main.current_user] = lambda: account("user")
    session = MagicMock()
    monkeypatch.setattr(main, "Session", session)
    response = client.post(path) if path.endswith("checkout") else client.get(path)
    assert response.status_code == 403
    session.assert_not_called()
    session.begin.assert_not_called()

def test_unauthenticated_checkout_denied(client):
    assert client.post("/admin/bookings/42/checkout").status_code in (401, 403)

def test_manual_checkout_is_locked_idempotent_and_non_destructive(client, monkeypatch):
    main.app.dependency_overrides[main.current_user] = lambda: account("admin")
    b = booking()
    db = MagicMock()
    db.scalar.return_value = b
    db.get.return_value = SimpleNamespace(username="parking_owner")
    factory = MagicMock()
    factory.begin.return_value.__enter__.return_value = db
    monkeypatch.setattr(main, "Session", factory)
    first = client.post("/admin/bookings/42/checkout", json={"reason":"  Vehicle left the campus  "})
    second = client.post("/admin/bookings/42/checkout", json={"reason":"Different retry reason must not overwrite original"})
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["ended_at"] and first.json()["amount_cents"] == 2000
    sql = str(db.scalar.call_args.args[0].compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in sql
    db.delete.assert_not_called()
    assert b.user_id == 7 and b.slot_id == 3
    db.add.assert_called_once()
    audit = db.add.call_args.args[0]
    assert audit.action == "manual_checkout" and audit.actor_id == 8
    assert audit.slot_id == 3
    assert audit.after["booking_id"] == 42
    assert audit.after["admin_username"] == "operator"
    assert audit.after["username"] == "parking_owner"
    assert audit.after["released_at"] == b.ended_at.isoformat()
    assert audit.after["space"] == "P-3"
    assert audit.after["reason"] == "Vehicle left the campus"

def test_missing_booking_returns_404(client, monkeypatch):
    main.app.dependency_overrides[main.current_user] = lambda: account("admin")
    db = MagicMock()
    db.scalar.return_value = None
    factory = MagicMock()
    factory.begin.return_value.__enter__.return_value = db
    monkeypatch.setattr(main, "Session", factory)
    assert client.post("/admin/bookings/999/checkout", json={"reason":"Vehicle departed"}).status_code == 404

def test_dashboard_contains_booking_owner_name(client, monkeypatch):
    main.app.dependency_overrides[main.current_user] = lambda: account("admin")
    db = MagicMock()
    db.execute.return_value = [(booking(), "parking_owner")]
    db.scalars.return_value = [3]
    factory = MagicMock()
    factory.return_value.__enter__.return_value = db
    monkeypatch.setattr(main, "Session", factory)
    response = client.get("/admin/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert data["active"] == 1
    assert data["bookings"][0]["username"] == "parking_owner"
    assert "password_hash" not in data["bookings"][0]


def test_release_history_is_admin_only_bounded_and_newest_first(client, monkeypatch):
    main.app.dependency_overrides[main.current_user] = lambda: account("admin")
    entry = SimpleNamespace(id=12, actor_id=8, after={"booking_id":42,"admin_username":"operator","username":"parking_owner","space":"P-3","vehicle":"TEST CAR","released_at":"2026-11-02T10:00:00+00:00","amount_cents":2000,"reason":"Vehicle departed"})
    db = MagicMock()
    db.scalars.return_value = [entry]
    factory = MagicMock()
    factory.return_value.__enter__.return_value = db
    monkeypatch.setattr(main, "Session", factory)
    response = client.get("/admin/releases")
    assert response.status_code == 200
    assert response.json() == [{"id":12,"admin_id":8,**entry.after}]
    sql = str(db.scalars.call_args.args[0].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds":True}))
    assert "manual_checkout" in sql and "ORDER BY slot_audit.id DESC" in sql and "LIMIT 100" in sql

def test_empty_release_history(client, monkeypatch):
    main.app.dependency_overrides[main.current_user] = lambda: account("admin")
    db = MagicMock()
    db.scalars.return_value = []
    factory = MagicMock()
    factory.return_value.__enter__.return_value = db
    monkeypatch.setattr(main, "Session", factory)
    assert client.get("/admin/releases").json() == []


@pytest.mark.parametrize("body", [{}, {"reason":""}, {"reason":"   \t\n"}, {"reason":"x"*501}, {"reason":None}, {"reason":123}, {"reason":"Valid reason", "extra":"not allowed"}])
def test_missing_or_invalid_reason_rejected_before_database_write(client, monkeypatch, body):
    main.app.dependency_overrides[main.current_user] = lambda: account("admin")
    factory = MagicMock()
    monkeypatch.setattr(main, "Session", factory)
    assert client.post("/admin/bookings/42/checkout", json=body).status_code == 422
    factory.begin.assert_not_called()

def test_missing_body_rejected(client, monkeypatch):
    main.app.dependency_overrides[main.current_user] = lambda: account("admin")
    factory = MagicMock()
    monkeypatch.setattr(main, "Session", factory)
    assert client.post("/admin/bookings/42/checkout").status_code == 422
    factory.begin.assert_not_called()

def test_reason_length_boundary():
    assert main.ManualReleaseInput(reason="x"*500).reason == "x"*500
    assert main.ManualReleaseInput(reason=" x ").reason == "x"
