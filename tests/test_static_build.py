"""Unit tests for UI-8: Static build generator and artifact integrity."""
import json
import re
from pathlib import Path
from stripewatch.config import BASE_DIR

import pytest
from scripts.build_static import build_static

DIST_DIR = BASE_DIR / "dist"
DIST_DATA_DIR = DIST_DIR / "data"


@pytest.fixture(scope="session", autouse=True)
def ensure_dist_exists():
    """Ensure dist/ exists and is built before testing."""
    if not (DIST_DIR / "index.html").exists() or not (DIST_DATA_DIR / "validate_matrix.json").exists():
        build_static()


def test_dist_artifacts_exist():
    """Verify all required static distribution artifacts and snapshots exist."""
    assert (DIST_DIR / "index.html").exists()
    assert (DIST_DIR / "app.css").exists()
    assert (DIST_DIR / "app.js").exists()

    required_json = [
        "summary.json",
        "rows.json",
        "calendar.json",
        "notes.json",
        "weeks.json",
        "review_default.json",
        "validate_matrix.json",
        "ask_prebaked.json",
        "route_Ahmedabad-Mumbai.json",
        "route_Chennai-Bangalore.json",
        "route_Delhi-Chennai.json",
        "route_Delhi-Jaipur.json",
        "route_Kolkata-Bhubaneswar.json",
        "route_Mumbai-Delhi.json",
        "route_Mumbai-Pune.json"
    ]
    for r in required_json:
        f = DIST_DATA_DIR / r
        assert f.exists(), f"Missing required snapshot {r}"
        assert f.stat().st_size > 0, f"Snapshot {r} is empty"


def test_validate_matrix_compactness_and_structure():
    """Verify compact validation matrix contains why_reasons and check bits for offline validation."""
    matrix_file = DIST_DATA_DIR / "validate_matrix.json"
    assert matrix_file.exists()

    with open(matrix_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "why_reasons" in data
    assert "matrix" in data
    assert len(data["why_reasons"]) > 0

    # Test sample lookup: Ahmedabad-Mumbai festival week (2025-01-20) with N002
    key = "Ahmedabad-Mumbai|2025-01-20|N002"
    assert key in data["matrix"]
    bits, why_idx = data["matrix"][key]
    # Check bit 5 (32: justified) must be 1
    assert (bits & 32) != 0, f"Expected N002 on Ahmedabad-Mumbai 2025-01-20 to be justified, got bits: {bits}"

    # Total size budget check (< 5.0 MB)
    total_bytes = sum(f.stat().st_size for f in DIST_DIR.rglob("*") if f.is_file())
    assert total_bytes < 5.0 * 1024 * 1024, f"dist/ size {total_bytes} exceeds 5MB"


def test_dist_sanitization():
    """Verify dist/ contains zero API keys or local absolute machine paths."""
    forbidden = [
        r"AIza[0-9A-Za-z-_]{35}",
        r"gsk_[0-9A-Za-z]{30,}",
        r"c:/Users/",
        r"/home/",
        r"Users/Rishit"
    ]
    for p in DIST_DIR.rglob("*"):
        if p.is_file():
            try:
                txt = p.read_text(encoding="utf-8")
                for pat in forbidden:
                    assert not re.search(pat, txt, re.IGNORECASE), f"Found forbidden pattern {pat} in {p}"
            except Exception:
                pass
