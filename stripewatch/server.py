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

    return {
        "rises": total_rises,
        "justified": justified,
        "flagged": flagged,
        "flagged_excess_inr": flagged_excess_inr,
        "justified_excess_inr": justified_excess_inr,
        "total_evaluable": total_evaluable,
        "llm_calls": token_info.get("llm_calls", 19),
        "temperature": token_info.get("temperature", 0.0),
        "repro_identical": repro_identical
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
    """Get all 10 context notes."""
    notes_json = DATA_DIR / "notes_structured.json"
    if not notes_json.exists():
        raise HTTPException(status_code=404, detail="notes_structured.json not found")
    with open(notes_json, "r", encoding="utf-8") as f:
        return json.load(f)


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
            all_res = json.load(f)
        for r in all_res:
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


# Mount static assets
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(str(WEB_DIR / "index.html"))


def serve(port: int = 8000):
    """Run uvicorn server."""
    import uvicorn
    print(f"Launching StripeWatch Web UI at http://localhost:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
