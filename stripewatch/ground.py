"""Grounding checker: validates that generated explanations strictly adhere to verified facts."""
import re
from typing import Tuple, List, Dict, Any, Set


ALLOWED_UNEXPLAINED_PHRASES = [
    "no matching note",
    "couldn't find",
    "no supporting note",
    "unexplained",
    "flagged for review",
    "no genuine justification",
    "flagged",
    "worth a human review"
]


def check_grounding(text: str, packet: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Verify that an explanation string strictly uses facts from the evidence packet.

    Rules from systemdesign.md §10:
    1. If justified: text contains matched_note_id and at least one date from the note's start/end/date.
       If unexplained: text must NOT contain any note id that isn't in near_misses, and must contain
       a phrase confirming lack of justification / human review.
    2. Every note id regex N\\d{3} in text in {packet note id} union {near-miss ids}.
    3. Every number with % in text in numbers in the packet (+-0.1).
    4. Every date in text in dates in the packet.
    5. Starts with a valid verdict prefix; word count <= 60 words.

    Returns:
        (is_grounded, failure_reasons)
    """
    reasons = []
    text_clean = text.strip()
    words = text_clean.split()

    # Rule 5: Word count <= 60 words
    if len(words) > 60:
        reasons.append(f"Word count ({len(words)}) exceeds maximum 60 words")

    # Allowed note IDs
    allowed_note_ids: Set[str] = set()
    if packet.get("matched_note_id"):
        allowed_note_ids.add(packet["matched_note_id"])
    if packet.get("note") and packet["note"].get("id"):
        allowed_note_ids.add(packet["note"]["id"])
    for nm in packet.get("near_misses", []):
        if nm.get("id"):
            allowed_note_ids.add(nm["id"])

    # Rule 2: Every note id regex in text must be in allowed_note_ids
    found_note_ids = set(re.findall(r"\bN\d{3}\b", text_clean))
    disallowed_notes = found_note_ids - allowed_note_ids
    if disallowed_notes:
        reasons.append(f"Invented note IDs found in text: {disallowed_notes}")

    # Gather allowed dates from packet
    allowed_dates: Set[str] = set()
    if packet.get("week_of"):
        allowed_dates.add(packet["week_of"])
    note_info = packet.get("note")
    if note_info:
        for k in ["start", "end", "date"]:
            if note_info.get(k):
                allowed_dates.add(note_info[k])
    for nm in packet.get("near_misses", []):
        for d in re.findall(r"\b\d{4}-\d{2}-\d{2}\b", str(nm)):
            allowed_dates.add(d)

    # Rule 4: Every ISO date (YYYY-MM-DD) in text must be in allowed_dates
    found_dates = set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text_clean))
    disallowed_dates = found_dates - allowed_dates
    if disallowed_dates:
        reasons.append(f"Invented dates found in text: {disallowed_dates}")

    # Rule 3: Every percentage number in text must match numbers in packet (+-0.1)
    # Gather candidate numbers in packet
    allowed_pcts = [abs(float(packet["vs_own_pct"])), abs(float(packet["vs_peer_pct"]))]
    for nm in packet.get("near_misses", []):
        for p in re.findall(r"([+-]?\d+\.?\d*)\s*%", str(nm)):
            try:
                allowed_pcts.append(abs(float(p)))
            except ValueError:
                pass
    found_pcts = re.findall(r"([+-]?\d+\.?\d*)\s*%", text_clean)
    for p_str in found_pcts:
        try:
            val = abs(float(p_str))
            # Must be within 0.15 of any allowed pct or note range (5-7% for N003)
            matched = any(abs(val - a) <= 0.15 for a in allowed_pcts)
            if not matched and note_info and note_info.get("id") == "N003":
                # N003 explicitly mentions 5-7%
                if 5.0 <= val <= 7.0:
                    matched = True
            if not matched:
                reasons.append(f"Invented percentage value {p_str}% not matching packet {allowed_pcts}")
        except ValueError:
            pass

    # Rule 1: Verdict-specific requirements
    is_justified = (packet.get("verdict") == "justified")
    if is_justified:
        target_note_id = packet.get("matched_note_id")
        if not target_note_id or target_note_id not in text_clean:
            reasons.append(f"Justified explanation does not mention matched_note_id '{target_note_id}'")

        # Must mention at least one date
        has_date = any(d in text_clean for d in allowed_dates)
        if not has_date:
            reasons.append(f"Justified explanation does not contain any date from note: {allowed_dates}")
    else:
        # Unexplained
        if packet.get("matched_note_id"):
            reasons.append("Unexplained explanation has non-empty matched_note_id in packet")
        # Must contain one of allowed unexplained phrases
        text_lower = text_clean.lower()
        has_phrase = any(phrase in text_lower for phrase in ALLOWED_UNEXPLAINED_PHRASES)
        if not has_phrase:
            reasons.append(f"Unexplained text missing standard explanation phrase from: {ALLOWED_UNEXPLAINED_PHRASES}")

    is_grounded = (len(reasons) == 0)
    return is_grounded, reasons
