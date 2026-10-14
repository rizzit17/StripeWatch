#!/usr/bin/env python3
"""Run provider ablation comparison: template vs LLM."""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from stripewatch.ablation import run_ablation

if __name__ == "__main__":
    run_ablation()
