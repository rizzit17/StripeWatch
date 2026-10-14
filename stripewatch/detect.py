"""Candidate detection module: flags routes with unusual cost rises based on configured thresholds."""
import pandas as pd
from stripewatch.config import FLAG_OWN_PCT, FLAG_OWN_SOFT_PCT, FLAG_PEER_PCT


def is_candidate_mask(
    df: pd.DataFrame,
    own_pct: float = FLAG_OWN_PCT,
    own_soft_pct: float = FLAG_OWN_SOFT_PCT,
    peer_pct: float = FLAG_PEER_PCT
) -> pd.Series:
    """Boolean mask for candidate route-weeks under the dual-branch rule.

    Branch 1: vs_own >= own_pct (strong own rise, e.g. >= +8.0%)
    Branch 2: vs_own >= own_soft_pct AND vs_peer >= peer_pct (mild own rise e.g. >= +5.0% that is also a big peer gap >= +20.0%)
    Requirement: vs_own must be strictly positive.
    """
    strong_own = df["vs_own_pct"] >= own_pct
    peer_gap = (df["vs_own_pct"] >= own_soft_pct) & (df["vs_peer_pct"] >= peer_pct)
    return (df["vs_own_pct"] > 0) & (strong_own | peer_gap)


def detect_candidates(
    df: pd.DataFrame,
    own_pct: float = FLAG_OWN_PCT,
    own_soft_pct: float = FLAG_OWN_SOFT_PCT,
    peer_pct: float = FLAG_PEER_PCT
) -> pd.DataFrame:
    """Filter route-weeks that qualify as candidates for cost rise investigation.

    Args:
        df: DataFrame with computed baselines (vs_own_pct, vs_peer_pct).
        own_pct: Primary threshold for vs_own_pct.
        own_soft_pct: Secondary soft threshold for vs_own_pct.
        peer_pct: Outlier threshold for vs_peer_pct.

    Returns:
        Filtered DataFrame containing only candidate rows.
    """
    mask = is_candidate_mask(df, own_pct=own_pct, own_soft_pct=own_soft_pct, peer_pct=peer_pct)
    candidates_df = df[mask].copy().reset_index(drop=True)
    return candidates_df
