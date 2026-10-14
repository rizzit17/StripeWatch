"""Tests for weekly watch mode (Feature 10)."""
import pytest
import pandas as pd

from stripewatch.config import EVAL_DIR
from stripewatch.watch import watch_week


def test_watch_rejects_non_monday():
    # 2024-11-12 is a Tuesday
    with pytest.raises(ValueError, match="not a Monday"):
        watch_week("2024-11-12")


def test_watch_gold_weeks_match_full_run():
    gold_df = pd.read_csv(EVAL_DIR / "gold_candidates.csv").fillna({"expected_note_id": ""})
    
    # Check 3 anchor rows via watch
    anchors = [
        ("Delhi-Jaipur", "2024-11-11", "Yes", ""),
        ("Ahmedabad-Mumbai", "2025-01-20", "No (justified)", "N002"),
        ("Mumbai-Pune", "2025-09-15", "Yes", "")
    ]
    
    for route, wk, exp_flagged, exp_note in anchors:
        findings = watch_week(wk)
        # Find matching route in findings
        matching = [f for f in findings if f["route"] == route]
        assert len(matching) == 1, f"Expected 1 finding for {route} on {wk}, got {len(matching)}"
        cand = matching[0]
        assert cand["flagged"] == exp_flagged
        assert cand["matched_note_id"] == exp_note
