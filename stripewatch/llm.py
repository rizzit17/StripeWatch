"""LLM client adapter with disk caching, token tracking, and deterministic zero-temperature calls."""
import hashlib
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from stripewatch.config import (
    CACHE_DIR,
    OUTPUT_DIR,
    LLM_PROVIDER,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
    TEMPERATURE,
)

logger = logging.getLogger(__name__)

# Published rates for cost estimation (Gemini 3.1 Flash Lite / Flash pricing)
RATES = {
    "gemini": {
        "rate_in": 0.075,   # $ per 1M tokens
        "rate_out": 0.30,   # $ per 1M tokens
        "note": "Google Gemini free tier ($0 actual spend); published pay-as-you-go rate shown for reference"
    },
    "groq": {
        "rate_in": 0.59,
        "rate_out": 0.79,
        "note": "Groq free tier ($0 actual spend)"
    },
    "none": {
        "rate_in": 0.0,
        "rate_out": 0.0,
        "note": "Deterministic template mode (0 LLM calls, $0 spend)"
    }
}


class LLMClient:
    """Manages LLM inference with SHA-256 disk caching and token tracking."""

    def __init__(self, provider: Optional[str] = None, enable_cache: bool = True):
        self.provider = (provider or LLM_PROVIDER or "none").lower()
        self.enable_cache = enable_cache
        self.run_id = f"run_{int(time.time())}_{uuid.uuid4().hex[:6]}"

        self.cache_file = CACHE_DIR / "llm_cache.json"
        self._cache: Dict[str, Any] = {}
        if self.enable_cache:
            self._load_cache()

        self.calls_count = 0
        self.cache_hits = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.grounding_rejections = 0
        self.per_call_log: list[dict] = []

        self._init_provider()

    def _load_cache(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load cache: {e}")
                self._cache = {}

    def _save_cache(self):
        if not self.enable_cache:
            return
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save cache: {e}")

    def _init_provider(self):
        self.client = None
        if self.provider == "gemini":
            if not GEMINI_API_KEY:
                logger.warning("GEMINI_API_KEY not found in environment; falling back to none provider")
                self.provider = "none"
                return
            try:
                from google import genai
                self.client = genai.Client(api_key=GEMINI_API_KEY)
                self.model = GEMINI_MODEL
            except Exception as e:
                logger.warning(f"Failed to init Gemini client: {e}. Falling back to none.")
                self.provider = "none"
        elif self.provider == "groq":
            if not GROQ_API_KEY:
                logger.warning("GROQ_API_KEY not found; falling back to none.")
                self.provider = "none"
                return
            try:
                from groq import Groq
                self.client = Groq(api_key=GROQ_API_KEY)
                self.model = GROQ_MODEL
            except Exception as e:
                logger.warning(f"Failed to init Groq client: {e}. Falling back to none.")
                self.provider = "none"
        else:
            self.provider = "none"
            self.model = "none"

    def generate(
        self,
        prompt: str,
        purpose: str = "explain",
        call_key: str = "",
        max_output_tokens: int = 90
    ) -> Tuple[Optional[str], dict]:
        """Generate text with caching and token usage tracking.

        Returns:
            (generated_text, usage_dict)
            generated_text is None if provider == "none" or API call fails.
        """
        if self.provider == "none":
            usage = {"in": 0, "out": 0, "cached": False, "provider": "none"}
            return None, usage

        # Cache key based on model, temp, max_tokens, and prompt
        cache_key_raw = f"{self.model}|temp_{TEMPERATURE}|max_{max_output_tokens}|{prompt}"
        cache_hash = hashlib.sha256(cache_key_raw.encode("utf-8")).hexdigest()

        if self.enable_cache and cache_hash in self._cache:
            entry = self._cache[cache_hash]
            self.cache_hits += 1
            self.calls_count += 1
            in_t = entry.get("input_tokens", 0)
            out_t = entry.get("output_tokens", 0)
            self.input_tokens += in_t
            self.output_tokens += out_t

            usage = {"in": in_t, "out": out_t, "cached": True, "provider": self.provider}
            self.per_call_log.append({
                "purpose": purpose,
                "key": call_key,
                "in": in_t,
                "out": out_t,
                "cached": True
            })
            return entry.get("text"), usage

        # Fresh call with rate limit pacing and retry
        text = None
        in_tokens = 0
        out_tokens = 0

        max_retries = 3
        for attempt in range(max_retries):
            try:
                if self.provider == "gemini":
                    from google.genai import types
                    response = self.client.models.generate_content(
                        model=self.model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=TEMPERATURE,
                            max_output_tokens=max_output_tokens
                        )
                    )
                    text = response.text.strip() if response.text else None
                    if response.usage_metadata:
                        in_tokens = int(response.usage_metadata.prompt_token_count or 0)
                        out_tokens = int(response.usage_metadata.candidates_token_count or 0)
                    # Respect 15 RPM free tier pacing
                    time.sleep(4.1)
                    break
                elif self.provider == "groq":
                    resp = self.client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=TEMPERATURE,
                        max_tokens=max_output_tokens
                    )
                    text = resp.choices[0].message.content.strip()
                    if resp.usage:
                        in_tokens = resp.usage.prompt_tokens
                        out_tokens = resp.usage.completion_tokens
                    break
            except Exception as e:
                err_str = str(e)
                if attempt < max_retries - 1:
                    sleep_sec = 10.0 if ("429" in err_str or "RESOURCE_EXHAUSTED" in err_str) else 3.0
                    logger.warning(f"LLM call attempt {attempt+1}/{max_retries} failed ({e}). Retrying in {sleep_sec}s...")
                    time.sleep(sleep_sec)
                else:
                    logger.warning(f"LLM call failed after {max_retries} attempts: {e}. Falling back to template.")
                    return None, {"in": 0, "out": 0, "cached": False, "error": err_str}

        self.calls_count += 1
        self.input_tokens += in_tokens
        self.output_tokens += out_tokens

        usage = {"in": in_tokens, "out": out_tokens, "cached": False, "provider": self.provider}
        self.per_call_log.append({
            "purpose": purpose,
            "key": call_key,
            "in": in_tokens,
            "out": out_tokens,
            "cached": False
        })

        if text is not None and self.enable_cache:
            self._cache[cache_hash] = {
                "text": text,
                "input_tokens": in_tokens,
                "output_tokens": out_tokens,
                "timestamp": time.time()
            }
            self._save_cache()

        return text, usage

    def record_grounding_rejection(self):
        """Increment count of LLM explanations rejected by ground.py."""
        self.grounding_rejections += 1

    def get_token_summary(self) -> Dict[str, Any]:
        """Compute comprehensive token and cost log."""
        rate_info = RATES.get(self.provider, RATES["none"])
        rate_in = rate_info["rate_in"]
        rate_out = rate_info["rate_out"]

        cost_usd = (self.input_tokens / 1_000_000.0 * rate_in) + (self.output_tokens / 1_000_000.0 * rate_out)

        return {
            "run_id": self.run_id,
            "provider": self.provider,
            "model": getattr(self, "model", "none"),
            "temperature": TEMPERATURE,
            "llm_calls": self.calls_count,
            "cache_hits": self.cache_hits,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "grounding_rejections": self.grounding_rejections,
            "rate_usd_per_1m_input": rate_in,
            "rate_usd_per_1m_output": rate_out,
            "estimated_cost_usd": round(cost_usd, 6),
            "notional_cost_note": rate_info["note"],
            "per_call": self.per_call_log
        }

    def save_token_log(self, output_path: Optional[Path] = None):
        """Save token log to output/token_log.json."""
        dest = output_path or (OUTPUT_DIR / "token_log.json")
        dest.parent.mkdir(parents=True, exist_ok=True)
        summary = self.get_token_summary()
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        logger.info(f"Token log saved to {dest}")
