"""Grounding validation tests: 100% pass on pipeline explanations, 100% rejection on corrupted samples."""
import pytest
import pandas as pd

from stripewatch.loader import load_shipments
from stripewatch.weekly import to_weekly
from stripewatch.baselines import add_baselines
from stripewatch.detect import detect_candidates
from stripewatch.notes import get_notes_dict
from stripewatch.retrieve import NoteRetriever
from stripewatch.validate import decide_verdict
from stripewatch.evidence import build_evidence_packet
from stripewatch.explain import explain_candidate, generate_template_explanation
from stripewatch.ground import check_grounding


@pytest.fixture(scope="module")
def pipeline_packets():
    shipments = load_shipments()
    weekly = to_weekly(shipments)
    baselines = add_baselines(weekly, drop_first_weeks=True)
    cands = detect_candidates(baselines)

    retriever = NoteRetriever()
    notes_map = get_notes_dict()

    packets = []
    for _, row in cands.iterrows():
        wk_str = pd.to_datetime(row["week_of"]).strftime("%Y-%m-%d")
        hits = retriever.retrieve_for_candidate(row["route"], wk_str, k=3)
        candidate_notes = [notes_map[nid] for nid, _ in hits]
        v = decide_verdict(row, candidate_notes)
        chosen_note = notes_map[v.note_id] if v.note_id else None
        pkt = build_evidence_packet(row, v, chosen_note, candidate_notes)
        packets.append(pkt)

    return packets


def test_grounding_on_all_nineteen_rows(pipeline_packets):
    """Every generated explanation for the 19 candidates must pass grounding 100%."""
    assert len(pipeline_packets) == 19

    for pkt in pipeline_packets:
        explanation = generate_template_explanation(pkt)
        is_grounded, reasons = check_grounding(explanation, pkt)
        assert is_grounded, f"Failed grounding for {pkt['route']} {pkt['week_of']}: {reasons}\nText: {explanation}"


def test_five_corrupted_samples_must_fail(pipeline_packets):
    """Test the 5 specific adversarial corruptions described in systemdesign.md §13.4."""
    justified_pkt = next(p for p in pipeline_packets if p["verdict"] == "justified")
    unexplained_pkt = next(p for p in pipeline_packets if p["verdict"] == "unexplained")

    # Corruption 1: Invented note ID (e.g. N999)
    bad_id_text = f"Matches note N999 dated {justified_pkt['note']['date']}: flood disruption on corridor."
    is_grounded, reasons = check_grounding(bad_id_text, justified_pkt)
    assert not is_grounded, "Corrupted note ID must fail grounding"
    assert any("Invented note IDs" in r for r in reasons)

    # Corruption 2: Invented percentage figure (e.g. +78.5%)
    bad_pct_text = (
        f"Matches note {justified_pkt['matched_note_id']} dated {justified_pkt['note']['date']}: "
        f"cost rose by +78.5% due to major driver strikes."
    )
    is_grounded, reasons = check_grounding(bad_pct_text, justified_pkt)
    assert not is_grounded, "Invented percentage must fail grounding"
    assert any("Invented percentage" in r for r in reasons)

    # Corruption 3: Invented future date (e.g. 2029-08-15)
    bad_date_text = (
        f"Matches note {justified_pkt['matched_note_id']} dated 2029-08-15: "
        f"severe weather caused freight surges."
    )
    is_grounded, reasons = check_grounding(bad_date_text, justified_pkt)
    assert not is_grounded, "Invented date must fail grounding"
    assert any("Invented dates" in r for r in reasons)

    # Corruption 4: Justified verdict without citing the matched_note_id
    bad_no_id_text = f"The route experienced high floods starting {justified_pkt['note']['date']} and cost rose."
    is_grounded, reasons = check_grounding(bad_no_id_text, justified_pkt)
    assert not is_grounded, "Justified verdict missing matched_note_id must fail"
    assert any("matched_note_id" in r for r in reasons)

    # Corruption 5: Unexplained verdict missing required unexplained confirmation phrase
    bad_unexplained_text = "Rates were slightly elevated this week compared to historical trends."
    is_grounded, reasons = check_grounding(bad_unexplained_text, unexplained_pkt)
    assert not is_grounded, "Unexplained verdict missing required phrasing must fail"
    assert any("missing standard explanation phrase" in r for r in reasons)
