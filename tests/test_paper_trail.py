"""Unit tests for paper trail strip computation."""
import pytest
from stripewatch.paper_trail import compute_paper_trail
from stripewatch.notes import get_notes_dict


def test_paper_trail_chennai_bangalore_flood_window_fail():
    """Verify Chennai-Bangalore 2025-03-10 shows N001 closest with Window = FAIL."""
    notes_map = get_notes_dict()
    row = {
        "route": "Chennai-Bangalore",
        "week_of": "2025-03-10",
        "vs_own_pct": 22.1,
        "vs_peer_pct": 33.8
    }
    # Simulated top retrieved notes including N001
    retrieved_hits = [
        {"id": "N003", "score": 0.68},
        {"id": "N001", "score": 0.57},
        {"id": "N008", "score": 0.51},
        {"id": "N009", "score": 0.49}
    ]

    trail = compute_paper_trail(
        row=row,
        retrieved_hits=retrieved_hits,
        verdict_justified=False,
        matched_note_id=None,
        notes_map=notes_map
    )

    assert trail["closest_rejected_note"] == "N001"
    assert trail["evaluated_note_id"] == "N001"

    tickets = trail["tickets"]
    assert len(tickets) == 5

    # Ticket 1: Spotted
    assert tickets[0]["name"] == "Spotted"
    assert tickets[0]["status"] == "PASS"

    # Ticket 2: Searched
    assert tickets[1]["name"] == "Searched"
    assert "N001" in tickets[1]["chips"]

    # Ticket 3: Route
    assert tickets[2]["name"] == "Route"
    assert tickets[2]["status"] == "PASS"

    # Ticket 4: Window
    assert tickets[3]["name"] == "Window"
    assert tickets[3]["status"] == "FAIL"

    # Ticket 5: Effect & size (unevaluated because window failed)
    assert tickets[4]["name"] == "Effect & size"
    assert tickets[4]["status"] == "UNEVALUATED"
    assert tickets[4]["stamp"] == "—"


def test_paper_trail_ahmedabad_mumbai_festival_all_pass():
    """Verify Ahmedabad-Mumbai 2025-01-20 shows N002 all PASS."""
    notes_map = get_notes_dict()
    row = {
        "route": "Ahmedabad-Mumbai",
        "week_of": "2025-01-20",
        "vs_own_pct": 29.5,
        "vs_peer_pct": 22.5
    }
    retrieved_hits = [
        {"id": "N002", "score": 0.72},
        {"id": "N003", "score": 0.55}
    ]

    trail = compute_paper_trail(
        row=row,
        retrieved_hits=retrieved_hits,
        verdict_justified=True,
        matched_note_id="N002",
        notes_map=notes_map
    )

    assert trail["evaluated_note_id"] == "N002"

    tickets = trail["tickets"]
    assert len(tickets) == 5

    for t in tickets:
        assert t["status"] == "PASS"
        assert t["stamp"] in ["SPOTTED", "SEARCHED", "PASS"]
