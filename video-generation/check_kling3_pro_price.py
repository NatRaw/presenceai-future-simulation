"""
Estimate-only script: Kling 3.0 Pro · Text to video.

This script NEVER submits a generation. It only calls Higgsfield's free
estimate endpoint and prints the expected cost.

Verified against the official docs (docs.higgsfield.ai/docs/models/kling-3/pro-text-to-video):
  - Endpoint ID : kling-video/v3.0/pro/text-to-video
  - Fields      : prompt, duration (3–15), aspect_ratio ("16:9" | "9:16" | "1:1"),
                  sound ("on" | "off", default "on"), cfg_scale, multi_shots, multi_prompt, elements
  - No resolution field. The docs do not state the output resolution; quality is set by the "Pro" tier.
Estimate endpoint pattern (docs/concepts/billing-and-retention):
  POST https://api.higgsfield.ai/estimate/<endpoint id>  →  {"credits": "...", "usd": "..."}
"""

import sys
from pathlib import Path

import requests
from dotenv import dotenv_values

from scene1 import AVOID, PROMPT   # reuse the Scene 1 prompt (importing does not run scene1)

MODEL_ID = "kling-video/v3.0/pro/text-to-video"
ESTIMATE_URL = f"https://api.higgsfield.ai/estimate/{MODEL_ID}"

# Only documented fields. No negative_prompt field exists, so the avoid list goes in the prompt.
PAYLOAD = {
    "prompt": f"{PROMPT} Avoid: {', '.join(AVOID)}.",
    "duration": 5,
    "aspect_ratio": "16:9",
    "sound": "off",
    "multi_shots": False,   # single shot: exactly one 5-second clip
}


def main() -> None:
    env = Path(__file__).resolve().parent / ".env"
    key = (dotenv_values(env).get("HIGGSFIELD_API_KEY") or "").strip()
    if not key or ":" not in key or key == "your-key-id:your-key-secret":
        sys.exit("✗ HIGGSFIELD_API_KEY missing or not in KEY_ID:KEY_SECRET format in video-generation/.env")

    print("Estimate only. No video will be generated.\n")
    print("  Model/endpoint : Kling 3.0 Pro · Text to video")
    print(f"  Endpoint ID    : {MODEL_ID}")
    print(f"  Estimate URL   : POST {ESTIMATE_URL}")
    print("  Quality mode   : Pro tier (no resolution field; docs don't state the output resolution)")
    print(f"  Duration       : {PAYLOAD['duration']} seconds")
    print(f"  Aspect ratio   : {PAYLOAD['aspect_ratio']}")
    print(f"  Audio          : {PAYLOAD['sound']}")
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
