"""Paper trail strip data generator.

Constructs the 5-ticket verification strip:
1. Spotted (candidate rule check)
2. Searched (top-3 retrieved note IDs)
3. Route (scope check: PASS/FAIL)
4. Window (date overlap check: PASS/FAIL/—)
5. Effect and size (cost rise + magnitude + universal peer outlier: PASS/FAIL/—)
"""
from typing import Dict, Any, List, Optional
import pandas as pd
from stripewatch.notes import Note, get_notes_dict
from stripewatch.validate import validate_note

def compute_abstention_stat(
    candidates: List[Dict[str, Any]],
    notes: Optional[List[Note]] = None
) -> Dict[str, Any]:
    """Compute abstention statistics from candidate results and structured notes."""
    if notes is None:
        from stripewatch.notes import load_structured_notes
        notes = load_structured_notes()

    total = len(candidates)
    unexplained = sum(1 for c in candidates if c.get("verdict") == "unexplained")
    rate = round(unexplained / total, 3) if total > 0 else 0.0

    usable_note_ids = [n.id for n in notes if n.effect == "raises" and n.scope != "NONE"]
    usable_notes = len(usable_note_ids)
    total_notes = len(notes)

    notes_cited = sorted(list(set(
        str(c.get("matched_note_id")).strip()
        for c in candidates
        if c.get("verdict") == "justified" and c.get("matched_note_id")
    )))
    notes_usable_never_cited = [nid for nid in usable_note_ids if nid not in notes_cited]

    return {
        "unexplained": unexplained,
        "total": total,
        "rate": rate,
        "usable_notes": usable_notes,
        "total_notes": total_notes,
        "notes_cited": notes_cited,
        "notes_usable_never_cited": notes_usable_never_cited
    }


def compute_paper_trail(
    row: pd.Series | dict,
    retrieved_hits: List[dict] | List[tuple],
    verdict_justified: bool,
    matched_note_id: Optional[str] = None,
    notes_map: Optional[Dict[str, Note]] = None
) -> Dict[str, Any]:
    """Generate 5-ticket paper trail data for a candidate route-week."""
    if notes_map is None:
        notes_map = get_notes_dict()

    # Normalize hits to list of dicts: [{"id": nid, "score": score}]
    hits_list: List[Dict[str, Any]] = []
    for item in retrieved_hits:
        if isinstance(item, dict):
            hits_list.append({"id": item["id"], "score": round(float(item.get("score", 0.0)), 4)})
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            hits_list.append({"id": str(item[0]), "score": round(float(item[1]), 4)})

    route_str = str(row["route"]).strip()
    vs_own = float(row["vs_own_pct"])
    vs_peer = float(row["vs_peer_pct"]) if pd.notnull(row.get("vs_peer_pct")) else 0.0

    # Evaluate checks for all retrieved notes
    note_checks: Dict[str, Dict[str, Any]] = {}
    for h in hits_list:
        nid = h["id"]
        if nid in notes_map:
            chk_res = validate_note(row, notes_map[nid])
            note_checks[nid] = {
                "checks": chk_res.checks,
                "why_not": chk_res.why_not,
                "justified": chk_res.justified
            }

    # Determine closest rejected note if not justified
    closest_rejected_note: Optional[str] = None
    if not verdict_justified:
        candidates_to_rank = [h["id"] for h in hits_list if h["id"] in note_checks]
        if candidates_to_rank:
            def sort_key(nid: str):
                # Number of passing checks (higher is better)
                passing_count = sum(1 for v in note_checks[nid]["checks"].values() if v)
                return (-passing_count, nid)

            ranked = sorted(candidates_to_rank, key=sort_key)
            closest_rejected_note = ranked[0]

    evaluated_note_id = matched_note_id if (verdict_justified and matched_note_id) else closest_rejected_note
    evaluated_note = notes_map.get(evaluated_note_id) if evaluated_note_id else None

    # Ticket 1: Spotted
    t1 = {
        "index": 1,
        "name": "Spotted",
        "status": "PASS",
        "detail": f"{vs_own:+.1f}% own · {vs_peer:+.1f}% peers",
        "summary": "Candidate rule matched (vs own >= 8.0%, vs peer >= 5.0%, cost > 20% noise)",
        "stamp": "SPOTTED"
    }

    # Ticket 2: Searched
    searched_chips = [h["id"] for h in hits_list[:3]]
    t2 = {
        "index": 2,
        "name": "Searched",
        "status": "PASS",
        "chips": searched_chips,
        "detail": ", ".join(searched_chips) if searched_chips else "None",
        "summary": f"Retrieved {len(hits_list)} candidate notes via semantic search",
        "stamp": "SEARCHED"
    }

    # Tickets 3, 4, 5 depend on evaluated_note
    if not evaluated_note:
        t3 = {"index": 3, "name": "Route", "status": "FAIL", "detail": "No notes retrieved", "stamp": "FAIL"}
        t4 = {"index": 4, "name": "Window", "status": "UNEVALUATED", "detail": "—", "stamp": "—"}
        t5 = {"index": 5, "name": "Effect & size", "status": "UNEVALUATED", "detail": "—", "stamp": "—"}
    else:
        chk_data = note_checks.get(evaluated_note.id, {})
        checks = chk_data.get("checks", {})

        route_ok = checks.get("route_in_scope", False)
        window_ok = checks.get("window_overlaps", False)
        effect_ok = checks.get("effect_is_cost_rise", False)
        mag_ok = checks.get("magnitude_ok", True)
        univ_ok = checks.get("not_peer_outlier_for_universal", True)
        effect_and_size_ok = (effect_ok and mag_ok and univ_ok)

        # Window detail string
        window_label = f"{evaluated_note.start} to {evaluated_note.end if evaluated_note.end else 'ongoing'}"

        # Ticket 3: Route
        if not route_ok:
            t3 = {
                "index": 3,
                "name": "Route",
                "status": "FAIL",
                "detail": f"Scope: '{evaluated_note.scope}'",
                "stamp": "FAIL",
                "why_not": f"Note applies to '{evaluated_note.scope}', not '{route_str}'"
            }
            t4 = {"index": 4, "name": "Window", "status": "UNEVALUATED", "detail": window_label, "stamp": "—"}
            t5 = {"index": 5, "name": "Effect & size", "status": "UNEVALUATED", "detail": "—", "stamp": "—"}
        else:
            t3 = {
                "index": 3,
                "name": "Route",
                "status": "PASS",
                "detail": f"Scope: '{evaluated_note.scope}' matches '{route_str}'",
                "stamp": "PASS"
            }

            # Ticket 4: Window
            if not window_ok:
                t4 = {
                    "index": 4,
                    "name": "Window",
                    "status": "FAIL",
                    "detail": window_label,
                    "stamp": "FAIL",
                    "why_not": f"Window ({window_label}) does not overlap week"
                }
                t5 = {"index": 5, "name": "Effect & size", "status": "UNEVALUATED", "detail": "—", "stamp": "—"}
            else:
                t4 = {
                    "index": 4,
                    "name": "Window",
                    "status": "PASS",
                    "detail": window_label,
                    "stamp": "PASS"
                }

                # Ticket 5: Effect and size
                subchecks = {
                    "effect_is_cost_rise": effect_ok,
                    "magnitude_ok": mag_ok,
                    "not_peer_outlier_for_universal": univ_ok
                }
                if not effect_and_size_ok:
                    fail_reasons = []
                    if not effect_ok:
                        fail_reasons.append(f"effect is '{evaluated_note.effect}'")
                    if not mag_ok:
                        fail_reasons.append(f"exceeds ~{evaluated_note.mag_max}% limit")
                    if not univ_ok:
                        fail_reasons.append("universal note cannot explain route peer outlier")

                    t5 = {
                        "index": 5,
                        "name": "Effect & size",
                        "status": "FAIL",
                        "detail": "; ".join(fail_reasons),
                        "stamp": "FAIL",
                        "subchecks": subchecks
                    }
                else:
                    t5 = {
                        "index": 5,
                        "name": "Effect & size",
                        "status": "PASS",
                        "detail": f"Raises cost, magnitude plausible",
                        "stamp": "PASS",
                        "subchecks": subchecks
                    }

    return {
        "retrieved": hits_list,
        "checks": note_checks,
        "closest_rejected_note": closest_rejected_note,
        "evaluated_note_id": evaluated_note_id,
        "tickets": [t1, t2, t3, t4, t5]
    }
