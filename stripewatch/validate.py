"""Deterministic validation of retrieved notes against route-week candidates.

This module is the core trust guardrail of StripeWatch:
Verdicts and note justifications are 100% deterministic code.
The LLM never decides a verdict or matched_note_id.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
import pandas as pd

from stripewatch.config import FLAG_PEER_PCT, MAG_TOL_PP
from stripewatch.notes import Note


@dataclass
class NoteCheckResult:
    justified: bool
    note_id: Optional[str]
    checks: Dict[str, bool]
    why_not: str


@dataclass
class Verdict:
    justified: bool
    note_id: Optional[str]
    checks: Dict[str, bool]
    why_not: str
    rejected_notes: List[dict]  # list of {"id": str, "why_not": str}


def validate_note(row, note: Note) -> NoteCheckResult:
    """Validate a single candidate row against a candidate note using 5 strict checks."""
    week_of_dt = pd.to_datetime(row["week_of"])
    week_start_str = week_of_dt.strftime("%Y-%m-%d")
    week_end_dt = week_of_dt + pd.Timedelta(days=6)
    week_end_str = week_end_dt.strftime("%Y-%m-%d")

    route_str = str(row["route"]).strip()
    vs_own = float(row["vs_own_pct"])
    vs_peer = float(row["vs_peer_pct"]) if pd.notnull(row["vs_peer_pct"]) else 0.0

    # Check 1: Effect must be a cost rise
    effect_ok = (note.effect == "raises")

    # Check 2: Route in scope (corridor specific or ALL)
    route_ok = (note.scope == "ALL" or note.scope == route_str)

    # Check 3: Window overlaps the target week
    # Overlap iff: note.start <= week_end AND (note.end is None OR note.end >= week_start)
    window_ok = (note.start <= week_end_str) and (note.end is None or note.end >= week_start_str)

    # Check 4: Magnitude plausibility
    # Note mag_max + tolerance >= vs_own
    if note.mag_max is not None:
        mag_ok = (vs_own <= note.mag_max + MAG_TOL_PP)
    else:
        mag_ok = True

    # Check 5: Nationwide / Universal notes cannot explain route peer outliers
    if note.scope == "ALL" and vs_peer >= FLAG_PEER_PCT:
        universal_peer_ok = False
    else:
        universal_peer_ok = True

    checks = {
        "effect_is_cost_rise": effect_ok,
        "route_in_scope": route_ok,
        "window_overlaps": window_ok,
        "magnitude_ok": mag_ok,
        "not_peer_outlier_for_universal": universal_peer_ok,
    }

    justified = all(checks.values())

    # Formulate plain-English why_not if not justified (in strict priority order)
    why_not = ""
    if not justified:
        if not effect_ok:
            why_not = f"{note.id} does not describe a cost rise (effect: '{note.effect}')"
        elif not route_ok:
            why_not = f"{note.id} applies to '{note.scope}', not '{route_str}'"
        elif not window_ok:
            end_label = note.end if note.end else "ongoing"
            why_not = f"{note.id} disruption window ({note.start} to {end_label}) does not overlap week of {week_start_str}"
        elif not mag_ok:
            why_not = f"{note.id} stated magnitude (~{note.mag_max}%) is exceeded by the +{vs_own:.1f}% rise"
        elif not universal_peer_ok:
            why_not = f"{note.id} is nationwide and cannot explain a +{vs_peer:.1f}% peer gap (>= +{FLAG_PEER_PCT}%)"

    return NoteCheckResult(
        justified=justified,
        note_id=note.id,
        checks=checks,
        why_not=why_not
    )


def decide_verdict(row, candidate_notes: List[Note]) -> Verdict:
    """Evaluate candidate notes for a row and return the final deterministic Verdict."""
    accepted: List[tuple[Note, NoteCheckResult]] = []
    rejected: List[dict] = []

    for note in candidate_notes:
        res = validate_note(row, note)
        if res.justified:
            accepted.append((note, res))
        else:
            rejected.append({"id": note.id, "why_not": res.why_not})

    if accepted:
        # Selection priority:
        # 1. Prefer route-specific scope over ALL-routes scope
        # 2. Tie-breaker: lowest note_id
        def sort_key(item):
            n, _ = item
            is_universal = 1 if n.scope == "ALL" else 0
            return (is_universal, n.id)

        accepted.sort(key=sort_key)
        winner_note, winner_res = accepted[0]
        return Verdict(
            justified=True,
            note_id=winner_note.id,
            checks=winner_res.checks,
            why_not="",
            rejected_notes=rejected
        )
    else:
        primary_why = rejected[0]["why_not"] if rejected else "No notes found"
        return Verdict(
            justified=False,
            note_id=None,
            checks={},
            why_not=primary_why,
            rejected_notes=rejected
        )
