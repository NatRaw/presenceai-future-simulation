"""
PresenceAI · Scene 7: Wan 3.0 (closing shot: the teacher leaves)
================================================================

Generates ONE 8-second 1080p clip with Wan 3.0 IMAGE-TO-VIDEO. The last frame of the
finished Scene 6 (empty room, teacher with laptop, projector already OFF) is used as the
literal FIRST FRAME, so Scene 7 continues seamlessly from where Scene 6 ended.
No dashboard reference is sent: in attempt 1 (reference mode) it made the projector turn
back on. Saved as output_wan/scene7_wan_1080p.mp4, so it can never overwrite Scenes 1–6.

Verified against the official docs (docs.higgsfield.ai/docs/models/wan-3/image-to-video):
  - Endpoint : POST https://api.higgsfield.ai/alibaba/wan-3.0/image-to-video
  - Fields   : prompt (required), image_url (required, first frame), end_image_url (optional),
               duration (2–30), resolution, aspect_ratio, generate_audio, enable_thinking, seed
  - Image-to-video has no reference arrays (image_urls). The dashboard, logo, teacher and room
    are all already visible in the first frame, so they carry over from there.
  - The projector is OFF in that first frame; no dashboard image is sent, so nothing invites it back on.

Pricing: the estimate endpoint returns a per-second rate description (before discount);
this script reads the live 1080p rate and computes the cost.
"""

import json
import re
import sys
import time
import uuid
from pathlib import Path

import requests

# Reuse ONLY side-effect-free helpers from the Kling script (no file paths, no job handling).
from scene1 import (
    ask_yes_no, describe_error, fail, headers, load_credentials, poll, upload_references,
)

BASE_URL = "https://api.higgsfield.ai"
MODEL_ID = "alibaba/wan-3.0/image-to-video"
GENERATE_URL = f"{BASE_URL}/{MODEL_ID}"
ESTIMATE_URL = f"{BASE_URL}/estimate/{MODEL_ID}"

DURATION = 8       # teacher finishes packing, walks out, brief hold on the empty room
RESOLUTION = "1080p"
MAX_USD = 2.00     # hard cap: refuses above this

HERE = Path(__file__).resolve().parent
FIRST_FRAME = HERE / "references" / "scene6_wan_last_frame.png"   # last frame of finished Scene 6
OUT_DIR = HERE / "output_wan"
OUTPUT_FILE = OUT_DIR / "scene7_wan_1080p.mp4"
JOB_FILE = OUT_DIR / "scene7_wan_1080p_job.json"

# ── Full Scene 7 prompt (exact text) ────────────────────────────────────────
FULL_PROMPT = """\
A realistic cinematic continuation of the exact final moment of Scene 6.

The FIRST FRAME must visually match the final frame of Scene 6 as closely as possible.

The camera remains outside the classroom in the hallway, looking through the same glass wall from the same angle and camera height.

The classroom is already empty except for the teacher, who is finishing packing their laptop, notes and belongings.

The large classroom projector / PresenceAI display is ALREADY OFF at the beginning of the shot, exactly as it was at the end of Scene 6.

The projector must remain completely OFF for the entire scene.
Do not reactivate the display.
Do not show the PresenceAI dashboard.
Do not perform another screen shutdown or dimming animation.

Keep all other room lighting and natural daylight exactly consistent with the final frame of Scene 6.

During the shot, the teacher finishes packing, picks up their belongings, calmly walks toward the existing classroom exit and leaves the room.

The teacher does not interact with the projector, PresenceAI or any switches.

After the teacher exits, the classroom is completely empty.

Hold briefly on the empty classroom at the end.

IMPORTANT:
- exact continuation from Scene 6
- projector starts OFF
- projector stays OFF
- projector never turns on
- no second shutdown animation
- room lighting stays consistent with Scene 6
- teacher only finishes packing and leaves
- classroom ends fully empty
- camera remains outside the glass
- no new story event"""


def build_payload(first_frame_url: str) -> dict:
    return {
        "prompt": FULL_PROMPT,
        "image_url": first_frame_url,   # literal first frame = last frame of Scene 6
        "duration": DURATION,
        "resolution": RESOLUTION,
        "aspect_ratio": "16:9",
        "generate_audio": False,        # audio off
        "enable_thinking": True,        # supported; no price difference in live estimates
    }


def live_cost(key: str, payload: dict) -> float:
    """Call the free estimate endpoint and compute the cost from the live per-second rate."""
    print("\n→ Requesting live pricing (free, no generation)…")
    try:
        resp = requests.post(ESTIMATE_URL, headers=headers(key), json=payload, timeout=30)
    except requests.RequestException as e:
        fail(f"Could not reach the estimate endpoint ({e.__class__.__name__}). Nothing was charged.")
    if not resp.ok:
        fail("Estimate failed, so nothing was submitted.\n  " + describe_error(resp))
    data = resp.json()

    if "usd" in data:   # in case Higgsfield starts returning exact amounts
        print(f"  Exact estimate: ${data['usd']} ({data.get('credits', '?')} credits)")
        return float(data["usd"])

    text = data.get("pricing_description", "")
    print(f"  Higgsfield says: {text}")
    m = re.search(RESOLUTION + r" \$([\d.]+)", text)   # matches "1080p $0.20" and "1080p $0.20/s"
    if not m:
        fail(f"Could not read the {RESOLUTION} rate from the estimate. Nothing was submitted.")
    return float(m.group(1).rstrip(".")) * DURATION


def save(job: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    JOB_FILE.write_text(json.dumps(job, indent=2))


def download(url: str) -> None:
    print("\n→ Downloading MP4…")
    tmp = OUTPUT_FILE.with_suffix(".mp4.part")
    try:
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
    except requests.RequestException as e:
        tmp.unlink(missing_ok=True)
        fail(f"Download failed ({e.__class__.__name__}). Run the script again to retry (no new generation).")
    tmp.replace(OUTPUT_FILE)


def finish(key: str, job: dict) -> None:
    result = poll(key, job["status_url"])
    job["status"] = result.get("status")
    save(job)
    if job["status"] != "completed":
        fail(f"Job ended with status '{job['status']}'. {result.get('error', '')}\n"
             f"  Not retrying automatically. Failed/NSFW jobs are not charged.")
    url = (result.get("video") or {}).get("url")
    if not url:
        fail(f"Job completed but no video URL was found: {result}")
    job["video_url"] = url
    save(job)
    download(url)
    print(f"\n✓ Done! Wan Scene 7 saved to:\n  {OUTPUT_FILE}")


def main() -> None:
    key = load_credentials()

    if OUTPUT_FILE.exists():
        print(f"✓ {OUTPUT_FILE.name} already exists. Nothing to do.\n  {OUTPUT_FILE}")
        return

    # Existing job: resume it, never create a new one.
    if JOB_FILE.exists():
        job = json.loads(JOB_FILE.read_text())
        if job.get("request_id"):
            print(f"→ Found existing job {job['request_id']}. Resuming the SAME job (no new charge).")
            finish(key, job)
            return
        fail(f"{JOB_FILE.name} has no job ID (the submission may have been interrupted).\n"
             f"  Check your Higgsfield dashboard before deleting it and trying again.")

    if not FIRST_FRAME.exists():
        fail(f"First-frame image not found: {FIRST_FRAME}")

    print("=" * 64)
    print(" PresenceAI · Scene 7: Wan 3.0 (closing shot: the teacher leaves)")
    print("=" * 64)
    print(f"  Model         : Wan 3.0 · Image to video")
    print(f"  Model ID      : {MODEL_ID}")
    print(f"  First frame   : references/{FIRST_FRAME.name} (last frame of Scene 6, projector OFF)")
    print(f"  Resolution    : {RESOLUTION}")
    print(f"  Duration      : {DURATION} seconds")
    print(f"  Aspect ratio  : 16:9")
    print(f"  Audio         : off")
    print(f"  Thinking      : on (no price difference in live estimates)")
    print(f"  Videos        : exactly 1")
    print(f"  Prompt length : {len(FULL_PROMPT)} characters")
    print(f"  Output file   : {OUTPUT_FILE}")
    print(f"  Spending cap  : ${MAX_USD:.2f}")

    first_frame_url = upload_references(key, [FIRST_FRAME])[0]
    payload = build_payload(first_frame_url)
    usd = live_cost(key, payload)
    print(f"\n  Cost for {DURATION} s at {RESOLUTION}: ~${usd:.2f} (before any discount)")

    if usd > MAX_USD:
        fail(f"~${usd:.2f} is above the spending cap of ${MAX_USD:.2f}. Nothing was submitted.")

    if not ask_yes_no(f"Generate Wan Scene 7 at {RESOLUTION} (~${usd:.2f})? (y/n)"):
        print("Cancelled. Nothing was submitted or charged.")
        return

    idem = str(uuid.uuid4())
    job = {"scene": 7, "model_id": MODEL_ID, "resolution": RESOLUTION, "idempotency_key": idem,
           "image_url": first_frame_url, "approx_usd_before_discount": round(usd, 3),
           "created": time.strftime("%Y-%m-%d %H:%M:%S")}
    save(job)   # stored BEFORE sending

    print("\n→ Submitting generation (one job)…")
    try:
        resp = requests.post(GENERATE_URL, headers=headers(key, idem), json=payload, timeout=60)
    except requests.RequestException as e:
        fail(f"Network problem during submission ({e.__class__.__name__}). It is unclear whether the job\n"
             f"  was accepted. Check your Higgsfield dashboard. The script will NOT resubmit automatically.")
    if not resp.ok:
        if resp.status_code < 500:
            JOB_FILE.unlink(missing_ok=True)   # rejected before acceptance: nothing created
        fail("Generation request failed.\n  " + describe_error(resp))

    data = resp.json()
    job.update(request_id=data["request_id"], status_url=data["status_url"], status=data.get("status"))
    save(job)
    print(f"  ✓ Job created. Job ID: {data['request_id']}\n    Saved to {JOB_FILE}")
    finish(key, job)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nStopped. If a job was created, run the script again to resume the SAME job.")
        sys.exit(130)
