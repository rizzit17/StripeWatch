"""Unit and API tests for Backend B: Human Review Queue."""
import csv
import json
import pytest
from fastapi.testclient import TestClient
from stripewatch.server import app
from stripewatch.review import (
    load_review_state,
    save_review_state,
    update_review_item,
    export_review_csv,
    REVIEW_STATE_FILE
)


@pytest.fixture(autouse=True)
def clean_review_state():
    """Backup and restore review state for test isolation."""
    original = load_review_state()
    yield
    save_review_state(original)


def test_review_api_get():
    """Verify GET /api/review returns all 19 candidates with default 'open' status."""
    client = TestClient(app)
    res = client.get("/api/review")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 19
    for it in items:
        assert "review_status" in it
        assert it["review_status"] in ["open", "confirmed", "dismissed"]


def test_review_api_put_valid():
    """Verify valid PUT updates review status and note."""
    client = TestClient(app)
    route = "Ahmedabad-Mumbai"
    week_of = "2025-01-20"

    res = client.put(f"/api/review/{route}/{week_of}", json={
        "status": "confirmed",
        "note": "Checked with operations: festival surcharges approved."
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "confirmed"
    assert data["note"] == "Checked with operations: festival surcharges approved."

    # Check that GET reflects the update
    res2 = client.get("/api/review")
    matched = next(x for x in res2.json() if x["route"] == route and x["week_of"] == week_of)
    assert matched["review_status"] == "confirmed"
    assert matched["review_note"] == "Checked with operations: festival surcharges approved."


def test_review_api_put_invalid_status():
    """Verify PUT with invalid status returns HTTP 400."""
    client = TestClient(app)
    res = client.put("/api/review/Ahmedabad-Mumbai/2025-01-20", json={
        "status": "invalid_status",
        "note": "valid note"
    })
    assert res.status_code == 400


def test_review_api_put_non_candidate_row():
    """Verify PUT for a non-candidate row returns HTTP 400."""
    client = TestClient(app)
    res = client.put("/api/review/Delhi-Jaipur/2024-01-08", json={
        "status": "confirmed",
        "note": "Not a candidate"
    })
    assert res.status_code == 400


def test_review_api_put_long_note():
    """Verify PUT with note > 280 chars returns HTTP 400."""
    client = TestClient(app)
    long_note = "A" * 281
    res = client.put("/api/review/Ahmedabad-Mumbai/2025-01-20", json={
        "status": "confirmed",
        "note": long_note
    })
    assert res.status_code == 400


def test_review_api_put_extra_keys():
    """Verify PUT with extra keys returns HTTP 400."""
    client = TestClient(app)
    res = client.put("/api/review/Ahmedabad-Mumbai/2025-01-20", json={
        "status": "confirmed",
        "note": "valid",
        "extra_field": "disallowed"
    })
    assert res.status_code == 400


def test_review_export_csv():
    """Verify review export produces expected columns and rows."""
    dest = export_review_csv()
    assert dest.exists()

    with open(dest, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        assert fieldnames == ["route", "week_of", "verdict", "matched_note_id", "review_status", "review_note"]
        rows = list(reader)
        assert len(rows) == 19
