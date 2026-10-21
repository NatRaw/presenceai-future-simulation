"""
PresenceAI · Scene 1: SEPARATE Seedance 2.5 test
================================================

Generates ONE 5-second clip with Seedance 2.5 reference-to-video, using the same
reference images and the exact same final prompt as the Kling Scene 1 (imported
from scene1.py). Everything is saved in output_seedance/, so it can never
overwrite the Kling files in output/.

Verified against the official docs (docs.higgsfield.ai/docs/models/seedance-2-5/reference-to-video):
  - Endpoint : POST https://api.higgsfield.ai/bytedance/seedance-2.5/reference-to-video
  - Fields   : prompt, image_urls (ordered), duration (4–30), resolution ("480p" | "720p" | "1080p"),
               aspect_ratio, bitrate_mode, generate_audio, video_urls, audio_urls
  - No draft / finalize option exists in the Higgsfield docs. The cheapest "draft" is a full
    generation at 480p. A 1080p version is a SEPARATE new generation, not an upgrade of the draft.

Pricing: for this model the estimate endpoint returns a pricing DESCRIPTION (per-second rates,
before discount) instead of an exact amount. This script reads those live rates and computes
the cost for 5 seconds. Rates are before discount, so the real charge should be equal or lower.

Usage:
  python seedance_scene1.py                      # 480p draft (default, cheapest)
  python seedance_scene1.py --resolution 1080p   # separate full 1080p generation
"""

import argparse
import json
import re
import sys
import time
import uuid
from pathlib import Path

import requests

# Reuse ONLY side-effect-free pieces from the Kling script (no file paths, no job handling).
from scene1 import (
    FULL_PROMPT, REFERENCE_IMAGES, ask_yes_no, describe_error, fail, headers,
    load_credentials, poll, upload_references,
)

BASE_URL = "https://api.higgsfield.ai"
MODEL_ID = "bytedance/seedance-2.5/reference-to-video"
GENERATE_URL = f"{BASE_URL}/{MODEL_ID}"
ESTIMATE_URL = f"{BASE_URL}/estimate/{MODEL_ID}"

DURATION = 5
MAX_USD = 2.00   # hard cap: refuses above this (a 1080p run needs a deliberate raise)

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "output_seedance"   # separate from the Kling output/ folder


def paths(resolution: str) -> tuple[Path, Path]:
    return (OUT_DIR / f"scene1_seedance_{resolution}.mp4",
            OUT_DIR / f"scene1_seedance_{resolution}_job.json")


def build_payload(image_urls: list[str], resolution: str) -> dict:
    return {
        "prompt": FULL_PROMPT,
        "image_urls": image_urls,
        "duration": DURATION,
        "resolution": resolution,
        "aspect_ratio": "16:9",
        "generate_audio": False,   # sound off
    }


def live_rates(key: str, payload: dict) -> dict[str, float]:
    """Call the free estimate endpoint and read the live per-second rates per resolution."""
    print("\n→ Requesting live pricing (free, no generation)…")
    try:
        resp = requests.post(ESTIMATE_URL, headers=headers(key), json=payload, timeout=30)
    except requests.RequestException as e:
        fail(f"Could not reach the estimate endpoint ({e.__class__.__name__}). Nothing was charged.")
    if not resp.ok:
        fail("Estimate failed, so nothing was submitted.\n  " + describe_error(resp))
    data = resp.json()

    if "usd" in data:   # in case Higgsfield starts returning exact amounts
        return {payload["resolution"]: float(data["usd"]) / DURATION}

    text = data.get("pricing_description", "")
    print(f"  Higgsfield says: {text.split('. Each')[0]}.")
    rates = {}
    for res in ("480p", "720p", "1080p"):
        m = re.search(r"\$([\d.]+)(?: per second of generated video)? at " + res, text)
        if m:
            rates[res] = float(m.group(1))
    if payload["resolution"] not in rates:
        fail(f"Could not read a price for {payload['resolution']} from the estimate. Nothing was submitted.")
    return rates


def save(job_file: Path, job: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    job_file.write_text(json.dumps(job, indent=2))


def download(url: str, out_file: Path) -> None:
    print("\n→ Downloading MP4…")
    tmp = out_file.with_suffix(".mp4.part")
    try:
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
    except requests.RequestException as e:
        tmp.unlink(missing_ok=True)
        fail(f"Download failed ({e.__class__.__name__}). Run the script again to retry (no new generation).")
    tmp.replace(out_file)


def finish(key: str, job: dict, job_file: Path, out_file: Path) -> None:
    result = poll(key, job["status_url"])
    job["status"] = result.get("status")
    save(job_file, job)
    if job["status"] != "completed":
        fail(f"Job ended with status '{job['status']}'. {result.get('error', '')}\n"
             f"  Not retrying automatically. Failed/NSFW jobs are not charged.")
    url = (result.get("video") or {}).get("url")
    if not url:
        fail(f"Job completed but no video URL was found: {result}")
    job["video_url"] = url
    save(job_file, job)
    download(url, out_file)
    print(f"\n✓ Done! Seedance Scene 1 saved to:\n  {out_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Separate Seedance 2.5 Scene 1 test")
    parser.add_argument("--resolution", choices=["480p", "720p", "1080p"], default="480p")
    resolution = parser.parse_args().resolution
    out_file, job_file = paths(resolution)
    key = load_credentials()

    if out_file.exists():
        print(f"✓ {out_file.name} already exists. Nothing to do.\n  {out_file}")
        return

    # Existing job for this resolution: resume it, never create a new one.
    if job_file.exists():
        job = json.loads(job_file.read_text())
        if job.get("request_id"):
            print(f"→ Found existing job {job['request_id']}. Resuming the SAME job (no new charge).")
            finish(key, job, job_file, out_file)
            return
        fail(f"{job_file.name} has no job ID (the submission may have been interrupted).\n"
             f"  Check your Higgsfield dashboard before deleting it and trying again.")

    print("=" * 64)
    print(" PresenceAI · Scene 1: SEPARATE Seedance 2.5 test")
    print("=" * 64)
    print(f"  Model         : Seedance 2.5 · Reference to video")
    print(f"  Model ID      : {MODEL_ID}")
    print(f"  Resolution    : {resolution}{'  (draft = cheapest tier; no official draft mode exists)' if resolution == '480p' else ''}")
    print(f"  Duration      : {DURATION} seconds")
    print(f"  Aspect ratio  : 16:9")
    print(f"  Audio         : off")
    print(f"  Videos        : exactly 1")
    for i, img in enumerate(REFERENCE_IMAGES, 1):
        print(f"  Reference {i}   : references/{img.name}")
    print(f"  Prompt        : same final prompt as Kling scene1.py ({len(FULL_PROMPT)} chars)")
    print(f"  Output file   : {out_file}")
    print(f"  Spending cap  : ${MAX_USD:.2f}")

    image_urls = upload_references(key)
    payload = build_payload(image_urls, resolution)
    rates = live_rates(key, payload)

    print("\n  Cost for 5 seconds (live rates, BEFORE any discount):")
    for res, rate in rates.items():
        marker = "  ← this run" if res == resolution else ""
        note = "  (= separate full generation)" if res == "1080p" and resolution != "1080p" else ""
        print(f"    {res:>5}: ~${rate * DURATION:.2f}{marker}{note}")
    usd = rates[resolution] * DURATION

    if usd > MAX_USD:
        fail(f"~${usd:.2f} is above the spending cap of ${MAX_USD:.2f}. Nothing was submitted.\n"
             f"  Raise MAX_USD in seedance_scene1.py only if you deliberately want this.")

    if not ask_yes_no(f"Generate Seedance Scene 1 at {resolution} (~${usd:.2f})? (y/n)"):
        print("Cancelled. Nothing was submitted or charged.")
        return

    idem = str(uuid.uuid4())
    job = {"scene": 1, "model_id": MODEL_ID, "resolution": resolution, "idempotency_key": idem,
           "image_urls": image_urls, "approx_usd_before_discount": round(usd, 3),
           "created": time.strftime("%Y-%m-%d %H:%M:%S")}
    save(job_file, job)   # stored BEFORE sending

    print("\n→ Submitting generation (one job)…")
    try:
        resp = requests.post(GENERATE_URL, headers=headers(key, idem), json=payload, timeout=60)
    except requests.RequestException as e:
        fail(f"Network problem during submission ({e.__class__.__name__}). It is unclear whether the job\n"
             f"  was accepted. Check your Higgsfield dashboard. The script will NOT resubmit automatically.")
    if not resp.ok:
        if resp.status_code < 500:
            job_file.unlink(missing_ok=True)   # rejected before acceptance: nothing created
        fail("Generation request failed.\n  " + describe_error(resp))

    data = resp.json()
    job.update(request_id=data["request_id"], status_url=data["status_url"], status=data.get("status"))
    save(job_file, job)
    print(f"  ✓ Job created. Job ID: {data['request_id']}\n    Saved to {job_file}")
    finish(key, job, job_file, out_file)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nStopped. If a job was created, run the script again to resume the SAME job.")
        sys.exit(130)
