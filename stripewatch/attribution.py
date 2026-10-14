"""Attribution check: analyzes whether an episode of cost rises is route-wide or concentrated.

Guiding principle:
- Describes factual evidence from shipment data (rises by transporter or material).
- Never claims or speculates about root causes.
- Strictly deterministic, templated plain-English explanations (no LLM).
"""
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np


def extract_episodes(candidate_weeks: List[pd.Timestamp | str]) -> List[List[pd.Timestamp]]:
    """Group sorted candidate weeks into episodes where consecutive weeks have gap <= 3 weeks (<= 28 days)."""
    if not candidate_weeks:
        return []
    
    dt_weeks = sorted([pd.to_datetime(w) for w in candidate_weeks])
    episodes: List[List[pd.Timestamp]] = []
    curr_ep: List[pd.Timestamp] = []
    
    for wk in dt_weeks:
        if not curr_ep:
            curr_ep.append(wk)
        else:
            gap_days = (wk - curr_ep[-1]).days
            if gap_days <= 28:
                curr_ep.append(wk)
            else:
                episodes.append(curr_ep)
                curr_ep = [wk]
    if curr_ep:
        episodes.append(curr_ep)
        
    return episodes


def analyze_dimension(
    ep_shipments: pd.DataFrame,
    pre_shipments: pd.DataFrame,
    dimension: str,
    all_values: List[str]
) -> Dict[str, Any]:
    """Analyze cost change per subgroup in a dimension (e.g. transporter, material)."""
    group_stats = []
    
    for val in sorted(all_values):
        g_ep = ep_shipments[ep_shipments[dimension] == val]
        g_pre = pre_shipments[pre_shipments[dimension] == val]
        
        n_ep = len(g_ep)
        n_pre = len(g_pre)
        
        if n_ep < 3 or n_pre < 3:
            group_stats.append({
                "group": val,
                "status": "too few shipments",
                "n_pre": n_pre,
                "n_ep": n_ep,
                "pct": None
            })
        else:
            tk_ep = (g_ep["quantity_tonnes"] * g_ep["distance_km"]).sum()
            tk_pre = (g_pre["quantity_tonnes"] * g_pre["distance_km"]).sum()
            c_ep = (g_ep["freight_cost_inr"].sum() / tk_ep) if tk_ep > 0 else 0.0
            c_pre = (g_pre["freight_cost_inr"].sum() / tk_pre) if tk_pre > 0 else 0.0
            pct = ((c_ep / c_pre - 1) * 100) if c_pre > 0 else 0.0
            
            group_stats.append({
                "group": val,
                "status": "eligible",
                "n_pre": n_pre,
                "n_ep": n_ep,
                "pct": round(pct, 1)
            })
            
    eligible = [g for g in group_stats if g["status"] == "eligible"]
    
    if not eligible:
        return {
            "verdict": "too few shipments to attribute",
            "groups": group_stats
        }
        
    pcts = [g["pct"] for g in eligible]
    med_pct = float(np.median(pcts))
    half_med = med_pct * 0.5
    
    # If median rise is positive and every eligible group's rise is >= half the median group rise -> Spread
    all_spread = (med_pct > 0) and all(g["pct"] >= half_med for g in eligible) and (min(pcts) > 0)
    if all_spread:
        min_p = min(pcts)
        max_p = max(pcts)
        verdict = f"Spread across all {len(eligible)} {dimension}s (rises between +{min_p:.1f}% and +{max_p:.1f}%)"
    else:
        top_g = max(eligible, key=lambda g: g["pct"])
        top_name = top_g["group"]
        top_pct = top_g["pct"]
        
        # Calculate combined rest
        rest_ep = ep_shipments[ep_shipments[dimension] != top_name]
        rest_pre = pre_shipments[pre_shipments[dimension] != top_name]
        
        tk_rest_ep = (rest_ep["quantity_tonnes"] * rest_ep["distance_km"]).sum()
        tk_rest_pre = (rest_pre["quantity_tonnes"] * rest_pre["distance_km"]).sum()
        c_rest_ep = (rest_ep["freight_cost_inr"].sum() / tk_rest_ep) if tk_rest_ep > 0 else 0.0
        c_rest_pre = (rest_pre["freight_cost_inr"].sum() / tk_rest_pre) if tk_rest_pre > 0 else 0.0
        rest_pct = ((c_rest_ep / c_rest_pre - 1) * 100) if c_rest_pre > 0 else 0.0
        
        verdict = f"Concentrated: {top_name} rose +{top_pct:.1f}% vs +{rest_pct:.1f}% for the rest"
        
    return {
        "verdict": verdict,
        "groups": group_stats
    }


def compute_route_attribution(
    shipments_df: pd.DataFrame,
    candidates_df: pd.DataFrame
) -> Dict[str, List[Dict[str, Any]]]:
    """Compute attribution episodes and verdicts for all routes with candidate weeks.

    Returns:
        Dict mapping route name to list of episode attribution records.
    """
    results: Dict[str, List[Dict[str, Any]]] = {}
    
    for route in sorted(candidates_df["route"].unique()):
        r_cands = candidates_df[candidates_df["route"] == route].sort_values("week_of")
        cand_weeks = r_cands["week_of"].tolist()
        episodes = extract_episodes(cand_weeks)
        
        r_shipments = shipments_df[shipments_df["route"] == route].copy()
        
        ep_records = []
        for ep in episodes:
            ep_start = ep[0]
            ep_end = ep[-1] + pd.Timedelta(days=6)
            pre_start = ep_start - pd.Timedelta(weeks=8)
            pre_end = ep_start - pd.Timedelta(days=1)
            
            record: Dict[str, Any] = {
                "route": route,
                "start": ep_start.strftime("%Y-%m-%d"),
                "end": ep_end.strftime("%Y-%m-%d"),
                "weeks_count": len(ep),
                "weeks": [w.strftime("%Y-%m-%d") for w in ep]
            }
            
            # Single-week episodes have insufficient data for attribution
            if len(ep) == 1:
                record["verdict"] = "too few shipments to attribute"
                record["transporter"] = {"verdict": "too few shipments to attribute", "groups": []}
                record["material"] = {"verdict": "too few shipments to attribute", "groups": []}
                ep_records.append(record)
                continue
                
            ep_s = r_shipments[
                (r_shipments["shipment_date"] >= ep_start) & (r_shipments["shipment_date"] <= ep_end)
            ]
            pre_s = r_shipments[
                (r_shipments["shipment_date"] >= pre_start) & (r_shipments["shipment_date"] <= pre_end)
            ]
            
            trans_res = analyze_dimension(
                ep_s, pre_s, "transporter", sorted(r_shipments["transporter"].unique())
            )
            mat_res = analyze_dimension(
                ep_s, pre_s, "material", sorted(r_shipments["material"].unique())
            )
            
            record["verdict"] = trans_res["verdict"]
            record["transporter"] = trans_res
            record["material"] = mat_res
            ep_records.append(record)
            
        results[route] = ep_records
        
    return results
