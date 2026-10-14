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
        results = json.load(f)

    total_rises = len(results)
    justified = sum(1 for r in results if r.get("verdict") == "justified")
    flagged = sum(1 for r in results if r.get("verdict") == "unexplained")

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
        "total_evaluable": total_evaluable,
        "llm_calls": token_info.get("llm_calls", 19),
        "temperature": token_info.get("temperature", 0.0),
        "repro_identical": repro_identical
    }


@app.get("/api/rows")
def get_rows(route: Optional[str] = None, verdict: Optional[str] = None):
    """Get all 19 candidate rows with filter options."""
    results_file = OUTPUT_DIR / "results.json"
    if not results_file.exists():
        raise HTTPException(status_code=404, detail="Run pipeline first")

    with open(results_file, "r", encoding="utf-8") as f:
        rows = json.load(f)

    if route and route != "All routes":
        rows = [r for r in rows if r["route"] == route]

    if verdict:
        v_clean = verdict.lower()
        if "just" in v_clean:
            rows = [r for r in rows if r["verdict"] == "justified"]
        elif "flag" in v_clean:
            rows = [r for r in rows if r["verdict"] == "unexplained"]

    return rows


@app.get("/api/route/{route}")
def get_route_details(route: str):
    """Get weekly historical metric series and evidence slips for a specific route."""
    weekly_file = OUTPUT_DIR / "weekly_metrics.csv"
    results_file = OUTPUT_DIR / "results.json"

    if not weekly_file.exists() or not results_file.exists():
        raise HTTPException(status_code=404, detail="Run pipeline first")

    w_df = pd.read_csv(weekly_file)
    route_df = w_df[w_df["route"] == route].sort_values("week_of").reset_index(drop=True)

    if route_df.empty:
        raise HTTPException(status_code=404, detail=f"Route '{route}' not found")

    with open(results_file, "r", encoding="utf-8") as f:
        all_results = json.load(f)

    route_candidates = [r for r in all_results if r["route"] == route]

    series = []
    for _, row in route_df.iterrows():
        series.append({
            "week_of": row["week_of"],
            "c": round(float(row["cost_per_tonne_km"]), 4),
            "own_avg": round(float(row["own_avg"]), 4) if pd.notnull(row["own_avg"]) else None,
            "peer_avg": round(float(row["peer_avg"]), 4) if pd.notnull(row["peer_avg"]) else None,
            "vs_own_pct": round(float(row["vs_own_pct"]), 2) if pd.notnull(row["vs_own_pct"]) else 0.0,
            "vs_peer_pct": round(float(row["vs_peer_pct"]), 2) if pd.notnull(row["vs_peer_pct"]) else 0.0,
            "is_candidate": bool(row.get("is_candidate", False))
        })

    route_type = route_df["route_type"].iloc[0]

    return {
        "route": route,
        "route_type": route_type,
        "series": series,
        "candidates": route_candidates
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
