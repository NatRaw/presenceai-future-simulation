"""
Estimate-only script: Wan 3.0 vs Wan 3.0 Prime · Text to video · 1080p.

This script NEVER submits a generation. It only calls Higgsfield's free
estimate endpoint for each model and prints the expected cost.

Verified against the official docs:
  - docs.higgsfield.ai/docs/models/wan-3/text-to-video        → alibaba/wan-3.0/text-to-video
  - docs.higgsfield.ai/docs/models/wan-3-prime/text-to-video  → alibaba/wan-3.0-prime/text-to-video
  Both accept: prompt (required), duration (2–30), resolution ("480p" | "720p" | "1080p"),
  aspect_ratio ("16:9" | ...), generate_audio (bool, default true), enable_thinking (bool, default false), seed.
Estimate endpoint pattern (docs/concepts/billing-and-retention):
  POST https://api.higgsfield.ai/estimate/<endpoint id>  →  {"credits": "...", "usd": "..."}
"""

import sys
from pathlib import Path

import requests
from dotenv import dotenv_values

from scene1 import AVOID, PROMPT   # reuse the Scene 1 prompt (importing does not run scene1)

MODELS = [
    ("Wan 3.0 · Text to video", "alibaba/wan-3.0/text-to-video"),
    ("Wan 3.0 Prime · Text to video", "alibaba/wan-3.0-prime/text-to-video"),
]

PAYLOAD = {
    "prompt": f"{PROMPT} Avoid: {', '.join(AVOID)}.",
    "duration": 5,
    "resolution": "1080p",
    "aspect_ratio": "16:9",
    "generate_audio": False,    # audio off
    "enable_thinking": False,   # default; stated explicitly so no premium option is added
}


def estimate(key: str, model_id: str) -> dict | None:
    url = f"https://api.higgsfield.ai/estimate/{model_id}"
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Key {key}", "Content-Type": "application/json"},
            json=PAYLOAD,
            timeout=30,
        )
    except requests.RequestException as e:
        print(f"  ✗ Could not reach the estimate endpoint ({e.__class__.__name__}).")
        return None
    if not resp.ok:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text[:300]
        print(f"  ✗ Estimate failed: HTTP {resp.status_code}. Detail: {detail}")
        return None
    return resp.json()


def main() -> None:
    env = Path(__file__).resolve().parent / ".env"
    key = (dotenv_values(env).get("HIGGSFIELD_API_KEY") or "").strip()
    if not key or ":" not in key or key == "your-key-id:your-key-secret":
        sys.exit("✗ HIGGSFIELD_API_KEY missing or not in KEY_ID:KEY_SECRET format in video-generation/.env")

    print("Estimate only. No video will be generated.\n")
    for name, model_id in MODELS:
        print(f"── {name}")
        print(f"  Endpoint ID    : {model_id}")
        print(f"  Estimate URL   : POST https://api.higgsfield.ai/estimate/{model_id}")
        print(f"  Resolution     : {PAYLOAD['resolution']}")
        print(f"  Duration       : {PAYLOAD['duration']} seconds")
        print(f"  Aspect ratio   : {PAYLOAD['aspect_ratio']}")
        print(f"  Audio          : off")
        print(f"  Videos         : 1")
        data = estimate(key, model_id)
        if data and "usd" in data:
            print(f"  Estimated USD     : ${data['usd']}")
            print(f"  Estimated credits : {data.get('credits', '?')}")
        elif data and data.get("type") == "description":
            # Some models return a pricing description instead of an exact amount.
            print("  Estimated USD     : no exact amount returned for this model")
            print("  Estimated credits : no exact amount returned for this model")
            print(f"  Pricing (from API): {data.get('pricing_description')}")
        elif data:
            print(f"  Unexpected estimate response: {data}")
        print()


if __name__ == "__main__":
    main()
