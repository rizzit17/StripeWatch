"""Static site generator for StripeWatch UI-8.

Compiles complete zero-backend static distribution into dist/ with prebaked
JSON API snapshots and a compact validation matrix for offline interactive verification.
"""
import sys
from pathlib import Path
import json
import shutil
import os
import re
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stripewatch.config import BASE_DIR, OUTPUT_DIR
from stripewatch.server import (
    get_summary,
    get_rows,
    get_calendar,
    get_notes,
    get_weeks,
    get_route_details
)
from stripewatch.review import get_review_items
from stripewatch.validate import validate_note
from stripewatch.notes import get_notes_dict, load_structured_notes

DIST_DIR = BASE_DIR / "dist"
DIST_DATA_DIR = DIST_DIR / "data"
WEB_DIR = BASE_DIR / "web"


def build_compact_validate_matrix() -> dict:
    """Precompute validation for every route x evaluable week x note.

    Stored compactly using check bits and a why_not code table:
    Bits:
      1: effect_is_cost_rise
      2: route_in_scope
      4: window_overlaps
      8: magnitude_ok
      16: not_peer_outlier_for_universal
      32: justified
    """
    weekly_file = OUTPUT_DIR / "weekly_metrics.csv"
    w_df = pd.read_csv(weekly_file)
    evaluable_df = w_df[w_df["vs_own_pct"].notna()]
    notes = load_structured_notes()

    why_reasons = [""]
    why_map = {"": 0}
    matrix = {}

    for _, row in evaluable_df.iterrows():
        route = str(row["route"]).strip()
        week_of = str(row["week_of"]).strip()

        for note in notes:
            res = validate_note(row, note)
            bits = 0
            if res.checks.get("effect_is_cost_rise"):
                bits |= 1
            if res.checks.get("route_in_scope"):
                bits |= 2
            if res.checks.get("window_overlaps"):
                bits |= 4
            if res.checks.get("magnitude_ok"):
                bits |= 8
            if res.checks.get("not_peer_outlier_for_universal"):
                bits |= 16
            if res.justified:
                bits |= 32

            why_str = res.why_not or ""
            if why_str not in why_map:
                why_map[why_str] = len(why_reasons)
                why_reasons.append(why_str)

            why_idx = why_map[why_str]
            key = f"{route}|{week_of}|{note.id}"
            matrix[key] = [bits, why_idx]

    return {
        "why_reasons": why_reasons,
        "matrix": matrix
    }


def generate_prebaked_qa() -> list:
    """Return 3 prebaked question-answer pairs for static Ask mode."""
    return [
        {
            "question": "Why did Chennai-Bangalore freight cost rise in February and March 2025?",
            "answer": "Chennai-Bangalore experienced flooding from Feb 24 to Mar 8, 2025. Cost rises during weeks 2025-02-24 and 2025-03-03 are justified by note N001. Rises on 2025-03-10 and 2025-03-17 are flagged because highway conditions normalized by Mar 9 (note N009).",
            "based_on_rows": [
                {"route": "Chennai-Bangalore", "week_of": "2025-02-24", "note_id": "N001"},
                {"route": "Chennai-Bangalore", "week_of": "2025-03-03", "note_id": "N001"},
                {"route": "Chennai-Bangalore", "week_of": "2025-03-10", "note_id": None},
                {"route": "Chennai-Bangalore", "week_of": "2025-03-17", "note_id": None}
            ]
        },
        {
            "question": "What caused the persistent cost spikes on Mumbai-Pune in late 2025?",
            "answer": "Mumbai-Pune exhibited 10 flagged weeks between June and December 2025 with persistent +20% to +35% peer gaps. Note N006 confirms no major supply disruptions, and diesel note N003 cannot explain a single-corridor outlier. All 10 weeks remain unexplained.",
            "based_on_rows": [
                {"route": "Mumbai-Pune", "week_of": "2025-09-15", "note_id": None},
                {"route": "Mumbai-Pune", "week_of": "2025-10-06", "note_id": None},
                {"route": "Mumbai-Pune", "week_of": "2025-10-27", "note_id": None}
            ]
        },
        {
            "question": "Was the Ahmedabad-Mumbai cost increase in January 2025 justified?",
            "answer": "Yes. On the week of 2025-01-20, Ahmedabad-Mumbai rose +29.5% vs history and +22.5% vs peers. Note N002 documents temporary festival-week surcharges and driver shortages for this specific corridor, fully justifying the anomaly.",
            "based_on_rows": [
                {"route": "Ahmedabad-Mumbai", "week_of": "2025-01-20", "note_id": "N002"}
            ]
        }
    ]


def build_static():
    """Build the complete self-contained static site into dist/."""
    print("[Static Build] Initializing static export into dist/...")
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Snapshots of API responses
    print("[Static Build] Generating API snapshots in dist/data/...")
    with open(DIST_DATA_DIR / "summary.json", "w", encoding="utf-8") as f:
        json.dump(get_summary(), f, indent=2)

    with open(DIST_DATA_DIR / "rows.json", "w", encoding="utf-8") as f:
        json.dump(get_rows(), f, indent=2)

    with open(DIST_DATA_DIR / "calendar.json", "w", encoding="utf-8") as f:
        json.dump(get_calendar(), f, indent=2)

    with open(DIST_DATA_DIR / "notes.json", "w", encoding="utf-8") as f:
        json.dump(get_notes(), f, indent=2)

    with open(DIST_DATA_DIR / "weeks.json", "w", encoding="utf-8") as f:
        json.dump(get_weeks(), f, indent=2)

    rev_items = get_review_items()
    with open(DIST_DATA_DIR / "review_default.json", "w", encoding="utf-8") as f:
        json.dump(rev_items, f, indent=2)
    with open(DIST_DATA_DIR / "review.json", "w", encoding="utf-8") as f:
        json.dump(rev_items, f, indent=2)

    routes = [
        "Ahmedabad-Mumbai",
        "Chennai-Bangalore",
        "Delhi-Chennai",
        "Delhi-Jaipur",
        "Kolkata-Bhubaneswar",
        "Mumbai-Delhi",
        "Mumbai-Pune"
    ]
    for r in routes:
        safe_name = f"route_{r}.json"
        with open(DIST_DATA_DIR / safe_name, "w", encoding="utf-8") as f:
            json.dump(get_route_details(r), f, indent=2)

    # 2. Compact validate matrix
    print("[Static Build] Precomputing compact validation matrix (7 routes x 103 weeks x 10 notes)...")
    matrix_data = build_compact_validate_matrix()
    matrix_file = DIST_DATA_DIR / "validate_matrix.json"
    with open(matrix_file, "w", encoding="utf-8") as f:
        json.dump(matrix_data, f, separators=(',', ':'))

    matrix_size_kb = matrix_file.stat().st_size / 1024
    print(f"[Static Build] validate_matrix.json size: {matrix_size_kb:.1f} KB")

    # 3. Prebaked QA
    with open(DIST_DATA_DIR / "ask_prebaked.json", "w", encoding="utf-8") as f:
        json.dump(generate_prebaked_qa(), f, indent=2)

    # 4. Copy web assets with static configuration
    print("[Static Build] Copying web assets to dist/...")
    shutil.copy2(WEB_DIR / "app.css", DIST_DIR / "app.css")
    shutil.copy2(WEB_DIR / "app.js", DIST_DIR / "app.js")

    with open(WEB_DIR / "index.html", "r", encoding="utf-8") as f:
        html_content = f.read()

    # In index.html: make CSS/JS paths relative and inject window.STATIC_DEMO = true
    html_content = html_content.replace('href="/static/app.css"', 'href="app.css"')
    html_content = html_content.replace('src="/static/app.js"', 'src="app.js"')
    static_tag = '<script>window.STATIC_DEMO = true;</script>\n  <script src="app.js"></script>'
    html_content = html_content.replace('<script src="app.js"></script>', static_tag)

    with open(DIST_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    # 5. Calculate total dist/ size
    total_size_bytes = sum(f.stat().st_size for f in DIST_DIR.rglob("*") if f.is_file())
    total_size_mb = total_size_bytes / (1024 * 1024)
    print(f"[Static Build] Total dist/ size: {total_size_mb:.2f} MB (Budget: < 5.0 MB)")
    assert total_size_mb < 5.0, f"dist/ exceeded 5.0 MB budget: {total_size_mb:.2f} MB"

    # 6. Verify zero secrets or absolute paths
    print("[Static Build] Verifying zero secrets and zero absolute local paths...")
    forbidden_patterns = [
        r"AIza[0-9A-Za-z-_]{35}",
        r"gsk_[0-9A-Za-z]{30,}",
        r"c:/Users/",
        r"/home/",
        r"Users/Rishit"
    ]
    violations = []
    for p in DIST_DIR.rglob("*"):
        if p.is_file():
            try:
                txt = p.read_text(encoding="utf-8")
                for pat in forbidden_patterns:
                    if re.search(pat, txt, re.IGNORECASE):
                        violations.append((p.name, pat))
            except Exception:
                pass

    if violations:
        raise AssertionError(f"Forbidden patterns found in dist/: {violations}")

    print("[Static Build] SUCCESS! dist/ is clean, sanitized, and ready for hosting.")


if __name__ == "__main__":
    build_static()
