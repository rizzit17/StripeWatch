"""Tests for excess-spend estimation and priority ranking (Feature 2)."""
import pandas as pd
import pytest

from stripewatch.loader import load_shipments
from stripewatch.weekly import to_weekly
from stripewatch.baselines import add_baselines
from stripewatch.detect import detect_candidates


def test_excess_spend_formula_and_non_negative():
    df = load_shipments()
    w = to_weekly(df)
    b = add_baselines(w)
    
    # Formula check on a known candidate row: Delhi-Jaipur 2024-11-11
    dj_row = b[(b["route"] == "Delhi-Jaipur") & (b["week_of"] == "2024-11-11")].iloc[0]
    expected_dj = round((dj_row["c"] - dj_row["own_avg"]) * dj_row["tonne_km"])
    assert int(dj_row["excess_inr"]) == expected_dj
    
    # All excess_inr must be non-negative
    assert (b["excess_inr"] >= 0).all()


def test_excess_spend_totals_within_tolerance():
    df = load_shipments()
    w = to_weekly(df)
    b = add_baselines(w)
    cand = detect_candidates(b)
    
    # Format week strings for matching
    cand = cand.copy()
    cand["week_str"] = pd.to_datetime(cand["week_of"]).dt.strftime("%Y-%m-%d")
    
    just_mask = (
        ((cand["route"] == "Ahmedabad-Mumbai") & (cand["week_str"] == "2025-01-20")) |
        ((cand["route"] == "Chennai-Bangalore") & (cand["week_str"].isin(["2025-02-24", "2025-03-03"])))
    )
    
    justified_total = cand[just_mask]["excess_inr"].sum()
    flagged_total = cand[~just_mask]["excess_inr"].sum()
    
    # Expected: about ₹1,28,127 flagged and ₹77,960 justified (tolerance ±₹500)
    assert abs(flagged_total - 128127) <= 500, f"Flagged total was {flagged_total}, expected ~128127"
    assert abs(justified_total - 77960) <= 500, f"Justified total was {justified_total}, expected ~77960"
