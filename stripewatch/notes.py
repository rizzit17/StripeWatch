"""Notes domain model and loader for structured context notes."""
from dataclasses import dataclass
from pathlib import Path
import json
import pandas as pd

from stripewatch.config import NOTES_FILE, NOTES_STRUCTURED_FILE


@dataclass(frozen=True)
class Note:
    id: str
    date: str
    applies_to: str
    text: str
    scope: str
    effect: str
    start: str
    end: str | None
    mag_min: float | None
    mag_max: float | None
    rationale: str


def load_structured_notes(
    notes_csv_path: Path | str | None = None,
    structured_json_path: Path | str | None = None
) -> list[Note]:
    """Load notes combining raw text from context_notes.csv with structured fields from JSON.

    Returns:
        Sorted list of Note dataclass instances.
    """
    csv_file = Path(notes_csv_path) if notes_csv_path else NOTES_FILE
    json_file = Path(structured_json_path) if structured_json_path else NOTES_STRUCTURED_FILE

    raw_df = pd.read_csv(csv_file).set_index("note_id")

    with open(json_file, "r", encoding="utf-8") as f:
        structured_data = json.load(f)

    notes = []
    for item in structured_data:
        nid = item["id"]
        raw_row = raw_df.loc[nid]
        note = Note(
            id=nid,
            date=str(item.get("date", raw_row["date"])),
            applies_to=str(item.get("applies_to", raw_row["applies_to"])),
            text=str(raw_row["note"]).strip(),
            scope=str(item["scope"]),
            effect=str(item["effect"]),
            start=str(item["start"]),
            end=item["end"] if item.get("end") else None,
            mag_min=float(item["mag_min"]) if item.get("mag_min") is not None else None,
            mag_max=float(item["mag_max"]) if item.get("mag_max") is not None else None,
            rationale=str(item.get("rationale", "")).strip()
        )
        notes.append(note)

    notes.sort(key=lambda n: n.id)
    return notes


def get_notes_dict(
    notes_csv_path: Path | str | None = None,
    structured_json_path: Path | str | None = None
) -> dict[str, Note]:
    """Return notes as a dictionary mapping note_id to Note instance."""
    notes = load_structured_notes(notes_csv_path, structured_json_path)
    return {n.id: n for n in notes}
