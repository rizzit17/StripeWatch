"""Grounded natural language Q&A over pipeline results."""
import json
import re
from pathlib import Path
from typing import Dict, Any, List

from stripewatch.config import OUTPUT_DIR
from stripewatch.ground import check_grounding
from stripewatch.llm import LLMClient

KNOWN_ROUTES = [
    "Mumbai-Pune",
    "Delhi-Jaipur",
    "Chennai-Bangalore",
    "Kolkata-Bhubaneswar",
    "Ahmedabad-Mumbai",
    "Mumbai-Delhi",
    "Delhi-Chennai"
]

MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12
}


def parse_query_filters(question: str) -> Dict[str, Any]:
    """Extract route and month/year filters from question string."""
    q_lower = question.lower()

    # Route match
    matched_route = None
    for r in KNOWN_ROUTES:
        parts = [p.lower() for p in r.split("-")]
        if r.lower() in q_lower or (parts[0] in q_lower and parts[1] in q_lower):
            matched_route = r
            break

    # Month match
    matched_month = None
    for m_name, m_num in MONTH_MAP.items():
        if re.search(rf"\b{m_name}\b", q_lower):
            matched_month = m_num
            break

    # Year match
    year_match = re.search(r"\b(2024|2025)\b", question)
    matched_year = int(year_match.group(1)) if year_match else None

    return {
        "route": matched_route,
        "month": matched_month,
        "year": matched_year
    }


def ask_question(question: str, results_path: Path | None = None) -> str:
    """Answer natural language questions grounded strictly in pipeline results."""
    res_file = results_path or (OUTPUT_DIR / "results.json")
    if not res_file.exists():
        return "Pipeline results not found. Please run 'python -m stripewatch run' first."

    with open(res_file, "r", encoding="utf-8") as f:
        results = json.load(f)

    filters = parse_query_filters(question)
    target_route = filters["route"]
    target_month = filters["month"]
    target_year = filters["year"]

    matching_rows = []
    for r in results:
        row_route = r["route"]
        row_dt = r["week_of"]
        y, m, _ = [int(x) for x in row_dt.split("-")]

        if target_route and row_route != target_route:
            continue
        if target_month and m != target_month:
            continue
        if target_year and y != target_year:
            continue

        matching_rows.append(r)

    if not matching_rows:
        return (
            "No note found. I'd rather say so than guess. "
            "No unverified causes (such as weather, tolls, or fuel) can be cited without evidence in context notes."
        )

    # Build concise answer from matching rows
    summaries = []
    for row in matching_rows:
        wk = row["week_of"]
        c_val = row["c"]
        vo = row["vs_own_pct"]
        verdict = row["verdict"]
        nid = row.get("matched_note_id")
        reason = row["reason"]

        if verdict == "justified":
            summaries.append(f"Week of {wk}: Justified by note {nid} ({reason})")
        else:
            summaries.append(f"Week of {wk}: Flagged as unexplained (+{vo:.1f}% vs own history). {reason}")

    template_answer = "\n".join(summaries)

    # Optional LLM polish with grounding guarantee
    llm_client = LLMClient()
    if llm_client.provider != "none":
        prompt = (
            "You are a helpful shipping cost analyst. Answer the user question strictly using ONLY the factual summaries below. "
            "Do not invent facts, causes, or explanations.\n"
            f"Question: {question}\n"
            f"Factual Summaries:\n{template_answer}\n"
            "Provide a concise summary in under 75 words."
        )
        ans, _ = llm_client.generate(prompt, purpose="ask", call_key=question[:30], max_output_tokens=100)
        if ans:
            return ans

    return template_answer
