"""Explanation generator combining LLM synthesis with strict template fallback and grounding checks."""
import json
import logging
from typing import Tuple, Dict, Any, Optional

from stripewatch.ground import check_grounding
from stripewatch.llm import LLMClient

logger = logging.getLogger(__name__)


def generate_template_explanation(packet: Dict[str, Any]) -> str:
    """Generate a 100% deterministic, grounded template explanation matching sample format."""
    is_justified = (packet["verdict"] == "justified")

    if is_justified:
        note = packet["note"]
        nid = note["id"]
        date = note.get("date", packet["week_of"])
        rationale = note.get("rationale", note.get("text", ""))
        # Clean trailing period
        if rationale.endswith("."):
            rationale = rationale[:-1]
        start = note.get("start", date)
        end = note.get("end", start)
        return (
            f"Matches note {nid} dated {date}: {rationale}. "
            f"The cost rise has a clear explanation for the window {start} to {end}."
        )
    else:
        # Check near misses
        near_misses = packet.get("near_misses", [])
        if near_misses:
            nm = near_misses[0]
            nm_id = nm["id"]
            why_not = nm["why_not"]
            # Avoid repeating the note id if why_not starts with it
            if why_not.startswith(f"{nm_id} "):
                why_clause = why_not[len(nm_id) + 1:]
            else:
                why_clause = why_not
            return (
                f"The closest note ({nm_id}) {why_clause}. "
                f"No matching note found for this route or date range. Cost rise looks unexplained and worth a human review."
            )
        else:
            return "No matching note found for this route or date range. Cost rise looks unexplained and worth a human review."


def explain_candidate(
    packet: Dict[str, Any],
    llm_client: Optional[LLMClient] = None
) -> Tuple[str, Dict[str, Any]]:
    """Produce an explanation for an evidence packet.

    Tries LLM generation (temperature 0), verifies grounding.
    If LLM generation fails or fails grounding, falls back to deterministic template.

    Returns:
        (explanation_text, usage_dict)
    """
    call_key = f"{packet.get('matched_note_id') or 'NONE'}|{packet['route']}|{packet['week_of']}"

    if llm_client is None or llm_client.provider == "none":
        text = generate_template_explanation(packet)
        # Verify template grounding as a safety invariant
        is_grounded, reasons = check_grounding(text, packet)
        if not is_grounded:
            logger.error(f"Template failed grounding invariant: {reasons}")
        return text, {"provider": "none", "in": 0, "out": 0, "cached": False, "grounded": is_grounded}

    prompt = (
        "You are rewriting a verdict for a freight-cost analyst. Use ONLY the JSON below. "
        "Do not add causes, numbers, dates or note ids that are not in it.\n"
        "Start with 'Matches note' if justified or 'No matching note' / 'The closest note' if unexplained. "
        "If justified, name the note id and its dates. If unexplained, say no supporting note was found and mention near_misses only if present.\n"
        "Max 45 words, plain English, no markdown.\n"
        f"JSON: {json.dumps(packet, ensure_ascii=False)}"
    )

    llm_text, usage = llm_client.generate(prompt, purpose="explain", call_key=call_key, max_output_tokens=90)

    if llm_text:
        is_grounded, reasons = check_grounding(llm_text, packet)
        if is_grounded:
            usage["grounded"] = True
            return llm_text, usage
        else:
            logger.warning(f"LLM explanation failed grounding checks: {reasons}. Discarding and using template.")
            llm_client.record_grounding_rejection()

    # Fallback to deterministic template
    template_text = generate_template_explanation(packet)
    usage["grounded"] = True
    usage["fallback_used"] = True
    return template_text, usage
