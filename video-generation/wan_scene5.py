"""
PresenceAI · Scene 5: Wan 3.0 (list submitted, case stays uncertain)
====================================================================

Generates ONE 8-second 1080p clip with Wan 3.0 reference-to-video, using the same
reference images and settings as Wan Scene 1, with its own full Scene 5 prompt.
Saved as output_wan/scene5_wan_1080p.mp4, so it can never overwrite Scenes 1–4
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
# 3) the WIDE first frame (0.0 s) of the successful Scene 4 video: the authoritative reference for the
#    physical environment (glass wall, frosted strip, device, decal, projector, teacher, windows).
#    Attempt 1 used the tight END frame of Scene 4 and invented a new room once the camera pulled back.
REFERENCE_IMAGES = BASE_REFERENCES + [Path(__file__).resolve().parent / "references" / "scene4_wan_wide_frame.png"]

BASE_URL = "https://api.higgsfield.ai"
MODEL_ID = "alibaba/wan-3.0/reference-to-video"
GENERATE_URL = f"{BASE_URL}/{MODEL_ID}"
ESTIMATE_URL = f"{BASE_URL}/estimate/{MODEL_ID}"

DURATION = 8   # final scene: submission + slow dolly back + hold need more time
RESOLUTION = "1080p"
MAX_USD = 2.00   # hard cap: refuses above this

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "output_wan"      # separate from the Kling output/ folder
OUTPUT_FILE = OUT_DIR / "scene5_wan_1080p.mp4"
JOB_FILE = OUT_DIR / "scene5_wan_1080p_job.json"

# ── Full Scene 3 prompt (exact text) ────────────────────────────────────────
FULL_PROMPT = """\
A realistic cinematic final shot from the hallway OUTSIDE the same modern Dutch university classroom established in the previous scenes.

The camera looks through the transparent glass wall toward the large PresenceAI projector screen at the front of the classroom.

At the beginning of the shot, the framing is relatively tight on the PresenceAI dashboard. The projector is the main visual focus.

The same unresolved student registration remains visible on the dashboard.

Preserve the PresenceAI prototype status logic:
- green = Present
- yellow = Late
- red = Absent
- grey = Uncertain

Milan's unresolved registration remains primarily GREY, with the small yellow review-needed badge beside it.

The unresolved registration must remain grey for the entire shot. It must NOT become red, absent, present or late.

During the first part of the shot, show the automatic attendance submission completing.

Use a subtle and restrained system animation for the overall attendance list: a soft interface pulse, brief progress movement, followed by a small neutral confirmation symbol or check indicating that the list has successfully been submitted.

The submission confirmation applies to the attendance list as a whole. It must NOT imply that Milan's uncertain registration has been resolved.

Immediately after the submission completes, Milan's grey unresolved row remains visible and unchanged.

After the submission confirmation, the camera begins a slow, smooth cinematic dolly BACKWARD away from the classroom.

The camera remains in the hallway and gradually moves farther away from the glass classroom wall.

As the camera pulls backward, more of the classroom becomes visible through the glass. Students continue their normal lesson activities and the teacher continues normal teaching responsibilities. Nobody reacts dramatically to the system.

The PresenceAI projector becomes progressively smaller in the background as the camera moves farther into the hallway, but Milan's unresolved grey status remains part of the dashboard.

The final composition should show the classroom continuing normally behind the glass while the unresolved PresenceAI case remains inside the system.

End with the camera several meters farther back in the hallway, looking toward the classroom through the glass. Hold the final composition briefly, creating a quiet sense that the system and lesson have moved forward while the uncertainty still exists.

The scene should feel cinematic and slightly tense, but restrained and believable. Do not make it dystopian, threatening or dramatic through alarms. The tension comes from the unresolved case remaining after the automated process has completed.

Use natural daylight, realistic glass reflections, smooth cinematic camera movement, believable depth of field, clean modern Dutch university architecture and subtle near-future technology.

Do not generate readable clocks, countdowns or exact digital times. The exact timing and meaning will be communicated through voice-over.

IMPORTANT:
- camera starts relatively tight on the projector
- attendance submission completes
- use only a small neutral submission confirmation
- Milan remains grey and unresolved
- Milan never becomes red or absent
- after submission, camera slowly pulls backward into the hallway
- camera does not enter the classroom
- classroom continues normally
- projector gradually becomes smaller in the distance
- end on a quiet wide hallway view through the glass
- no new status decision is made

Reference images: the first is the authoritative PresenceAI dashboard for the projector UI, colors and status logic; Milan's row is its top grey row with the small yellow review badge. The second is the Windesheim logo, for environmental branding only: the small decal on the frosted glass beside the door. The third is a still from the previous scene (Scene 4) and is the AUTHORITATIVE VISUAL CONTINUITY REFERENCE for the physical environment: the classroom, hallway, glass wall with its frosted strip, camera height, architecture, lighting, projector placement, teacher and overall cinematic look. Scene 5 must look like the camera is continuing in the exact environment of that still. Do NOT redesign the classroom. Do NOT invent a new hallway. Do NOT change the glass-wall layout. Do NOT move the projector to a different part of the room.

Avoid: Milan becoming absent, red status replacing grey, teacher presenting the dashboard, dramatic alarms, flashing red warnings, giant holograms, cyberpunk aesthetics, dystopian atmosphere, aggressive surveillance imagery, large generated text, generated clocks, chaotic camera movement, warped faces, extra limbs, cartoon or anime style."""


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
    print(f"\n✓ Done! Wan Scene 5 saved to:\n  {OUTPUT_FILE}")


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
    print(" PresenceAI · Scene 5: Wan 3.0 (list submitted, case stays uncertain)")
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

    if not ask_yes_no(f"Generate Wan Scene 5 at {RESOLUTION} (~${usd:.2f})? (y/n)"):
        print("Cancelled. Nothing was submitted or charged.")
        return

    idem = str(uuid.uuid4())
    job = {"scene": 5, "model_id": MODEL_ID, "resolution": RESOLUTION, "idempotency_key": idem,
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
