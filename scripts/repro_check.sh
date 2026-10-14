#!/usr/bin/env bash
# StripeWatch Reproducibility Check Script
set -e

echo "Running StripeWatch Reproducibility Verification..."
python -m stripewatch repro
