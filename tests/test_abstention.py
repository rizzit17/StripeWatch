"""Tests for Backend C: Abstention statistics."""
import json
from stripewatch.paper_trail import compute_abstention_stat
from stripewatch.notes import load_structured_notes
from stripewatch.config import OUTPUT_DIR


def test_abstention_derived_from_data():
    """Verify abstention stat is strictly derived from data and not hard-coded."""
    notes = load_structured_notes()
    results_file = OUTPUT_DIR / "results.json"
    assert results_file.exists()

    with open(results_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    candidates = data["candidates"] if isinstance(data, dict) and "candidates" in data else data

    stat = compute_abstention_stat(candidates, notes)

    assert stat["total"] == len(candidates)
    assert stat["unexplained"] == sum(1 for c in candidates if c.get("verdict") == "unexplained")
    assert stat["rate"] == round(stat["unexplained"] / stat["total"], 3)
    assert stat["total_notes"] == len(notes)
    assert stat["usable_notes"] == sum(1 for n in notes if n.effect == "raises" and n.scope != "NONE")
    assert stat["notes_cited"] == ["N001", "N002"]
    assert stat["notes_usable_never_cited"] == ["N003"]

    # String format check
    summary_sentence = f"Left {stat['unexplained']} of {stat['total']} unexplained on purpose: only {stat['usable_notes']} of {stat['total_notes']} notes can justify a rise."
    assert summary_sentence == "Left 16 of 19 unexplained on purpose: only 3 of 10 notes can justify a rise."
