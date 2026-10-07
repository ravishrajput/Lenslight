"""One-off script to generate the Lenslight logo via Gemini Nano Banana.
Run: python backend/scripts/gen_logo.py
Saves PNG to /app/frontend/public/logo.png"""
import asyncio
import base64
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: E402

OUT = Path("/app/frontend/public/logo.png")

PROMPT = (
    "Design a minimalist square app logo for a data-analytics product called 'Lenslight'. "
    "Centered: an iconic abstract camera aperture / iris lens shape with 6 geometric blades, "
    "with a single sharp horizontal light beam cutting through the center from left to right. "
    "Flat vector style, extremely sharp geometric edges, no gradients, no 3D shading. "
    "Pure black (#050505) background. The lens outline is pure white (#FFFFFF) with a single "
    "accent color on the light beam: bright signal orange (#F24E1E). "
    "Technical / brutalist aesthetic, feels like a command-center or terminal product icon. "
    "No text, no letters, no words, logo only, centered with generous padding, 1024x1024 square."
)


async def main():
    api_key = os.environ["EMERGENT_LLM_KEY"]
    chat = LlmChat(
        api_key=api_key,
        session_id="lenslight-logo-v1",
        system_message="You are an expert brand identity designer.",
    ).with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])
    text, images = await chat.send_message_multimodal_response(UserMessage(text=PROMPT))
    print("text:", (text or "")[:120])
    if not images:
        print("No images returned")
        sys.exit(1)
    img = images[0]
    print("mime:", img.get("mime_type"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(base64.b64decode(img["data"]))
    print(f"Saved {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
