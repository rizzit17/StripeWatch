"""Core logic tests: golden sample rows, Monday alignment, no look-ahead, self-exclusion, and candidate count."""
from pathlib import Path
import pandas as pd
import numpy as np
import pytest

from stripewatch.loader import load_shipments
from stripewatch.weekly import to_weekly
from stripewatch.baselines import add_baselines
from stripewatch.detect import detect_candidates


@pytest.fixture(scope="module")
def base_data():
    shipments = load_shipments()
    weekly = to_weekly(shipments)
    with_baselines = add_baselines(weekly, drop_first_weeks=True)
    return shipments, weekly, with_baselines


def test_mondays_and_counts(base_data):
    shipments, weekly, with_baselines = base_data
    # 7 routes * 104 weeks = 728 route-weeks
    assert len(weekly) == 728
    assert weekly["route"].nunique() == 7
    # All week_of must be Mondays
    assert (weekly["week_of"].dt.weekday == 0).all()
    # 7 first weeks dropped -> 721 evaluable
    assert len(with_baselines) == 721


def test_golden_three_rows(base_data):
    _, _, df = base_data

    # 1. Delhi-Jaipur 2024-11-11: 4.17, +35.5%, +21.0%
    r1 = df[(df["route"] == "Delhi-Jaipur") & (df["week_of"] == "2024-11-11")].iloc[0]
    assert round(r1["c"], 2) == 4.17
    assert round(r1["vs_own_pct"], 1) == 35.5
    assert round(r1["vs_peer_pct"], 1) == 21.0

    # 2. Ahmedabad-Mumbai 2025-01-20: 3.29, +29.5%, +22.5%
    r2 = df[(df["route"] == "Ahmedabad-Mumbai") & (df["week_of"] == "2025-01-20")].iloc[0]
    assert round(r2["c"], 2) == 3.29
    assert round(r2["vs_own_pct"], 1) == 29.5
    assert round(r2["vs_peer_pct"], 1) == 22.5

    # 3. Mumbai-Pune 2025-09-15: 3.98, +9.2%, +23.6%
    r3 = df[(df["route"] == "Mumbai-Pune") & (df["week_of"] == "2025-09-15")].iloc[0]
    assert round(r3["c"], 2) == 3.98
    assert round(r3["vs_own_pct"], 1) == 9.2
    assert round(r3["vs_peer_pct"], 1) == 23.6


def test_peer_self_exclusion(base_data):
    """Short routes has only 2 routes: Mumbai-Pune and Delhi-Jaipur.
    Therefore, Mumbai-Pune's peer_avg MUST equal Delhi-Jaipur's c in that same week."""
    _, weekly, df = base_data
    mp_rows = df[df["route"] == "Mumbai-Pune"].set_index("week_of")
    dj_weekly = weekly[weekly["route"] == "Delhi-Jaipur"].set_index("week_of")

    common_weeks = mp_rows.index.intersection(dj_weekly.index)
    for wk in common_weeks[:10]:
        expected_peer = dj_weekly.loc[wk, "c"]
        actual_peer = mp_rows.loc[wk, "peer_avg"]
        assert pytest.approx(actual_peer, abs=1e-6) == expected_peer


def test_fewer_than_eight_priors(base_data):
    """Verify that earlier weeks use available priors without padding or look-ahead."""
    _, _, df = base_data
    # For every route, week 2 should have n_prior == 1, week 3 has n_prior == 2, etc.
    for route, grp in df.groupby("route"):
        grp = grp.sort_values("week_of").reset_index(drop=True)
        # First evaluable row is index 0 (which was week 2 of the dataset)
        assert grp.iloc[0]["n_prior"] == 1
        assert grp.iloc[1]["n_prior"] == 2
        assert grp.iloc[6]["n_prior"] == 7
        assert grp.iloc[7]["n_prior"] == 8
        assert grp.iloc[20]["n_prior"] == 8


def test_no_look_ahead_leakage(base_data):
    """Modifying future shipments must NOT affect past baselines."""
    shipments, _, original_baselines = base_data

    # Copy and tamper with shipments strictly after 2024-06-03 (a Monday)
    cutoff = "2024-06-03"
    tampered = shipments.copy()
    mask_future = tampered["shipment_date"] >= cutoff
    tampered.loc[mask_future, "freight_cost_inr"] *= 10.0

    tampered_weekly = to_weekly(tampered)
    tampered_baselines = add_baselines(tampered_weekly, drop_first_weeks=True)

    # Filter to weeks strictly before 2024-06-03
    orig_past = original_baselines[original_baselines["week_of"] < cutoff].sort_values(["route", "week_of"]).reset_index(drop=True)
    tamp_past = tampered_baselines[tampered_baselines["week_of"] < cutoff].sort_values(["route", "week_of"]).reset_index(drop=True)

    # The past metrics and baselines must remain identical
    np.testing.assert_allclose(orig_past["c"], tamp_past["c"])
    np.testing.assert_allclose(orig_past["own_avg"], tamp_past["own_avg"])
    np.testing.assert_allclose(orig_past["peer_avg"], tamp_past["peer_avg"])
    np.testing.assert_allclose(orig_past["vs_own_pct"], tamp_past["vs_own_pct"])
    np.testing.assert_allclose(orig_past["vs_peer_pct"], tamp_past["vs_peer_pct"])


def test_candidates_match_gold_set(base_data):
    _, _, df = base_data
    candidates = detect_candidates(df)

    assert len(candidates) == 19

    gold_path = Path("eval/gold_candidates.csv")
    assert gold_path.exists()
    gold_df = pd.read_csv(gold_path)
    assert len(gold_df) == 19

    # Compare set of (route, week_of)
    cand_set = set(zip(candidates["route"], candidates["week_of"].dt.strftime("%Y-%m-%d")))
    gold_set = set(zip(gold_df["route"], gold_df["week_of"]))
    assert cand_set == gold_set

    # Compare values
    for _, gold_row in gold_df.iterrows():
        cand_match = candidates[
            (candidates["route"] == gold_row["route"]) &
            (candidates["week_of"] == gold_row["week_of"])
        ].iloc[0]
        assert pytest.approx(cand_match["c"], abs=0.01) == gold_row["c"]
        assert pytest.approx(cand_match["vs_own_pct"], abs=0.1) == gold_row["vs_own_pct"]
        assert pytest.approx(cand_match["vs_peer_pct"], abs=0.1) == gold_row["vs_peer_pct"]
