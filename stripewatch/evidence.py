"""Evidence packet builder: constructs structured context for explanations and grounding."""
from typing import Dict, Any, List
import pandas as pd

from stripewatch.notes import Note
from stripewatch.validate import Verdict


def build_evidence_packet(
    row: pd.Series | dict,
    verdict: Verdict,
    chosen_note: Note | None,
    candidate_notes: List[Note] | None = None
) -> Dict[str, Any]:
    """Construct an evidence packet containing only verified, deterministic facts.

    This packet is the single source of truth for the explainer and the grounding checker.
    The LLM is strictly prohibited from introducing any facts outside this dictionary.
    """
    week_of_str = pd.to_datetime(row["week_of"]).strftime("%Y-%m-%d")
    vs_peer_val = float(row["vs_peer_pct"]) if pd.notnull(row["vs_peer_pct"]) else 0.0

    packet: Dict[str, Any] = {
        "route": str(row["route"]).strip(),
        "week_of": week_of_str,
        "c": round(float(row["c"]), 2),
        "vs_own_pct": round(float(row["vs_own_pct"]), 1),
        "vs_peer_pct": round(vs_peer_val, 1),
        "verdict": "justified" if verdict.justified else "unexplained",
        "matched_note_id": verdict.note_id,
        "note": None,
        "near_misses": []
    }

    if verdict.justified and chosen_note:
        packet["note"] = {
            "id": chosen_note.id,
            "text": chosen_note.text,
            "start": chosen_note.start,
            "end": chosen_note.end,
            "date": chosen_note.date,
            "rationale": chosen_note.rationale
        }

    # Near misses from rejected notes (limit to top 2 for concise explanations)
    near_misses = []
    for rej in verdict.rejected_notes:
        if verdict.note_id and rej["id"] == verdict.note_id:
            continue
        near_misses.append({
            "id": rej["id"],
            "why_not": rej["why_not"]
        })
        if len(near_misses) >= 2:
            break
    packet["near_misses"] = near_misses

    return packet
