"""Central configuration and constants for StripeWatch."""
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
EVAL_DIR = BASE_DIR / "eval"
DOCS_DIR = BASE_DIR / "docs"

# Data file paths
SHIPMENTS_FILE = DATA_DIR / "shipment_records.csv"
NOTES_FILE = DATA_DIR / "context_notes.csv"
SAMPLE_OUTPUT_FILE = DATA_DIR / "sample_output_format_v2.csv"
NOTES_STRUCTURED_FILE = DATA_DIR / "notes_structured.json"

# Candidate detection thresholds (context.md §6, systemdesign.md §3)
FLAG_OWN_PCT = 8.0          # Strong own-history rise (e.g. +8%)
FLAG_OWN_SOFT_PCT = 5.0     # Mild own-history rise (e.g. +5%)
FLAG_PEER_PCT = 20.0        # Peer outlier threshold (e.g. +20% above peers)
MAG_TOL_PP = 3.0            # Tolerance in percentage points for magnitude check (systemdesign.md §7)

# Rolling window for own history
PRIOR_WEEKS_LIMIT = 8

# LLM & Embedding configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Recommended models
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
TEMPERATURE = 0.0

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
CHROMA_DIR = BASE_DIR / ".chroma"
CACHE_DIR = BASE_DIR / ".cache"
