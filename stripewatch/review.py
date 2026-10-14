"""Human review queue management module.

Manages review status and notes for candidate rows without altering verdicts.
State is stored in .state/review_state.json using atomic writes.
"""
from pathlib import Path
import json
import csv
import re
import tempfile
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set

from stripewatch.config import BASE_DIR, OUTPUT_DIR

STATE_DIR = BASE_DIR / ".state"
REVIEW_STATE_FILE = STATE_DIR / "review_state.json"
VALID_STATUSES = {"open", "confirmed", "dismissed"}


def sanitize_note(note: str) -> str:
    """Strip control characters (except standard whitespace) and trim to 280 chars."""
    if not note:
        return ""
    # Strip non-printable control characters
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", str(note))
    return cleaned.strip()[:280]


def load_review_state() -> Dict[str, Dict[str, Any]]:
    """Load review state from .state/review_state.json or return empty dict."""
    if not REVIEW_STATE_FILE.exists():
        return {}
    try:
        with open(REVIEW_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_review_state(state: Dict[str, Dict[str, Any]]) -> None:
    """Atomic write to review state file via temp file in same directory."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    # Write to temp file in same directory to guarantee atomic rename
    with tempfile.NamedTemporaryFile("w", dir=str(STATE_DIR), delete=False, encoding="utf-8") as tf:
        json.dump(state, tf, indent=2)
        temp_name = tf.name

    Path(temp_name).replace(REVIEW_STATE_FILE)


def get_candidate_keys() -> Set[str]:
    """Retrieve set of valid '<route>|<week_of>' keys for the 19 candidates."""
    results_file = OUTPUT_DIR / "results.json"
    if not results_file.exists():
        return set()
    with open(results_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    candidates = data["candidates"] if isinstance(data, dict) and "candidates" in data else data
    return {f"{c['route']}|{c['week_of']}" for c in candidates}


def get_review_items() -> List[Dict[str, Any]]:
    """Merge candidates with their review status."""
    results_file = OUTPUT_DIR / "results.json"
    if not results_file.exists():
        return []

    with open(results_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    candidates = data["candidates"] if isinstance(data, dict) and "candidates" in data else data

    state = load_review_state()
    items = []
    for c in candidates:
        key = f"{c['route']}|{c['week_of']}"
        entry = state.get(key, {})
        items.append({
            "route": c["route"],
            "week_of": c["week_of"],
            "verdict": c["verdict"],
            "matched_note_id": c.get("matched_note_id") or "",
            "c": c.get("c"),
            "vs_own_pct": c.get("vs_own_pct"),
            "vs_peer_pct": c.get("vs_peer_pct"),
            "excess_inr": c.get("excess_inr", 0),
            "review_status": entry.get("status", "open"),
            "review_note": entry.get("note", ""),
            "updated_at": entry.get("updated_at")
        })
    return items


def update_review_item(route: str, week_of: str, status: str, note: str) -> Dict[str, Any]:
    """Update review status and note for a candidate row with strict validation."""
    key = f"{route}|{week_of}"
    candidate_keys = get_candidate_keys()
    if candidate_keys and key not in candidate_keys:
        raise ValueError(f"'{key}' is not one of the candidate rows")

    status_clean = str(status).strip().lower()
    if status_clean not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {sorted(list(VALID_STATUSES))}")

    clean_note = sanitize_note(note)
    now_iso = datetime.now(timezone.utc).isoformat()

    state = load_review_state()
    state[key] = {
        "status": status_clean,
        "note": clean_note,
        "updated_at": now_iso
    }
    save_review_state(state)

    return {
        "key": key,
        "status": status_clean,
        "note": clean_note,
        "updated_at": now_iso
    }


def export_review_csv(output_path: Optional[Path | str] = None) -> Path:
    """Export review state to output/review_export.csv."""
    dest = Path(output_path) if output_path else (OUTPUT_DIR / "review_export.csv")
    dest.parent.mkdir(parents=True, exist_ok=True)

    items = get_review_items()
    fieldnames = ["route", "week_of", "verdict", "matched_note_id", "review_status", "review_note"]

    with open(dest, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for it in items:
            writer.writerow({
                "route": it["route"],
                "week_of": it["week_of"],
                "verdict": it["verdict"],
                "matched_note_id": it.get("matched_note_id") or "",
                "review_status": it.get("review_status", "open"),
                "review_note": it.get("review_note", "")
            })

    return dest
