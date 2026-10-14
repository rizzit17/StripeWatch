"""Tests for 'Try to fool it' API endpoint (Feature 1).

Verifies the 8 canonical adversarial presets against the live validator API.
"""
import pytest
from fastapi.testclient import TestClient

from stripewatch.server import app

client = TestClient(app)


def test_preset_1_chennai_bangalore_n001_expired_window():
    # 1. Chennai-Bangalore 2025-03-10 + N001 -> rejected: window ended 2025-03-08
    resp = client.post("/api/validate", json={
        "route": "Chennai-Bangalore",
        "week_of": "2025-03-10",
        "note_id": "N001"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["justified"] is False
    assert data["checks"]["window_overlaps"] is False
    assert "2025-03-08" in data["why_not"] or "does not overlap" in data["why_not"]


def test_preset_2_chennai_bangalore_n009_no_rise():
    # 2. Chennai-Bangalore 2025-03-17 + N009 -> rejected: note does not describe a cost rise
    resp = client.post("/api/validate", json={
        "route": "Chennai-Bangalore",
        "week_of": "2025-03-17",
        "note_id": "N009"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["justified"] is False
    assert data["checks"]["effect_is_cost_rise"] is False
    assert "does not describe a cost rise" in data["why_not"]


def test_preset_3_mumbai_pune_n006_no_disruption():
    # 3. Mumbai-Pune 2025-09-15 + N006 -> rejected: note says no disruption
    resp = client.post("/api/validate", json={
        "route": "Mumbai-Pune",
        "week_of": "2025-09-15",
        "note_id": "N006"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["justified"] is False
    assert data["checks"]["effect_is_cost_rise"] is False


def test_preset_4_mumbai_pune_n001_different_route():
    # 4. Mumbai-Pune 2025-09-15 + N001 -> rejected: different route
    resp = client.post("/api/validate", json={
        "route": "Mumbai-Pune",
        "week_of": "2025-09-15",
        "note_id": "N001"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["justified"] is False
    assert data["checks"]["route_in_scope"] is False
    assert "Chennai-Bangalore" in data["why_not"]


def test_preset_5_mumbai_delhi_n003_magnitude_cap():
    # 5. Mumbai-Delhi 2025-05-12 + N003 -> rejected: +11.6% exceeds 7% + 3pp cap (10%)
    resp = client.post("/api/validate", json={
        "route": "Mumbai-Delhi",
        "week_of": "2025-05-12",
        "note_id": "N003"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["justified"] is False
    assert data["checks"]["magnitude_ok"] is False


def test_preset_6_mumbai_pune_n003_nationwide_peer_outlier():
    # 6. Mumbai-Pune 2025-06-23 + N003 -> rejected: nationwide note can't explain a +20.6% peer gap
    resp = client.post("/api/validate", json={
        "route": "Mumbai-Pune",
        "week_of": "2025-06-23",
        "note_id": "N003"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["justified"] is False
    assert data["checks"]["not_peer_outlier_for_universal"] is False


def test_preset_7_any_route_n004_out_of_scope():
    # 7. Any route + N004 -> rejected: out of scope
    resp = client.post("/api/validate", json={
        "route": "Delhi-Jaipur",
        "week_of": "2024-11-11",
        "note_id": "N004"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["justified"] is False
    assert data["checks"]["route_in_scope"] is False


def test_preset_8_ahmedabad_mumbai_n002_accepted():
    # 8. Ahmedabad-Mumbai 2025-01-20 + N002 -> accepted (positive control)
    resp = client.post("/api/validate", json={
        "route": "Ahmedabad-Mumbai",
        "week_of": "2025-01-20",
        "note_id": "N002"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["justified"] is True
    assert all(data["checks"].values())
    assert data["why_not"] == ""
