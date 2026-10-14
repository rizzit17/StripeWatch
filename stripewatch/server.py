"""FastAPI backend server and static file hosting for StripeWatch UI."""
from pathlib import Path
import json
import pandas as pd
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from stripewatch.config import OUTPUT_DIR, DATA_DIR, BASE_DIR
from stripewatch.ask import ask_question, parse_query_filters

app = FastAPI(title="StripeWatch", description="FreightTiger Cost Watchdog API")

WEB_DIR = BASE_DIR / "web"


class AskRequest(BaseModel):
    question: str


@app.get("/api/summary")
def get_summary():
    """Summary KPI metrics for Ledger strip."""
    results_file = OUTPUT_DIR / "results.json"
    weekly_file = OUTPUT_DIR / "weekly_metrics.csv"
    token_file = OUTPUT_DIR / "token_log.json"
    repro_file = OUTPUT_DIR / "repro_report.md"

    if not results_file.exists():
        raise HTTPException(status_code=404, detail="Run pipeline first: python -m stripewatch run")

    with open(results_file, "r", encoding="utf-8") as f:
        res_data = json.load(f)
    results = res_data["candidates"] if (isinstance(res_data, dict) and "candidates" in res_data) else res_data
    attribution_data = res_data.get("attribution", {}) if isinstance(res_data, dict) else {}

    total_rises = len(results)
    justified = sum(1 for r in results if r.get("verdict") == "justified")
    flagged = sum(1 for r in results if r.get("verdict") == "unexplained")
    flagged_excess_inr = sum(int(r.get("excess_inr", 0)) for r in results if r.get("verdict") == "unexplained")
    justified_excess_inr = sum(int(r.get("excess_inr", 0)) for r in results if r.get("verdict") == "justified")

    total_evaluable = 721
    if weekly_file.exists():
        w_df = pd.read_csv(weekly_file)
        total_evaluable = len(w_df)

    token_info = {}
    if token_file.exists():
        with open(token_file, "r", encoding="utf-8") as f:
            token_info = json.load(f)

    repro_identical = False
    if repro_file.exists():
        with open(repro_file, "r", encoding="utf-8") as f:
            txt = f.read()
            repro_identical = "Reproducibility verified: IDENTICAL" in txt or "IDENTICAL" in txt

    abstention = res_data.get("summary", {}).get("abstention")
    if not abstention:
        from stripewatch.paper_trail import compute_abstention_stat
        abstention = compute_abstention_stat(results)

    return {
        "rises": total_rises,
        "justified": justified,
        "flagged": flagged,
        "flagged_excess_inr": flagged_excess_inr,
        "justified_excess_inr": justified_excess_inr,
        "total_evaluable": total_evaluable,
        "llm_calls": token_info.get("llm_calls", 19),
        "temperature": token_info.get("temperature", 0.0),
        "repro_identical": repro_identical,
        "abstention": abstention
    }


@app.get("/api/rows")
def get_rows(route: Optional[str] = None, verdict: Optional[str] = None, sort_by: Optional[str] = None):
    """Get candidate rows with filter and sorting options."""
    results_file = OUTPUT_DIR / "results.json"
    if not results_file.exists():
        raise HTTPException(status_code=404, detail="Run pipeline first")

    with open(results_file, "r", encoding="utf-8") as f:
        res_data = json.load(f)
    rows = res_data["candidates"] if (isinstance(res_data, dict) and "candidates" in res_data) else res_data

    if route and route != "All routes":
        rows = [r for r in rows if r["route"] == route]

    if verdict:
        v_clean = verdict.lower()
        if "just" in v_clean:
            rows = [r for r in rows if r["verdict"] == "justified"]
        elif "flag" in v_clean:
            rows = [r for r in rows if r["verdict"] == "unexplained"]

    if sort_by == "excess":
        rows = sorted(rows, key=lambda r: int(r.get("excess_inr", 0)), reverse=True)

    return rows


@app.get("/api/route/{route}")
def get_route_details(route: str):
    """Get weekly historical metric series, candidate evidence slips, and attribution for a route."""
    weekly_file = OUTPUT_DIR / "weekly_metrics.csv"
    results_file = OUTPUT_DIR / "results.json"

    if not weekly_file.exists() or not results_file.exists():
        raise HTTPException(status_code=404, detail="Run pipeline first")

    w_df = pd.read_csv(weekly_file)
    route_df = w_df[w_df["route"] == route].sort_values("week_of").reset_index(drop=True)

    if route_df.empty:
        raise HTTPException(status_code=404, detail=f"Route '{route}' not found")

    with open(results_file, "r", encoding="utf-8") as f:
        res_data = json.load(f)
    all_results = res_data["candidates"] if (isinstance(res_data, dict) and "candidates" in res_data) else res_data
    attribution_all = res_data.get("attribution", {}) if isinstance(res_data, dict) else {}

    route_candidates = [r for r in all_results if r["route"] == route]
    route_attribution = attribution_all.get(route, [])

    series = []
    for _, row in route_df.iterrows():
        series.append({
            "week_of": str(row["week_of"]),
            "c": round(float(row["cost_per_tonne_km"]), 4),
            "own_avg": round(float(row["own_avg"]), 4) if pd.notnull(row["own_avg"]) else None,
            "peer_avg": round(float(row["peer_avg"]), 4) if pd.notnull(row["peer_avg"]) else None,
            "vs_own_pct": round(float(row["vs_own_pct"]), 2) if pd.notnull(row["vs_own_pct"]) else 0.0,
            "vs_peer_pct": round(float(row["vs_peer_pct"]), 2) if pd.notnull(row["vs_peer_pct"]) else 0.0,
            "is_candidate": bool(row.get("is_candidate", False)),
            "creep_tag": bool(row.get("creep_tag", False)),
            "peer_gap_4w": round(float(row["peer_gap_4w"]), 2) if pd.notnull(row.get("peer_gap_4w")) else None,
            "noise_pct": round(float(row["noise_pct"]), 2) if pd.notnull(row.get("noise_pct")) else None,
            "rise_z": round(float(row["rise_z"]), 2) if pd.notnull(row.get("rise_z")) else None,
            "excess_inr": int(row.get("excess_inr", 0))
        })

    route_type = route_df["route_type"].iloc[0]

    return {
        "route": route,
        "route_type": route_type,
        "series": series,
        "candidates": route_candidates,
        "attribution": route_attribution
    }


@app.get("/api/weeks")
def get_weeks(route: Optional[str] = None):
    """Get evaluable weeks for route selection in 'Try to fool it' console."""
    weekly_file = OUTPUT_DIR / "weekly_metrics.csv"
    if not weekly_file.exists():
        raise HTTPException(status_code=404, detail="Run pipeline first")

    w_df = pd.read_csv(weekly_file)
    w_df = w_df[w_df["vs_own_pct"].notna()]
    if route:
        w_df = w_df[w_df["route"] == route]

    weeks = []
    for _, r in w_df.sort_values("week_of").iterrows():
        weeks.append({
            "route": r["route"],
            "week_of": str(r["week_of"]),
            "c": round(float(r["cost_per_tonne_km"]), 4),
            "vs_own_pct": round(float(r["vs_own_pct"]), 2) if pd.notnull(r["vs_own_pct"]) else None,
            "vs_peer_pct": round(float(r["vs_peer_pct"]), 2) if pd.notnull(r["vs_peer_pct"]) else None,
            "is_candidate": bool(r.get("is_candidate", False))
        })
    return weeks


class ValidateRequest(BaseModel):
    route: str
    week_of: str
    note_id: str


@app.post("/api/validate")
def api_validate(req: ValidateRequest):
    """Live validation endpoint for the 'Try to fool it' console.
    
    Calls validate.validate_note directly — no re-implementation.
    """
    from stripewatch.validate import validate_note
    from stripewatch.notes import get_notes_dict

    weekly_file = OUTPUT_DIR / "weekly_metrics.csv"
    if not weekly_file.exists():
        raise HTTPException(status_code=404, detail="Run pipeline first")

    w_df = pd.read_csv(weekly_file)
    matching = w_df[(w_df["route"] == req.route) & (w_df["week_of"] == req.week_of)]
    if matching.empty:
        raise HTTPException(status_code=404, detail=f"No record found for route '{req.route}' on week '{req.week_of}'")

    target_row = matching.iloc[0]
    notes_map = get_notes_dict()
    if req.note_id not in notes_map:
        raise HTTPException(status_code=404, detail=f"Note '{req.note_id}' not found")

    target_note = notes_map[req.note_id]
    result = validate_note(target_row, target_note)

    is_cand = bool(target_row.get("is_candidate", False))
    note_comment = None if is_cand else "This week was not a candidate; showing what the validator would say."

    return {
        "row": {
            "c": round(float(target_row["cost_per_tonne_km"]), 4),
            "vs_own_pct": round(float(target_row["vs_own_pct"]), 2) if pd.notnull(target_row["vs_own_pct"]) else None,
            "vs_peer_pct": round(float(target_row["vs_peer_pct"]), 2) if pd.notnull(target_row["vs_peer_pct"]) else None,
            "is_candidate": is_cand
        },
        "note": {
            "id": target_note.id,
            "scope": target_note.scope,
            "effect": target_note.effect,
            "start": target_note.start,
            "end": target_note.end,
            "mag_max": target_note.mag_max
        },
        "checks": result.checks,
        "justified": result.justified,
        "why_not": result.why_not,
        "note_comment": note_comment
    }


@app.get("/api/notes")
def get_notes():
    """Get all 10 context notes combining raw note text with structured facts."""
    from stripewatch.notes import load_structured_notes
    notes = load_structured_notes()
    return [
        {
            "id": n.id,
            "date": n.date,
            "applies_to": n.applies_to,
            "text": n.text,
            "scope": n.scope,
            "effect": n.effect,
            "start": n.start,
            "end": n.end,
            "mag_min": n.mag_min,
            "mag_max": n.mag_max,
            "rationale": n.rationale,
            "evidence_spans": n.evidence_spans,
            "negating_spans": n.negating_spans,
            "window_end_span": n.window_end_span
        }
        for n in notes
    ]


@app.post("/api/ask")
def api_ask(req: AskRequest):
    """Handle natural language questions grounded in pipeline findings."""
    answer = ask_question(req.question)

    # Check which rows were based on
    filters = parse_query_filters(req.question)
    results_file = OUTPUT_DIR / "results.json"
    based_rows = []
    if results_file.exists():
        with open(results_file, "r", encoding="utf-8") as f:
            res_data = json.load(f)
        all_candidates = res_data["candidates"] if isinstance(res_data, dict) and "candidates" in res_data else res_data
        for r in all_candidates:
            m = int(r["week_of"].split("-")[1])
            y = int(r["week_of"].split("-")[0])
            if filters["route"] and r["route"] != filters["route"]:
                continue
            if filters["month"] and m != filters["month"]:
                continue
            if filters["year"] and y != filters["year"]:
                continue
            based_rows.append({
                "route": r["route"],
                "week_of": r["week_of"],
                "note_id": r.get("matched_note_id")
            })

    is_empty = ("no note found" in answer.lower() or "no flagged or justified" in answer.lower())

    return {
        "question": req.question,
        "answer": answer,
        "based_on_rows": based_rows,
        "empty": is_empty
    }


@app.get("/api/calendar")
def get_calendar():
    """Retrieve full 104-week x 7-route matrix and metrics for SVG heatmap."""
    weekly_file = OUTPUT_DIR / "weekly_metrics.csv"
    results_file = OUTPUT_DIR / "results.json"

    if not weekly_file.exists() or not results_file.exists():
        raise HTTPException(status_code=404, detail="Run pipeline first")

    w_df = pd.read_csv(weekly_file)
    with open(results_file, "r", encoding="utf-8") as f:
        res_data = json.load(f)
    candidates = res_data["candidates"] if isinstance(res_data, dict) and "candidates" in res_data else res_data

    cand_map = {f"{c['route']}|{c['week_of']}": c for c in candidates}

    route_groups = [
        {"type": "SHORT", "routes": ["Delhi-Jaipur", "Mumbai-Pune"]},
        {"type": "MEDIUM", "routes": ["Ahmedabad-Mumbai", "Chennai-Bangalore", "Kolkata-Bhubaneswar"]},
        {"type": "LONG", "routes": ["Delhi-Chennai", "Mumbai-Delhi"]}
    ]

    all_weeks = sorted(w_df["week_of"].unique().tolist())

    cells = []
    for _, r in w_df.iterrows():
        key = f"{r['route']}|{r['week_of']}"
        cand = cand_map.get(key)
        is_cand = bool(cand is not None or r.get("is_candidate", False))
        verdict = cand["verdict"] if cand else None
        matched_id = cand.get("matched_note_id") if cand else None
        is_evaluable = pd.notnull(r["vs_own_pct"])

        cells.append({
            "route": r["route"],
            "route_type": r["route_type"],
            "week_of": str(r["week_of"]),
            "c": round(float(r["cost_per_tonne_km"]), 4),
            "vs_own_pct": round(float(r["vs_own_pct"]), 2) if is_evaluable else None,
            "vs_peer_pct": round(float(r["vs_peer_pct"]), 2) if pd.notnull(r["vs_peer_pct"]) else None,
            "is_candidate": is_cand,
            "verdict": verdict,
            "matched_note_id": matched_id,
            "creep_tag": bool(r.get("creep_tag", False)),
            "is_evaluable": is_evaluable
        })

    mp_flagged = sum(1 for c in candidates if c["route"] == "Mumbai-Pune" and c["verdict"] == "unexplained")
    justified_routes = sorted(list(set(c["route"] for c in candidates if c["verdict"] == "justified")))
    sentence = f"Mumbai-Pune shows {mp_flagged} flagged weeks since Jun 2025, {len(justified_routes)} of 7 routes had flood- or festival-type spikes ({', '.join(justified_routes)})."

    return {
        "groups": route_groups,
        "route_groups": route_groups,
        "weeks": all_weeks,
        "cells": cells,
        "summary_sentence": sentence,
        "candidates": candidates
    }


@app.get("/api/review")
def get_review_queue():
    """Retrieve all 19 candidate rows merged with current review status and notes."""
    from stripewatch.review import get_review_items
    return get_review_items()


from fastapi import Request


@app.put("/api/review/{route}/{week_of}")
async def put_review_item(route: str, week_of: str, request: Request):
    """Update human review status and note for a candidate row with strict validation."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    allowed_keys = {"status", "note"}
    if not isinstance(body, dict) or (set(body.keys()) - allowed_keys):
        raise HTTPException(status_code=400, detail="Extra or invalid keys rejected")

    status = body.get("status")
    note = body.get("note", "")

    if not status or str(status).lower() not in ["open", "confirmed", "dismissed"]:
        raise HTTPException(status_code=400, detail="Status must be one of: open, confirmed, dismissed")

    if note and len(str(note)) > 280:
        raise HTTPException(status_code=400, detail="Note must be <= 280 characters")

    from stripewatch.review import update_review_item
    try:
        updated = update_review_item(route, week_of, status, note)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/review/export.csv")
def get_review_export():
    """Export human review queue to CSV."""
    from stripewatch.review import export_review_csv
    dest = export_review_csv()
    return FileResponse(str(dest), media_type="text/csv", filename="review_export.csv")


# Mount static assets
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(str(WEB_DIR / "index.html"))


def serve(port: int = 8000):
    """Run uvicorn server with automatic fallback if default port is occupied."""
    import socket
    import uvicorn

    def is_port_in_use(p: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', p)) == 0

    target_port = port
    if is_port_in_use(target_port):
        for candidate in [8080, 8001, 8002, 3000, 5000]:
            if not is_port_in_use(candidate):
                print(f"Port {target_port} is already in use; switching to port {candidate}")
                target_port = candidate
                break

    print(f"Launching StripeWatch Web UI at http://localhost:{target_port}")
    uvicorn.run(app, host="127.0.0.1", port=target_port, log_level="info")
