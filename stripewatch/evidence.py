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

    # Near misses from rejected notes: list ONLY notes matching the route OR overlapping the target week
    from stripewatch.notes import get_notes_dict
    notes_map = get_notes_dict()
    week_dt = pd.to_datetime(row["week_of"])
    week_start_str = week_dt.strftime("%Y-%m-%d")
    week_end_str = (week_dt + pd.Timedelta(days=6)).strftime("%Y-%m-%d")
    route_str = str(row["route"]).strip()

    near_misses = []
    for rej in verdict.rejected_notes:
        if verdict.note_id and rej["id"] == verdict.note_id:
            continue
        note_obj = notes_map.get(rej["id"])
        if not note_obj:
            continue

        route_matches = (note_obj.scope == route_str)
        week_overlaps = (note_obj.start <= week_end_str) and (note_obj.end is None or note_obj.end >= week_start_str)

        if not (route_matches or week_overlaps):
            continue

        near_misses.append({
            "id": rej["id"],
            "why_not": rej["why_not"]
        })
        if len(near_misses) >= 2:
            break
    packet["near_misses"] = near_misses

    return packet
