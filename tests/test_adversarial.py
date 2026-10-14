"""Adversarial suite and positive control tests for deterministic validator and RAG pipeline."""
import json
from pathlib import Path
import pytest
import pandas as pd

from stripewatch.notes import get_notes_dict, load_structured_notes
from stripewatch.validate import validate_note, decide_verdict
from stripewatch.retrieve import NoteRetriever
from stripewatch.loader import load_shipments
from stripewatch.weekly import to_weekly
from stripewatch.baselines import add_baselines
from stripewatch.detect import detect_candidates


@pytest.fixture(scope="module")
def notes_map():
    return get_notes_dict()


def test_adversarial_suite(notes_map):
    cases_path = Path("eval/adversarial_cases.json")
    assert cases_path.exists()

    with open(cases_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    assert len(cases) >= 12, "Must contain at least 12 adversarial / control cases"

    for c in cases:
        note = notes_map[c["note_id"]]
        row = {
            "route": c["route"],
            "week_of": c["week_of"],
            "vs_own_pct": c["vs_own_pct"],
            "vs_peer_pct": c["vs_peer_pct"],
        }
        res = validate_note(row, note)

        assert res.justified == c["expected_justified"], (
            f"Failed on: {c['description']} | Note {note.id} expected justified={c['expected_justified']}, got {res.justified}. why_not: {res.why_not}"
        )

        if not c["expected_justified"] and c.get("expected_failing_check"):
            failing = c["expected_failing_check"]
            assert res.checks[failing] is False, (
                f"Expected check '{failing}' to be False for {c['description']}, but checks were: {res.checks}"
            )


def test_full_pipeline_candidates_verdicts():
    """Run full loader -> weekly -> baselines -> detect -> retrieve -> validate.
    Assert Gate G3 requirement: N001 x 2, N002 x 1 justified; 16 unexplained."""
    shipments = load_shipments()
    weekly = to_weekly(shipments)
    baselines = add_baselines(weekly, drop_first_weeks=True)
    cands = detect_candidates(baselines)
    assert len(cands) == 19

    retriever = NoteRetriever()
    notes_map = get_notes_dict()

    verdicts = []
    for _, row in cands.iterrows():
        wk_str = pd.to_datetime(row["week_of"]).strftime("%Y-%m-%d")
        hits = retriever.retrieve_for_candidate(row["route"], wk_str, k=3)
        candidate_notes = [notes_map[nid] for nid, _ in hits]
        v = decide_verdict(row, candidate_notes)
        verdicts.append((row["route"], wk_str, v.justified, v.note_id))

    justified = [v for v in verdicts if v[2] is True]
    unexplained = [v for v in verdicts if v[2] is False]

    assert len(justified) == 3, f"Expected 3 justified rows, got {len(justified)}: {justified}"
    assert len(unexplained) == 16, f"Expected 16 unexplained rows, got {len(unexplained)}"

    # Check the 3 justified rows exactly
    justified_map = {(v[0], v[1]): v[3] for v in justified}
    assert justified_map.get(("Ahmedabad-Mumbai", "2025-01-20")) == "N002"
    assert justified_map.get(("Chennai-Bangalore", "2025-02-24")) == "N001"
    assert justified_map.get(("Chennai-Bangalore", "2025-03-03")) == "N001"

    # All unexplained must have note_id = None
    for u in unexplained:
        assert u[3] is None
