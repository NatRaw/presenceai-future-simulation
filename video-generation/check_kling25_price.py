"""
Estimate-only script: Kling 2.5 Turbo Pro · Text to video.

This script NEVER submits a generation. It only calls Higgsfield's free
estimate endpoint and prints the expected cost.

Verified against the official docs (docs.higgsfield.ai/docs/models/kling-2-5-turbo/pro-text-to-video):
  - Endpoint ID : kling-video/v2.5-turbo/pro/text-to-video
  - Fields      : prompt (required), duration (5 | 10), cfg_scale (0–1), negative_prompt
  - "This endpoint does not expose a sound or aspect_ratio field."
  - There is also no resolution field, so 1080p and 16:9 cannot be requested.
Estimate endpoint pattern (docs/concepts/billing-and-retention):
  POST https://api.higgsfield.ai/estimate/<endpoint id>  →  {"credits": "...", "usd": "..."}
"""

import sys
from pathlib import Path

import requests
from dotenv import dotenv_values

from scene1 import AVOID, PROMPT   # reuse the Scene 1 prompt (importing does not run scene1)

MODEL_ID = "kling-video/v2.5-turbo/pro/text-to-video"
ESTIMATE_URL = f"https://api.higgsfield.ai/estimate/{MODEL_ID}"

# Only documented fields. This model has a real negative_prompt field.
PAYLOAD = {
    "prompt": PROMPT,
    "negative_prompt": ", ".join(AVOID),
    "duration": 5,
}


def main() -> None:
    env = Path(__file__).resolve().parent / ".env"
    key = (dotenv_values(env).get("HIGGSFIELD_API_KEY") or "").strip()
    if not key or ":" not in key or key == "your-key-id:your-key-secret":
        sys.exit("✗ HIGGSFIELD_API_KEY missing or not in KEY_ID:KEY_SECRET format in video-generation/.env")

    print("Estimate only. No video will be generated.\n")
    print("  Model/endpoint : Kling 2.5 Turbo Pro · Text to video")
    print(f"  Endpoint ID    : {MODEL_ID}")
    print(f"  Estimate URL   : POST {ESTIMATE_URL}")
    print(f"  Duration       : {PAYLOAD['duration']} seconds")
    print("  Resolution     : not configurable (no resolution field on this endpoint)")
    print("  Aspect ratio   : not configurable (no aspect_ratio field on this endpoint)")
    print("  Audio          : not configurable (no sound field on this endpoint)")
    print("  Videos         : 1")

    try:
        resp = requests.post(
            ESTIMATE_URL,
            headers={"Authorization": f"Key {key}", "Content-Type": "application/json"},
            json=PAYLOAD,
            timeout=30,
        )
    except requests.RequestException as e:
        sys.exit(f"\n✗ Could not reach the estimate endpoint ({e.__class__.__name__}).")

    if not resp.ok:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text[:300]
        sys.exit(f"\n✗ Estimate failed: HTTP {resp.status_code}\n  Detail: {detail}")

    data = resp.json()
    if "usd" in data:
        print(f"\n  Estimated USD     : ${data['usd']}")
        print(f"  Estimated credits : {data.get('credits', '?')}")
    elif data.get("type") == "description":
        print("\n  No exact amount returned for this model.")
        print(f"  Pricing (from API): {data.get('pricing_description')}")
    else:
        print(f"\n  Unexpected estimate response: {data}")


if __name__ == "__main__":
    main()
