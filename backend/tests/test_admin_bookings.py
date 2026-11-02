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

@pytest.mark.parametrize("path", ["/admin/dashboard", "/admin/bookings/42/checkout"])
def test_ordinary_user_denied(client, monkeypatch, path):
    main.app.dependency_overrides[main.current_user] = lambda: account("user")
    session = MagicMock()
    monkeypatch.setattr(main, "Session", session)
    response = client.get(path) if path.endswith("dashboard") else client.post(path)
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
    factory = MagicMock()
    factory.begin.return_value.__enter__.return_value = db
    monkeypatch.setattr(main, "Session", factory)
    first = client.post("/admin/bookings/42/checkout")
    second = client.post("/admin/bookings/42/checkout")
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["ended_at"] and first.json()["amount_cents"] == 2000
    sql = str(db.scalar.call_args.args[0].compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in sql
    db.delete.assert_not_called()
    assert b.user_id == 7 and b.slot_id == 3

def test_missing_booking_returns_404(client, monkeypatch):
    main.app.dependency_overrides[main.current_user] = lambda: account("admin")
    db = MagicMock()
    db.scalar.return_value = None
    factory = MagicMock()
    factory.begin.return_value.__enter__.return_value = db
    monkeypatch.setattr(main, "Session", factory)
    assert client.post("/admin/bookings/999/checkout").status_code == 404

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
