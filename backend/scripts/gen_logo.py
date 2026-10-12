"""One-off logo helper.

This file intentionally avoids any Emergent-specific integrations and uses the
standard Gemini API configuration already used by the app."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
OUT = Path("/app/frontend/public/logo.png")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is not configured")

print("Gemini logo generation is configured via the standard app API key.")
print(f"Key present: {bool(API_KEY)}")
print(f"Output target: {OUT}")
