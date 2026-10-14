"""Sensitivity analysis for threshold tuning across own history and peer thresholds."""
import pandas as pd
from typing import List, Dict, Any

from stripewatch.loader import load_shipments
from stripewatch.weekly import to_weekly
from stripewatch.baselines import add_baselines
from stripewatch.detect import is_candidate_mask


def run_sensitivity_analysis() -> List[Dict[str, Any]]:
    """Run grid analysis over FLAG_OWN_PCT and FLAG_PEER_PCT.

    Grid:
      FLAG_OWN in [6.0, 8.0, 10.0]
      FLAG_PEER in [15.0, 20.0, 25.0]
      FLAG_OWN_SOFT = 5.0
    """
    shipments = load_shipments()
    weekly = to_weekly(shipments)
    df = add_baselines(weekly, drop_first_weeks=True)

    own_grid = [6.0, 8.0, 10.0]
    peer_grid = [15.0, 20.0, 25.0]
    soft_own = 5.0

    results = []
    for own in own_grid:
        for peer in peer_grid:
            mask = is_candidate_mask(df, own_pct=own, own_soft_pct=soft_own, peer_pct=peer)
            cand_df = df[mask]
            count = len(cand_df)
            routes = cand_df["route"].value_counts().to_dict()

            results.append({
                "flag_own": own,
                "flag_own_soft": soft_own,
                "flag_peer": peer,
                "candidates_count": count,
                "route_breakdown": routes
            })

    return results


def format_sensitivity_table_markdown(results: List[Dict[str, Any]]) -> str:
    """Format grid results into a clean markdown table."""
    lines = [
        "| vs_own Threshold | vs_own Soft | vs_peer Threshold | Total Candidates | Selected / Default |",
        "|---|---|---|---|---|"
    ]
    for r in results:
        is_default = (r["flag_own"] == 8.0 and r["flag_peer"] == 20.0)
        marker = "**YES (Default)**" if is_default else "No"
        lines.append(
            f"| +{r['flag_own']:.1f}% | +{r['flag_own_soft']:.1f}% | +{r['flag_peer']:.1f}% | {r['candidates_count']} | {marker} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    res = run_sensitivity_analysis()
    print(format_sensitivity_table_markdown(res))
