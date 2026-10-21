"""
PresenceAI · Scene 3: Wan 3.0 (the system starts to struggle)
=============================================================

Generates ONE 5-second 1080p clip with Wan 3.0 reference-to-video, using the same
reference images and settings as Wan Scene 1, with its own full Scene 3 prompt.
Saved as output_wan/scene3_wan_1080p.mp4, so it can never overwrite Scenes 1–2
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
# 3) a still frame from the finished Wan Scene 1 video, so Scene 3 matches its set and style.
REFERENCE_IMAGES = BASE_REFERENCES + [Path(__file__).resolve().parent / "references" / "scene1_wan_frame.png"]

BASE_URL = "https://api.higgsfield.ai"
MODEL_ID = "alibaba/wan-3.0/reference-to-video"
GENERATE_URL = f"{BASE_URL}/{MODEL_ID}"
ESTIMATE_URL = f"{BASE_URL}/estimate/{MODEL_ID}"

DURATION = 5
RESOLUTION = "1080p"
MAX_USD = 2.00   # hard cap: refuses above this

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "output_wan"      # separate from the Kling output/ folder
OUTPUT_FILE = OUT_DIR / "scene3_wan_1080p.mp4"
JOB_FILE = OUT_DIR / "scene3_wan_1080p_job.json"

# ── Full Scene 3 prompt (exact text) ────────────────────────────────────────
FULL_PROMPT = """\
A realistic cinematic medium-wide shot INSIDE the same modern Dutch university classroom established in the previous scenes. The lesson is already underway. Students are seated at desks and working normally.

The MAIN ACTION of this scene is the teacher personally helping ONE seated student at their desk.

The teacher is NOT standing at the front of the classroom. The teacher has walked away from the projector and is standing beside one student's desk, leaning slightly toward the seated student and looking DOWN at the student's laptop, notebook or coursework. The teacher points toward the student's work on the desk while quietly helping them.

The teacher's attention must be completely focused on the student and the student's work.

The teacher must NOT look at, point toward, present, explain, touch or interact with the PresenceAI dashboard.

The large classroom projector is visible only in the BACKGROUND of the shot. It still shows the PresenceAI attendance dashboard from the reference image, but it is not the focus of the teacher's attention.

On the PresenceAI dashboard, one registration remains unresolved. Preserve the prototype's visual status logic:
- green = Present
- yellow = Late
- red = Absent
- grey = Uncertain

The uncertain student row should remain primarily GREY, matching the original PresenceAI prototype. A small yellow “review needed” style badge may remain beside it as a secondary attention cue, matching the reference interface. Do not turn the whole uncertain row yellow.

Do not depend on readable generated text. Communicate the unresolved case visually through the grey status pill, grey row treatment and small secondary review indicator.

The purpose of the scene is to visually communicate that human review is available in the system, but the teacher is occupied with a normal teaching responsibility and does not immediately notice or act on the unresolved registration.

Other students remain seated and work naturally. The classroom should feel calm and normal, not chaotic or stressful. This is ordinary classroom pressure, not an emergency.

Use the same realistic near-future 2045 visual language as the previous scenes: modern Dutch university classroom, natural daylight, clean architecture, subtle technology, realistic body language, professional cinematic realism.

Use a polished cinematic visual style with subtle camera movement, soft natural morning light, realistic depth of field, layered foreground and background composition, and smooth natural motion. The PresenceAI screen should remain visible enough for the audience to notice the unresolved grey case, but the human action of the teacher helping the student is the primary visual focus.

IMPORTANT COMPOSITION:
Place the teacher beside a student's desk, away from the projector.
The teacher should be seen from the side or three-quarter angle while leaning toward the student.
Keep the projector several meters behind the teacher in the background.
The teacher's hands should gesture DOWN toward the student's desk or laptop, never upward toward the projector.

The third reference image is a still frame from Scene 1: use it only for continuity of the classroom interior, furniture, projector, the teacher's appearance and clothing, lighting and color grading. Do NOT copy the teacher's position from that frame; in this scene the teacher is beside a student's desk, away from the projector.

Avoid: teacher standing directly in front of the projector, teacher pointing at the PresenceAI screen, teacher presenting PresenceAI, teacher lecturing about the dashboard, teacher looking at the dashboard, teacher interacting with attendance controls, students entering the classroom, hallway focus, giant holograms, cyberpunk aesthetics, dystopian atmosphere, exaggerated surveillance imagery, text-heavy generated interfaces, warped faces, extra limbs, cartoon or anime style, dark dramatic lighting, chaotic classroom behavior."""


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
    print(f"\n✓ Done! Wan Scene 3 saved to:\n  {OUTPUT_FILE}")


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
    print(" PresenceAI · Scene 3: Wan 3.0 (the system starts to struggle)")
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

    if not ask_yes_no(f"Generate Wan Scene 3 at {RESOLUTION} (~${usd:.2f})? (y/n)"):
        print("Cancelled. Nothing was submitted or charged.")
        return

    idem = str(uuid.uuid4())
    job = {"scene": 3, "model_id": MODEL_ID, "resolution": RESOLUTION, "idempotency_key": idem,
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
