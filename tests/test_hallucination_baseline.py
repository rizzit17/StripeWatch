"""Unit tests for Backend A: Hallucination baseline without network calls."""
import pytest
from eval.hallucination_baseline import (
    classify_text_lexicon,
    classify_sentenced_reasons,
    run_hallucination_baseline
)


def test_lexicon_classifier_canned_strings():
    """Verify lexicon classifier accurately identifies cause, hedged, and other on 8 canned strings."""
    # 1. Direct diesel cause
    assert classify_text_lexicon("Costs rose due to sudden diesel price hike.") == "asserts a cause"
    # 2. Monsoon flood cause
    assert classify_text_lexicon("Monsoon rains and highway flooding caused detours.") == "asserts a cause"
    # 3. Pure hedged statement
    assert classify_text_lexicon("Cannot determine the reason from available records.") == "hedged"
    # 4. Insufficient information
    assert classify_text_lexicon("There is insufficient evidence to explain this spike.") == "hedged"
    # 5. Hedged with cause word -> cause takes precedence
    assert classify_text_lexicon("It is unclear whether diesel prices were a factor.") == "asserts a cause"
    # 6. Strike / driver shortage
    assert classify_text_lexicon("A local driver shortage led to freight rate escalation.") == "asserts a cause"
    # 7. Unrelated statement (other)
    assert classify_text_lexicon("Volume increased by 20% compared to last quarter.") == "other"
    # 8. Empty or neutral string
    assert classify_text_lexicon("The weekly trend was observed.") == "other"


def test_sentenced_reasons_classification():
    """Verify that StripeWatch sentences mentioning causes with rejection words are marked as rejected near-miss."""
    sample_reason = (
        "Unexplained cost increase. Note N001 was rejected because its flood disruption window "
        "ended prior to this week. Diesel hike note N003 cannot explain route-specific peer outlier."
    )
    findings = classify_sentenced_reasons(sample_reason)
    assert len(findings) >= 2
    for s, label, category in findings:
        assert label == "mentioned as rejected near-miss"


def test_baseline_clean_exit_no_provider(monkeypatch):
    """Verify run_hallucination_baseline exits cleanly when provider is 'none'."""
    monkeypatch.setattr("eval.hallucination_baseline.LLM_PROVIDER", "none")
    # Should exit cleanly without error
    run_hallucination_baseline()
