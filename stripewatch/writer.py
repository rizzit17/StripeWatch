"""Output generation and contract assertion module."""
from pathlib import Path
import csv
import json
import pandas as pd
from typing import List, Dict, Any

from stripewatch.config import OUTPUT_DIR, SAMPLE_OUTPUT_FILE


CONTRACT_COLUMNS = [
    "route",
    "week_of",
    "cost_per_tonne_km",
    "vs_own_history",
    "vs_similar_routes",
    "flagged",
    "matched_note_id",
    "reason"
]


def format_output_row(row_data: Dict[str, Any]) -> Dict[str, Any]:
    """Format row fields strictly according to sample_output_format_v2 contract."""
    c_val = float(row_data["c"])
    vo_val = float(row_data["vs_own_pct"])
    vp_val = float(row_data["vs_peer_pct"]) if pd.notnull(row_data.get("vs_peer_pct")) else 0.0

    is_justified = (row_data["verdict"] == "justified")
    flagged_str = "No (justified)" if is_justified else "Yes"
    matched_id = str(row_data["matched_note_id"]) if (is_justified and row_data.get("matched_note_id")) else ""

    return {
        "route": str(row_data["route"]).strip(),
        "week_of": str(row_data["week_of"]).strip(),
        "cost_per_tonne_km": f"{c_val:.2f}",
        "vs_own_history": f"{vo_val:+.1f}% vs this route's past average",
        "vs_similar_routes": f"{vp_val:+.1f}% vs similar-length routes this week",
        "flagged": flagged_str,
        "matched_note_id": matched_id,
        "reason": str(row_data["reason"]).strip()
    }


def write_contract_csv(
    formatted_rows: List[Dict[str, Any]],
    output_path: Path | str | None = None
) -> Path:
    """Write output/output.csv and strictly assert contract conformity against sample_output_format_v2.csv."""
    dest = Path(output_path) if output_path else (OUTPUT_DIR / "output.csv")
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Sort rows stably by week_of, then route
    sorted_rows = sorted(formatted_rows, key=lambda r: (r["week_of"], r["route"]))

    df = pd.DataFrame(sorted_rows, columns=CONTRACT_COLUMNS)
    # Write with standard quoting (quotes fields containing commas or quotes)
    df.to_csv(dest, index=False, columns=CONTRACT_COLUMNS, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)

    # STRICT ASSERTIONS
    assert_contract_conformity(dest)
    return dest


def assert_contract_conformity(csv_path: Path):
    """Verify headers, column count, and value invariants against sample_output_format_v2.csv."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Output CSV not found at {csv_path}")

    with open(SAMPLE_OUTPUT_FILE, "r", encoding="utf-8") as f:
        sample_header = f.readline().strip().split(",")

    with open(csv_path, "r", encoding="utf-8") as f:
        output_header = f.readline().strip().split(",")

    if output_header != sample_header:
        raise AssertionError(
            f"Output header does not match contract header!\n"
            f"Expected: {sample_header}\n"
            f"Actual:   {output_header}"
        )

    # Check rows
    df = pd.read_csv(csv_path, dtype={"matched_note_id": str}).fillna({"matched_note_id": ""})

    for idx, row in df.iterrows():
        flagged = row["flagged"]
        nid = str(row["matched_note_id"]).strip()

        if flagged not in ["Yes", "No (justified)"]:
            raise AssertionError(f"Row {idx}: Invalid flagged value '{flagged}'. Must be 'Yes' or 'No (justified)'")

        if flagged == "No (justified)":
            if not nid or nid in ["None", "nan", "N/A"]:
                raise AssertionError(f"Row {idx}: Justified row has missing/invalid note id: '{nid}'")
        else:
            if nid != "":
                raise AssertionError(f"Row {idx}: Unexplained row must have empty matched_note_id, got: '{nid}'")


def write_weekly_metrics(df_evaluable: pd.DataFrame, output_path: Path | str | None = None) -> Path:
    """Write supplementary output/weekly_metrics.csv containing all 721 evaluable route-weeks."""
    dest = Path(output_path) if output_path else (OUTPUT_DIR / "weekly_metrics.csv")
    dest.parent.mkdir(parents=True, exist_ok=True)

    out_df = df_evaluable.copy().sort_values(["week_of", "route"])
    out_df["cost_per_tonne_km"] = out_df["c"].round(4)
    out_df["vs_own_pct"] = out_df["vs_own_pct"].round(2)
    out_df["vs_peer_pct"] = out_df["vs_peer_pct"].round(2)

    out_df.to_csv(dest, index=False, lineterminator="\n")
    return dest


def write_results_json(results_data: List[Dict[str, Any]], output_path: Path | str | None = None) -> Path:
    """Write structured output/results.json."""
    dest = Path(output_path) if output_path else (OUTPUT_DIR / "results.json")
    dest.parent.mkdir(parents=True, exist_ok=True)

    with open(dest, "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2)
    return dest
