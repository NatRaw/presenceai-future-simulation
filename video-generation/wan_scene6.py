"""
PresenceAI · Scene 6: Wan 3.0 (final scene: the lesson ends)
============================================================

Generates ONE 10-second 1080p clip with Wan 3.0 reference-to-video, using the same
reference images and settings as Wan Scene 1, with its own full Scene 6 prompt.
Saved as output_wan/scene6_wan_1080p.mp4, so it can never overwrite Scenes 1–5
or the Kling files.

Verified against the official docs (docs.higgsfield.ai/docs/models/wan-3/reference-to-video):
  - Endpoint : POST https://api.higgsfield.ai/alibaba/wan-3.0/reference-to-video
  - Fields   : prompt (required), image_urls (ordered, max 10), duration (2–30),
               resolution ("480p" | "720p" | "1080p"), aspect_ratio, generate_audio,
               enable_thinking, seed, video_urls, audio_urls, file_url, link_url
  - enable_thinking: live estimates show the same price with it on or off, so it is enabled.

Pricing: for this model the estimate endpoint returns a pricing DESCRIPTION (per-second rates,
before discount). Without input videos only the output duration is billed. This script reads
the live rate and computes the cost for 5 seconds.
"""

import json
import re
import sys
import time
import uuid
from pathlib import Path

import requests

# Reuse ONLY side-effect-free pieces from the Kling script (no file paths, no job handling).
from scene1 import (
    REFERENCE_IMAGES as BASE_REFERENCES, ask_yes_no, describe_error, fail, headers,
    load_credentials, poll, upload_references,
)

# Ordered references: 1) PresenceAI dashboard, 2) Windesheim logo (same as Scene 1),
# 3) the FINAL frame of the successful Scene 5 video: authoritative continuity reference for the
#    classroom layout, hallway angle, glass wall, projector position, lighting and camera framing.
REFERENCE_IMAGES = BASE_REFERENCES + [Path(__file__).resolve().parent / "references" / "scene5_wan_last_frame.png"]

BASE_URL = "https://api.higgsfield.ai"
MODEL_ID = "alibaba/wan-3.0/reference-to-video"
GENERATE_URL = f"{BASE_URL}/{MODEL_ID}"
ESTIMATE_URL = f"{BASE_URL}/estimate/{MODEL_ID}"

DURATION = 10   # students leave, room empties, teacher packs, projector dims: needs time
RESOLUTION = "1080p"
MAX_USD = 2.00   # hard cap: refuses above this

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "output_wan"      # separate from the Kling output/ folder
OUTPUT_FILE = OUT_DIR / "scene6_wan_1080p.mp4"
JOB_FILE = OUT_DIR / "scene6_wan_1080p_job.json"

# ── Full Scene 3 prompt (exact text) ────────────────────────────────────────
FULL_PROMPT = """\
A realistic cinematic continuation of the exact final moment of the previous scene.

The FIRST FRAME should visually match the final frame of Scene 5 as closely as possible. Use the final frame from Scene 5 as the authoritative continuity reference for the hallway, glass classroom wall, classroom layout, projector position, lighting, camera height and overall composition.

The camera remains OUTSIDE the classroom in the hallway, looking through the glass wall into the same classroom.

Do not introduce a new camera angle or a different classroom.

The attendance list has already been automatically submitted. The lesson is now ending.

At the beginning of the shot, students begin calmly packing their belongings and leaving the classroom through the existing classroom door. Their movement should feel natural and ordinary, like the end of a university lesson.

The teacher remains inside the classroom while the students leave.

The teacher does NOT interact with PresenceAI and does NOT review the uncertain registration. Instead, the teacher calmly packs their own laptop, notes and teaching materials at the desk.

Over the course of the shot, the classroom gradually becomes empty as the students leave.

The PresenceAI dashboard remains visible on the classroom projector during the first part of the shot. The attendance session has already finished and been submitted.

Near the end of the shot, the projector interface gently dims and transitions into a neutral standby or session-ended state, indicating that the classroom attendance session is over.

Do NOT show Milan becoming absent.
Do NOT show the uncertain registration being corrected.
Do NOT imply that the unresolved case has been deleted.
The unresolved case still exists in the administrative workflow; only the classroom display is ending its session.

By the final moment, the classroom is almost completely empty. The teacher has finished packing their materials and turns slightly toward the exit, clearly preparing to leave.

The final feeling should be quiet and reflective: the lesson has ended, the classroom is moving on, but the unresolved attendance case still exists elsewhere in the system.

Use natural evening or late-morning classroom light consistent with the previous shot, realistic glass reflections, smooth natural student movement, believable body language and polished cinematic realism.

IMPORTANT:
- start from the exact visual composition where Scene 5 ended
- camera stays outside in the hallway
- do not reset or redesign the classroom
- students leave naturally
- teacher stays behind and packs laptop and materials
- teacher does not interact with PresenceAI
- classroom gradually becomes empty
- PresenceAI projector gently transitions to neutral standby at the end
- teacher prepares to leave in the final moment
- no dramatic alarms or system errors
- no status changes
- no new storyline

Reference images: the first is the authoritative PresenceAI dashboard for the projector UI and status logic; Milan's row is its top grey row with the small yellow review badge. The second is the Windesheim logo, for subtle environmental branding only: the small decal on the frosted glass beside the door. The third is the final frame of the successful Scene 5 and is the AUTHORITATIVE CONTINUITY REFERENCE for the classroom layout, hallway angle, glass wall, projector position, lighting and camera framing: the shot must start from exactly that composition. This third reference is the MOST IMPORTANT reference: prioritize continuity with that frame over inventing a new composition, and keep its classroom, hallway, glass wall, projector, teacher and camera framing unchanged.

Avoid: new classroom layout, camera entering the classroom, teacher reviewing Milan, Milan becoming absent, teacher pointing at the dashboard, dramatic shutdown effects, flashing warnings, cyberpunk aesthetics, giant holograms, chaotic movement, distorted people, cartoon or anime style."""


def build_payload(image_urls: list[str]) -> dict:
    return {
        "prompt": FULL_PROMPT,
        "image_urls": image_urls,
        "duration": DURATION,
        "resolution": RESOLUTION,
        "aspect_ratio": "16:9",
        "generate_audio": False,   # audio off
        "enable_thinking": True,   # supported; no price difference in live estimates
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
    m = re.search(RESOLUTION + r" \$([\d.]+)/s", text)
    if not m:
        fail(f"Could not read the {RESOLUTION} rate from the estimate. Nothing was submitted.")
    return float(m.group(1)) * DURATION


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
    print(f"\n✓ Done! Wan Scene 6 saved to:\n  {OUTPUT_FILE}")


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

    print("=" * 64)
    print(" PresenceAI · Scene 6: Wan 3.0 (final scene: the lesson ends)")
    print("=" * 64)
    print(f"  Model         : Wan 3.0 · Reference to video")
    print(f"  Model ID      : {MODEL_ID}")
    print(f"  Resolution    : {RESOLUTION}")
    print(f"  Duration      : {DURATION} seconds")
    print(f"  Aspect ratio  : 16:9")
    print(f"  Audio         : off")
    print(f"  Thinking      : on (no price difference in live estimates)")
    print(f"  Videos        : exactly 1")
    for i, img in enumerate(REFERENCE_IMAGES, 1):
        print(f"  Reference {i}   : references/{img.name}")
    print(f"  Prompt length : {len(FULL_PROMPT)} characters")
    print(f"  Output file   : {OUTPUT_FILE}")
    print(f"  Spending cap  : ${MAX_USD:.2f}")

    image_urls = upload_references(key, REFERENCE_IMAGES)
    payload = build_payload(image_urls)
    usd = live_cost(key, payload)
    print(f"\n  Cost for {DURATION} s at {RESOLUTION}: ~${usd:.2f} (before any discount)")

    if usd > MAX_USD:
        fail(f"~${usd:.2f} is above the spending cap of ${MAX_USD:.2f}. Nothing was submitted.")

    if not ask_yes_no(f"Generate Wan Scene 6 at {RESOLUTION} (~${usd:.2f})? (y/n)"):
        print("Cancelled. Nothing was submitted or charged.")
        return

    idem = str(uuid.uuid4())
    job = {"scene": 6, "model_id": MODEL_ID, "resolution": RESOLUTION, "idempotency_key": idem,
           "image_urls": image_urls, "approx_usd_before_discount": round(usd, 3),
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
