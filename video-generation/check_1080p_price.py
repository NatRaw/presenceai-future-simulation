"""
TEMPORARY estimate-only script: Kling 3.0 Turbo · Text to video · 1080p.

This script NEVER submits a generation. It only calls Higgsfield's free
estimate endpoint and prints the expected cost.

Verified against the official docs (docs.higgsfield.ai/docs/models/kling-3/turbo-text-to-video):
  - Endpoint ID : kling-video/v3.0-turbo/text-to-video
  - Fields      : prompt (required), duration (3–15), resolution ("720p" | "1080p"),
                  aspect_ratio ("16:9" | "9:16" | "1:1")
  - No `sound` field: audio cannot be switched off on this endpoint.
Estimate endpoint pattern (docs/concepts/billing-and-retention):
  POST https://api.higgsfield.ai/estimate/<endpoint id>  →  {"credits": "...", "usd": "..."}
"""

import sys
from pathlib import Path

import requests
from dotenv import dotenv_values

from scene1 import AVOID, PROMPT   # reuse the Scene 1 prompt (importing does not run scene1)

MODEL_ID = "kling-video/v3.0-turbo/text-to-video"
ESTIMATE_URL = f"https://api.higgsfield.ai/estimate/{MODEL_ID}"

PAYLOAD = {
    "prompt": f"{PROMPT} Avoid: {', '.join(AVOID)}.",
    "duration": 5,
    "resolution": "1080p",
    "aspect_ratio": "16:9",
    # no "sound" field: not supported by this endpoint
}


def main() -> None:
    env = Path(__file__).resolve().parent / ".env"
    key = (dotenv_values(env).get("HIGGSFIELD_API_KEY") or "").strip()
    if not key or ":" not in key or key == "your-key-id:your-key-secret":
        sys.exit("✗ HIGGSFIELD_API_KEY missing or not in KEY_ID:KEY_SECRET format in video-generation/.env")

    print("Estimate only. No video will be generated.\n")
    print(f"  Model/endpoint : Kling 3.0 Turbo · Text to video")
    print(f"  Endpoint ID    : {MODEL_ID}")
    print(f"  Estimate URL   : POST {ESTIMATE_URL}")
    print(f"  Resolution     : {PAYLOAD['resolution']}")
    print(f"  Duration       : {PAYLOAD['duration']} seconds")
    print(f"  Aspect ratio   : {PAYLOAD['aspect_ratio']}")
    print(f"  Audio          : not configurable (endpoint has no sound field)")
    print(f"  Videos         : 1")

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
    print(f"\n  Estimated USD     : ${data.get('usd', '?')}")
    print(f"  Estimated credits : {data.get('credits', '?')}")


if __name__ == "__main__":
    main()
