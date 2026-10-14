"""Weekly watch mode (Feature 10).

Evaluates only a single Monday's route-weeks using strictly prior history.
Outputs structured JSON of candidate anomalies, deterministic verdicts, and explanations.
"""
from pathlib import Path
import json
import sys
from typing import List, Dict, Any
import pandas as pd

from stripewatch.config import OUTPUT_DIR
from stripewatch.loader import load_shipments
from stripewatch.weekly import to_weekly
from stripewatch.baselines import add_baselines
from stripewatch.detect import detect_candidates
from stripewatch.notes import get_notes_dict
from stripewatch.retrieve import NoteRetriever
from stripewatch.validate import decide_verdict
from stripewatch.evidence import build_evidence_packet
from stripewatch.explain import generate_template_explanation, explain_candidate
from stripewatch.llm import LLMClient
from stripewatch.writer import format_output_row


def watch_week(
    target_week_str: str,
    explain_with_llm: bool = False,
    provider: str | None = None
) -> List[Dict[str, Any]]:
    """Evaluate anomalies for a specific Monday route-week.

    Args:
        target_week_str: ISO date string for Monday (e.g. '2024-11-11').
        explain_with_llm: If True, uses LLM for explanation synthesis; otherwise template.
        provider: Optional LLM provider override.

    Returns:
        List of candidate dictionaries.
    """
    try:
        target_dt = pd.to_datetime(target_week_str)
    except Exception as e:
        raise ValueError(f"Invalid date format '{target_week_str}': {e}")

    # Enforce Monday invariant
    if target_dt.weekday() != 0:
        raise ValueError(f"Date '{target_week_str}' is not a Monday (weekday={target_dt.weekday()}). StripeWatch requires Monday-aligned weeks.")

    # Strictly prior data: up to the target week's Sunday
    target_sunday = target_dt + pd.Timedelta(days=6)

    shipments_df = load_shipments()
    prior_shipments = shipments_df[shipments_df["shipment_date"] <= target_sunday].copy()

    weekly_df = to_weekly(prior_shipments)
    evaluable_df = add_baselines(weekly_df, drop_first_weeks=True)

    # Filter for the specific week
    week_mask = evaluable_df["week_of"] == target_dt
    target_week_df = evaluable_df[week_mask].copy()

    if target_week_df.empty:
        return []

    candidates_df = detect_candidates(target_week_df)
    if candidates_df.empty:
        return []

    retriever = NoteRetriever()
    notes_map = get_notes_dict()
    llm_client = LLMClient(provider=provider, enable_cache=True) if explain_with_llm else None

    findings = []
    for _, row in candidates_df.iterrows():
        route = str(row["route"])
        wk_str = target_dt.strftime("%Y-%m-%d")

        hits = retriever.retrieve_for_candidate(route, wk_str, k=5)
        candidate_notes = [notes_map[nid] for nid, _ in hits]
        verdict = decide_verdict(row, candidate_notes)
        chosen_note = notes_map[verdict.note_id] if verdict.note_id else None
        packet = build_evidence_packet(row, verdict, chosen_note, candidate_notes)

        if explain_with_llm and llm_client:
            reason_text, _ = explain_candidate(packet, llm_client=llm_client)
        else:
            reason_text = generate_template_explanation(packet)

        row_payload = {
            "route": route,
            "week_of": wk_str,
            "c": row["c"],
            "vs_own_pct": row["vs_own_pct"],
            "vs_peer_pct": row["vs_peer_pct"],
            "excess_inr": int(row.get("excess_inr", 0)),
            "verdict": packet["verdict"],
            "matched_note_id": verdict.note_id,
            "reason": reason_text
        }
        findings.append(format_output_row(row_payload))

    return findings
