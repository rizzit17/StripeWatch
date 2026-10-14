"""Data loading and schema validation module."""
from pathlib import Path
import pandas as pd
from stripewatch.config import SHIPMENTS_FILE, NOTES_FILE

REQUIRED_SHIPMENT_COLS = [
    "shipment_id", "origin", "destination", "route_type", "material",
    "quantity_tonnes", "distance_km", "freight_cost_inr", "shipment_date", "transporter"
]

REQUIRED_NOTE_COLS = [
    "note_id", "date", "applies_to", "note"
]


def load_shipments(path: Path | str | None = None) -> pd.DataFrame:
    """Load, validate, and parse shipment_records.csv.

    Raises:
        ValueError: If columns are missing, nulls exist, duplicates exist, or numbers are invalid.
    """
    file_path = Path(path) if path else SHIPMENTS_FILE
    if not file_path.exists():
        raise FileNotFoundError(f"Shipments file not found at: {file_path}")

    df = pd.read_csv(file_path)

    # 1. Column assertion
    missing = [c for c in REQUIRED_SHIPMENT_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Shipments file missing required columns: {missing}")

    # 2. Null check
    null_counts = df[REQUIRED_SHIPMENT_COLS].isnull().sum()
    if null_counts.any():
        raise ValueError(f"Found null values in shipments: {null_counts[null_counts > 0].to_dict()}")

    # 3. Duplicate check
    dups = df["shipment_id"].duplicated().sum()
    if dups > 0:
        raise ValueError(f"Found {dups} duplicate shipment_id entries")

    # 4. Positive numbers check
    for col in ["quantity_tonnes", "distance_km", "freight_cost_inr"]:
        if (df[col] <= 0).any():
            raise ValueError(f"Found non-positive values in column: {col}")

    # 5. Route consistency: exactly one route_type per (origin, destination)
    df["route"] = df["origin"].str.strip() + "-" + df["destination"].str.strip()
    types_per_route = df.groupby("route")["route_type"].nunique()
    if (types_per_route > 1).any():
        inconsistent = types_per_route[types_per_route > 1].index.tolist()
        raise ValueError(f"Routes with multiple route_types: {inconsistent}")

    # 6. Parse date
    df["shipment_date"] = pd.to_datetime(df["shipment_date"])

    return df


def load_notes(path: Path | str | None = None) -> pd.DataFrame:
    """Load and validate context_notes.csv."""
    file_path = Path(path) if path else NOTES_FILE
    if not file_path.exists():
        raise FileNotFoundError(f"Notes file not found at: {file_path}")

    df = pd.read_csv(file_path)

    missing = [c for c in REQUIRED_NOTE_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Notes file missing required columns: {missing}")

    if df[REQUIRED_NOTE_COLS].isnull().any().any():
        raise ValueError("Found null values in context_notes.csv")

    return df
