"""Core CLI and execution commands for StripeWatch."""
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd

from stripewatch.config import (
    OUTPUT_DIR,
    LLM_PROVIDER,
    FLAG_OWN_PCT,
    FLAG_OWN_SOFT_PCT,
    FLAG_PEER_PCT,
    CACHE_DIR
)
from stripewatch.loader import load_shipments, load_notes
from stripewatch.weekly import to_weekly
from stripewatch.baselines import add_baselines
from stripewatch.detect import detect_candidates, is_candidate_mask
from stripewatch.notes import get_notes_dict
from stripewatch.retrieve import NoteRetriever
from stripewatch.validate import decide_verdict
from stripewatch.evidence import build_evidence_packet
from stripewatch.explain import explain_candidate
from stripewatch.ground import check_grounding
from stripewatch.llm import LLMClient
from stripewatch.writer import (
    format_output_row,
    write_contract_csv,
    write_weekly_metrics,
    write_results_json
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_pipeline(
    provider: str | None = None,
    enable_cache: bool = True,
    cold_cache: bool = False
) -> Dict[str, Any]:
    """Execute the full StripeWatch pipeline end-to-end.

    Returns:
        Dictionary summarizing execution counts and output paths.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if cold_cache:
        cache_file = CACHE_DIR / "llm_cache.json"
        if cache_file.exists():
            cache_file.unlink()

    print("============================================================")
    print("  STRIPEWATCH: Automated Shipping Cost Anomaly Watchdog    ")
    print("============================================================")

    # 1. Load data
    print("[1/6] Loading shipment records and context notes...")
    shipments_df = load_shipments()
    notes_df = load_notes()
    print(f"      Loaded {len(shipments_df)} shipments across {shipments_df['route'].nunique()} routes.")

    # 2. Weekly aggregation
    print("[2/6] Aggregating shipments into Monday-aligned weeks (ratio of sums)...")
    weekly_df = to_weekly(shipments_df)
    print(f"      Computed {len(weekly_df)} route-weeks.")

    # 3. Baselines
    print("[3/6] Computing trailing own history (<=8 weeks) and peer baselines...")
    evaluable_df = add_baselines(weekly_df, drop_first_weeks=True)
    evaluable_df["is_candidate"] = is_candidate_mask(evaluable_df)
    print(f"      {len(evaluable_df)} evaluable route-weeks (7 first-weeks dropped).")

    # 4. Candidate detection
    print(f"[4/6] Detecting cost rise candidates (own >= +{FLAG_OWN_PCT}% OR own >= +{FLAG_OWN_SOFT_PCT}% & peer >= +{FLAG_PEER_PCT}%)...")
    candidates_df = detect_candidates(evaluable_df)
    print(f"      Identified {len(candidates_df)} candidate route-weeks.")

    # 5. RAG Retrieval & Deterministic Validation
    print("[5/6] Retrieving context notes (ChromaDB/Embeddings) and running deterministic validator...")
    retriever = NoteRetriever()
    notes_map = get_notes_dict()
    llm_client = LLMClient(provider=provider, enable_cache=enable_cache)

    results_data = []
    formatted_rows = []
    retrieval_records = []

    for _, row in candidates_df.iterrows():
        route = str(row["route"])
        wk_str = pd.to_datetime(row["week_of"]).strftime("%Y-%m-%d")

        # Top-5 retrieval to evaluate corridor near-misses
        hits = retriever.retrieve_for_candidate(route, wk_str, k=5)
        candidate_notes = [notes_map[nid] for nid, _ in hits]

        # Deterministic verdict
        verdict = decide_verdict(row, candidate_notes)
        chosen_note = notes_map[verdict.note_id] if verdict.note_id else None

        # Record retrieval log
        retrieval_records.append({
            "route": route,
            "week_of": wk_str,
            "hits": [
                {
                    "note_id": nid,
                    "score": score,
                    "effect": notes_map[nid].effect,
                    "scope": notes_map[nid].scope
                }
                for nid, score in hits
            ],
            "verdict": "justified" if verdict.justified else "unexplained",
            "matched_note_id": verdict.note_id
        })

        # Build evidence packet & generate explanation
        packet = build_evidence_packet(row, verdict, chosen_note, candidate_notes)
        reason_text, usage = explain_candidate(packet, llm_client=llm_client)

        row_payload = {
            "route": route,
            "week_of": wk_str,
            "c": row["c"],
            "vs_own_pct": row["vs_own_pct"],
            "vs_peer_pct": row["vs_peer_pct"],
            "excess_inr": int(row.get("excess_inr", 0)),
            "verdict": packet["verdict"],
            "matched_note_id": verdict.note_id,
            "reason": reason_text,
            "evidence_packet": packet,
            "llm_usage": usage
        }
        results_data.append(row_payload)
        formatted_rows.append(format_output_row(row_payload))

    # Save retrieval log
    retrieval_log_file = OUTPUT_DIR / "retrieval_log.jsonl"
    with open(retrieval_log_file, "w", encoding="utf-8") as f:
        for rec in retrieval_records:
            f.write(json.dumps(rec) + "\n")

    # Compute episode attribution for candidate routes
    from stripewatch.attribution import compute_route_attribution
    attribution_data = compute_route_attribution(shipments_df, candidates_df)

    # 6. Write outputs & contract assertions
    print("[6/6] Writing output artifacts and asserting contract conformity...")
    output_csv = write_contract_csv(formatted_rows)
    weekly_csv = write_weekly_metrics(evaluable_df)
    results_json = write_results_json({"candidates": results_data, "attribution": attribution_data})
    llm_client.save_token_log()

    # Print summary
    justified_count = sum(1 for r in results_data if r["verdict"] == "justified")
    unexplained_count = sum(1 for r in results_data if r["verdict"] == "unexplained")

    print("\n------------------------------------------------------------")
    print(f"PIPELINE COMPLETED SUCCESSFULLY:")
    print(f"  * Total candidate rows:    {len(results_data)}")
    print(f"  * Justified rows:          {justified_count} (3 expected: N001x2, N002x1)")
    print(f"  * Unexplained flagged rows: {unexplained_count} (16 expected)")
    print(f"  * Output CSV:              {output_csv}")
    print(f"  * Weekly Metrics CSV:      {weekly_csv}")
    print(f"  * Results JSON:            {results_json}")
    print(f"  * Token Log JSON:          {OUTPUT_DIR / 'token_log.json'}")
    print(f"  * Retrieval Log JSONL:     {retrieval_log_file}")
    print("------------------------------------------------------------\n")

    return {
        "candidates": len(results_data),
        "justified": justified_count,
        "unexplained": unexplained_count,
        "output_csv": str(output_csv),
        "token_summary": llm_client.get_token_summary()
    }


def main():
    parser = argparse.ArgumentParser(description="StripeWatch Shipping Cost Anomaly Watchdog")
    subparsers = parser.add_subparsers(dest="command")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run the anomaly detection pipeline")
    run_parser.add_argument("--provider", type=str, default=None, help="LLM provider: gemini, groq, none")
    run_parser.add_argument("--no-cache", action="store_true", help="Disable LLM disk caching")
    run_parser.add_argument("--cold-cache", action="store_true", help="Clear cache before running")

    # Eval command
    eval_parser = subparsers.add_parser("eval", help="Run evaluation harness, tests, and generate eval_report.md")
    eval_parser.add_argument("--synthetic", action="store_true", help="Run 60-spike synthetic injection benchmark")

    # Repro command
    subparsers.add_parser("repro", help="Run 3 fresh reproducible executions and generate repro_report.md")

    # Ask command
    ask_parser = subparsers.add_parser("ask", help="Ask plain-English questions about anomalies")
    ask_parser.add_argument("question", type=str, help="Question to ask StripeWatch")

    # Ablation command
    subparsers.add_parser("ablation", help="Compare template vs LLM explanations and write ablation_report.md")

    # Watch command
    watch_parser = subparsers.add_parser("watch", help="Evaluate single Monday route-weeks")
    watch_parser.add_argument("--week", type=str, required=True, help="Monday ISO date (YYYY-MM-DD)")
    watch_parser.add_argument("--explain", action="store_true", help="Use LLM for explanations")

    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Launch web UI and API server")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to listen on")

    args = parser.parse_args()

    if args.command == "run" or args.command is None:
        run_pipeline(
            provider=args.provider if hasattr(args, "provider") else None,
            enable_cache=not getattr(args, "no_cache", False),
            cold_cache=getattr(args, "cold_cache", False)
        )
    elif args.command == "eval":
        from eval.run_eval import run_evaluation
        run_evaluation(run_synthetic=getattr(args, "synthetic", False))
    elif args.command == "repro":
        from stripewatch.repro import run_reproducibility_check
        run_reproducibility_check()
    elif args.command == "ablation":
        from stripewatch.ablation import run_ablation
        run_ablation()
    elif args.command == "watch":
        from stripewatch.watch import watch_week
        findings = watch_week(args.week, explain_with_llm=getattr(args, "explain", False))
        print(json.dumps(findings, indent=2))
    elif args.command == "ask":
        from stripewatch.ask import ask_question
        ans = ask_question(args.question)
        print(ans)
    elif args.command == "serve":
        from stripewatch.server import serve
        serve(port=args.port)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
