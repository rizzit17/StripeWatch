"""Unit tests for UI-3: Evidence and negating spans validation and text splitting."""
import json
import pandas as pd
from stripewatch.config import NOTES_FILE, NOTES_STRUCTURED_FILE


def test_spans_occur_exactly_once():
    """Verify that every defined span occurs exactly once in its note's raw text."""
    raw_df = pd.read_csv(NOTES_FILE)
    raw_notes = {r["note_id"]: r["note"] for _, r in raw_df.iterrows()}

    with open(NOTES_STRUCTURED_FILE, "r", encoding="utf-8") as f:
        structured = json.load(f)

    for item in structured:
        nid = item["id"]
        text = raw_notes.get(nid, "")
        assert text, f"Missing raw note text for {nid}"

        # Evidence spans
        for span in item.get("evidence_spans", []):
            cnt = text.count(span)
            assert cnt == 1, f"Evidence span '{span}' in {nid} occurs {cnt} times, expected 1"

        # Window end span
        if "window_end_span" in item:
            span = item["window_end_span"]
            cnt = text.count(span)
            assert cnt == 1, f"Window end span '{span}' in {nid} occurs {cnt} times, expected 1"

        # Negating spans
        for span in item.get("negating_spans", []):
            cnt = text.count(span)
            assert cnt == 1, f"Negating span '{span}' in {nid} occurs {cnt} times, expected 1"


def split_text_by_spans(text: str, spans: list[str]) -> list[dict]:
    """Pure-Python reference implementation of the text-node splitting algorithm."""
    # Find all occurrences with start and end indices
    intervals = []
    for span in spans:
        if not span:
            continue
        idx = text.find(span)
        while idx != -1:
            intervals.append((idx, idx + len(span), span))
            idx = text.find(span, idx + len(span))

    # Sort intervals by start index
    intervals.sort(key=lambda x: (x[0], x[1]))

    # Merge or handle non-overlapping
    segments = []
    last_idx = 0
    for start, end, span in intervals:
        if start < last_idx:
            # Overlapping span, adjust start
            start = last_idx
        if start > last_idx:
            segments.append({"text": text[last_idx:start], "is_mark": False})
        if end > start:
            segments.append({"text": text[start:end], "is_mark": True, "span": span})
            last_idx = end
    if last_idx < len(text):
        segments.append({"text": text[last_idx:], "is_mark": False})
    return segments


def test_split_text_by_spans():
    """Verify segment splitting correctly preserves original text."""
    sample = "Severe flooding from Feb 24 to Mar 8 led to higher trip costs across highways."
    spans = ["Feb 24 to Mar 8", "higher trip costs"]
    segs = split_text_by_spans(sample, spans)

    reassembled = "".join(s["text"] for s in segs)
    assert reassembled == sample

    marked = [s["text"] for s in segs if s["is_mark"]]
    assert marked == spans
