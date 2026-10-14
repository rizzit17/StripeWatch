"""Tests for episode-level attribution analysis (Feature 4)."""
import pandas as pd
import pytest

from stripewatch.loader import load_shipments
from stripewatch.weekly import to_weekly
from stripewatch.baselines import add_baselines
from stripewatch.detect import detect_candidates
from stripewatch.attribution import extract_episodes, analyze_dimension, compute_route_attribution


def test_extract_episodes():
    # Gap <= 28 days -> same episode
    weeks = [
        "2025-09-15",
        "2025-10-06",  # 21 days
        "2025-10-20",  # 14 days
        "2025-11-24",  # 35 days -> new episode
    ]
    eps = extract_episodes(weeks)
    assert len(eps) == 2
    assert len(eps[0]) == 3
    assert len(eps[1]) == 1


def test_synthetic_concentrated_vs_spread():
    # Construct synthetic shipments
    dates_pre = pd.date_range("2025-07-21", "2025-09-14", freq="W-MON")
    dates_ep = pd.date_range("2025-09-15", "2025-10-20", freq="W-MON")
    
    rows = []
    # Transporter A: normal in pre, 100% hike in ep
    for d in dates_pre:
        rows.append({"shipment_date": d, "transporter": "CarrierA", "freight_cost_inr": 1000, "quantity_tonnes": 10, "distance_km": 100})
        rows.append({"shipment_date": d, "transporter": "CarrierB", "freight_cost_inr": 1000, "quantity_tonnes": 10, "distance_km": 100})
        rows.append({"shipment_date": d, "transporter": "CarrierC", "freight_cost_inr": 1000, "quantity_tonnes": 10, "distance_km": 100})
        
    for d in dates_ep:
        # CarrierA spikes, CarrierB and CarrierC stay flat
        rows.append({"shipment_date": d, "transporter": "CarrierA", "freight_cost_inr": 2000, "quantity_tonnes": 10, "distance_km": 100})
        rows.append({"shipment_date": d, "transporter": "CarrierB", "freight_cost_inr": 1000, "quantity_tonnes": 10, "distance_km": 100})
        rows.append({"shipment_date": d, "transporter": "CarrierC", "freight_cost_inr": 1000, "quantity_tonnes": 10, "distance_km": 100})
        
    df_syn = pd.DataFrame(rows)
    ep_s = df_syn[df_syn["shipment_date"] >= "2025-09-15"]
    pre_s = df_syn[df_syn["shipment_date"] < "2025-09-15"]
    
    res = analyze_dimension(ep_s, pre_s, "transporter", ["CarrierA", "CarrierB", "CarrierC"])
    assert res["verdict"].startswith("Concentrated: CarrierA rose")
    
    # Uniform rise: all 3 carriers rise +20%
    rows_uniform = []
    for d in dates_pre:
        for c in ["CarrierA", "CarrierB", "CarrierC"]:
            rows_uniform.append({"shipment_date": d, "transporter": c, "freight_cost_inr": 1000, "quantity_tonnes": 10, "distance_km": 100})
    for d in dates_ep:
        for c in ["CarrierA", "CarrierB", "CarrierC"]:
            rows_uniform.append({"shipment_date": d, "transporter": c, "freight_cost_inr": 1200, "quantity_tonnes": 10, "distance_km": 100})
            
    df_uni = pd.DataFrame(rows_uniform)
    res_uni = analyze_dimension(
        df_uni[df_uni["shipment_date"] >= "2025-09-15"],
        df_uni[df_uni["shipment_date"] < "2025-09-15"],
        "transporter",
        ["CarrierA", "CarrierB", "CarrierC"]
    )
    assert res_uni["verdict"].startswith("Spread across all 3 transporters")


def test_few_shipments_handling():
    # Only 1 shipment in pre-window
    pre_s = pd.DataFrame([{"transporter": "CarrierA", "freight_cost_inr": 1000, "quantity_tonnes": 10, "distance_km": 100}])
    ep_s = pd.DataFrame([{"transporter": "CarrierA", "freight_cost_inr": 1500, "quantity_tonnes": 10, "distance_km": 100}] * 5)
    
    res = analyze_dimension(ep_s, pre_s, "transporter", ["CarrierA"])
    assert res["verdict"] == "too few shipments to attribute"
    assert res["groups"][0]["status"] == "too few shipments"


def test_real_mumbai_pune_episode():
    df = load_shipments()
    w = to_weekly(df)
    b = add_baselines(w)
    cand = detect_candidates(b)
    
    attr = compute_route_attribution(df, cand)
    assert "Mumbai-Pune" in attr
    episodes = attr["Mumbai-Pune"]
    assert len(episodes) == 2
    
    # First episode is single week -> too few shipments
    assert episodes[0]["verdict"] == "too few shipments to attribute"
    
    # Second episode (fall 2025) is route-wide across all 5 transporters
    assert episodes[1]["verdict"].startswith("Spread across all 5 transporters")
