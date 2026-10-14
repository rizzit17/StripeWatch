"""Baseline calculations: vs own history (strictly prior <=8 weeks) and vs similar routes (same week & route_type, self excluded)."""
import pandas as pd
import numpy as np


def add_baselines(w: pd.DataFrame, drop_first_weeks: bool = True) -> pd.DataFrame:
    """Compute rolling own history average and peer average for each route-week.

    Rules:
    - vs_own: mean of previous <=8 weekly c values, strictly before current week (shift(1)).
      If fewer than 8 prior weeks exist, use all available prior weeks.
      Rows with 0 priors have no history.
    - vs_peer: average c across other routes sharing the same route_type in the same week.
      Self is excluded from own peer average.

    Args:
        w: Weekly DataFrame with columns: route, route_type, week_of, cost, tonne_km, n_shipments, c
        drop_first_weeks: If True, drops rows with n_prior == 0 (non-evaluable first weeks).

    Returns:
        DataFrame with added columns:
            own_avg, n_prior, peer_avg, vs_own_pct, vs_peer_pct
    """
    df = w.copy().sort_values(["route", "week_of"]).reset_index(drop=True)

    # Own history: strictly prior weeks via shift(1), rolling up to 8 weeks, min_periods=1
    df["own_avg"] = df.groupby("route")["c"].transform(
        lambda s: s.shift(1).rolling(8, min_periods=1).mean()
    )
    df["n_prior"] = df.groupby("route").cumcount().clip(upper=8)

    # Peers: same week_of and route_type, excluding self
    grp = (
        df.groupby(["route_type", "week_of"])["c"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "peer_sum", "count": "peer_count"})
    )
    df = df.join(grp, on=["route_type", "week_of"])

    # Exclude self: (sum - c) / (count - 1)
    # If peer_count <= 1, peer_avg is NaN
    has_peers = df["peer_count"] > 1
    df["peer_avg"] = np.where(has_peers, (df["peer_sum"] - df["c"]) / (df["peer_count"] - 1), np.nan)
    df.drop(columns=["peer_sum", "peer_count"], inplace=True)

    # Noise band helper: rolling std of strictly prior <=8 weeks
    own_std = df.groupby("route")["c"].transform(
        lambda s: s.shift(1).rolling(8, min_periods=1).std()
    )

    # Percentages relative to baselines (unrounded floats)
    df["vs_own_pct"] = (df["c"] / df["own_avg"] - 1) * 100
    df["vs_peer_pct"] = (df["c"] / df["peer_avg"] - 1) * 100

    if drop_first_weeks:
        df = df[df["n_prior"] > 0].copy().reset_index(drop=True)
        own_std = own_std[w["n_prior"] > 0 if "n_prior" in w.columns else (w.groupby("route").cumcount() > 0)].values

    # Supplementary metrics (Features 2 & 8 - do not alter candidate flags or verdicts)
    # Excess spend in whole INR vs own trailing baseline
    df["excess_inr"] = ((df["c"] - df["own_avg"]).clip(lower=0) * df["tonne_km"]).round().astype(int)

    # Creep early-warning: rolling 4-evaluable-week mean of vs_peer_pct per route
    df["peer_gap_4w"] = df.groupby("route")["vs_peer_pct"].transform(
        lambda s: s.rolling(4, min_periods=1).mean()
    )
    df["creep_tag"] = df["peer_gap_4w"] >= 15.0

    # Noise band and z-score
    df["noise_pct"] = (own_std / df["own_avg"]) * 100
    df["rise_z"] = np.where(df["n_prior"] >= 3, (df["c"] - df["own_avg"]) / own_std, np.nan)

    return df
