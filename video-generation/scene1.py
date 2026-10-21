"""
PresenceAI · Future Simulation: Scene 1 video generator
=========================================================

Generates ONE 5-second clip with Higgsfield's Kling O3 image-reference
model in Pro mode (sound off), guided by two reference images, and saves
it as output/scene1.mp4.

Based on the official Higgsfield API docs (docs.higgsfield.ai):
  - Endpoint : POST https://api.higgsfield.ai/kling-video/o3/image-reference
  - Estimate : POST https://api.higgsfield.ai/estimate/kling-video/o3/image-reference
  - Uploads  : POST https://api.higgsfield.ai/files/generate-upload-url → PUT file → public_url
  - Auth     : Authorization: Key <KEY_ID>:<KEY_SECRET>
  - Status   : GET <status_url> → queued | in_progress | completed | failed | nsfw | canceled
  - Output   : response["video"]["url"]

Budget safety
  - Shows the cost estimate and asks "Generate Scene 1? (y/n)" before spending.
  - Submits at most ONE job. Never retries a generation automatically.
  - Saves the job ID to output/scene1_job.json. If you run the script again,
    it resumes polling/downloading that SAME job instead of creating a new one.
  - Uses an Idempotency-Key, so a re-sent submission can never create a second charge.
"""

import json
import random
import sys
import time
import uuid
from pathlib import Path

import requests
from dotenv import dotenv_values

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

BASE_URL = "https://api.higgsfield.ai"
MODEL_ID = "kling-video/o3/image-reference"   # Kling O3 · Image reference (exact docs ID), mode "pro"
GENERATE_URL = f"{BASE_URL}/{MODEL_ID}"
ESTIMATE_URL = f"{BASE_URL}/estimate/{MODEL_ID}"
UPLOAD_URL_ENDPOINT = f"{BASE_URL}/files/generate-upload-url"

# Hard spending cap: the script refuses to submit if the estimate is above this.
MAX_USD = 2.00

HERE = Path(__file__).resolve().parent
ENV_FILE = HERE / ".env"
OUTPUT_DIR = HERE / "output"
OUTPUT_FILE = OUTPUT_DIR / "scene1.mp4"
JOB_FILE = OUTPUT_DIR / "scene1_job.json"

POLL_TIMEOUT_SECONDS = 30 * 60   # stop polling after 30 min (job keeps running; rerun to resume)

# Reference images, in order. The docs define image_urls as an ORDERED list, so the
# prompt refers to them as "the first" and "the second" reference image.
REFERENCES_DIR = HERE / "references"
REFERENCE_IMAGES = [
    REFERENCES_DIR / "presenceai_dashboard_cropped.png",   # 1: dashboard (laptop frame cropped away)
    REFERENCES_DIR / "windesheim_logo.png",                # 2: university branding
]

# Based on attempt 3 (the good one), with the entrance device and Windesheim logo made explicit.
PROMPT = (
    "A realistic cinematic wide shot from the hallway outside a modern Dutch university classroom. The "
    "viewer is positioned slightly to the side of the classroom entrance, so the entrance and the "
    "classroom interior are clearly visible."
    "\n\n"
    "The classroom has a wide modern glass door and glass wall. Part of the glass is frosted for privacy, "
    "while another section remains transparent so the viewer can clearly see inside."
    "\n\n"
    "Several diverse university students walk from the hallway INTO the classroom at the start of a "
    "lesson."
    "\n\n"
    "Inside, a teacher stands at the front of the room, in front of a large projector screen behind them "
    "that shows the PresenceAI attendance dashboard from the first reference image."
    "\n\n"
    "Clearly visible in the hallway, mounted on the wall right beside the glass door at shoulder height, "
    "is a small sleek PresenceAI attendance device: a compact camera lens above a small glowing screen. "
    "As each student walks past it, the device screen lights up with a futuristic facial-template scan, "
    "a glowing blue wireframe face mesh with scanning lines, which then turns into a green check mark "
    "confirming successful registration. The device and its glowing screen must be visible in the shot."
    "\n\n"
    "On the glass wall next to the door is a small Windesheim logo decal matching the second reference "
    "image: the yellow W mark with the black Windesheim wordmark. Small and subtle like real campus "
    "signage, but clearly present."
    "\n\n"
    "The technology feels advanced enough for 2045 but realistic and believable. Natural morning "
    "daylight, realistic student movement, believable body language, clean modern architecture, "
    "professional cinematic realism."
)

# Tells the model how to use the first (dashboard) reference image.
REFERENCE_NOTE = (
    "The first reference image is the authoritative PresenceAI dashboard: show it on the classroom "
    "display, preserving its branding, layout, colors, status logic and style. Do not invent other "
    "student names, counts or statuses."
)

# Kling O3 has no negative-prompt field, so the "avoid" list is appended to the prompt itself.
AVOID = [
    "students walking out of the classroom", "exterior building exits", "giant holograms",
    "cyberpunk aesthetics", "dystopian atmosphere", "aggressive surveillance visuals",
    "giant face close-ups", "large scan overlays on students' faces", "text-heavy generated interfaces",
    "warped faces", "extra limbs", "cartoon or anime style", "dark dramatic lighting",
    "chaotic camera movement", "oversized Windesheim branding",
]

FULL_PROMPT = f"{PROMPT}\n\n{REFERENCE_NOTE}\n\nAvoid: {', '.join(AVOID)}."

# Request body, using only fields documented in the official input schema.
# image_urls is added at runtime after the reference images are uploaded.
PAYLOAD = {
    "prompt": FULL_PROMPT,
    "mode": "pro",          # documented values: "std" | "pro" | "4k"
    "duration": 5,          # seconds
    "aspect_ratio": "16:9",
    "sound": "off",         # audio disabled (documented values: "on" / "off")
    "multi_shots": False,   # single shot: exactly one 5-second clip
}


def build_payload(image_urls: list[str]) -> dict:
    return {**PAYLOAD, "image_urls": image_urls}

TERMINAL_STATUSES = {"completed", "failed", "nsfw", "canceled"}


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

class ApiError(Exception):
    """An HTTP error from Higgsfield, with a readable message (never contains the API key)."""


def fail(msg: str) -> None:
    print(f"\n✗ {msg}")
    sys.exit(1)


def load_credentials() -> str:
    """Read HIGGSFIELD_API_KEY from video-generation/.env and validate it (never printed)."""
    if not ENV_FILE.exists():
        fail(f"No .env file found at {ENV_FILE}")

    key = (dotenv_values(ENV_FILE).get("HIGGSFIELD_API_KEY") or "").strip()
    if not key:
        fail("HIGGSFIELD_API_KEY is missing or empty in video-generation/.env")
    if key == "your-key-id:your-key-secret":
        fail("HIGGSFIELD_API_KEY is still the placeholder. Paste your real key in video-generation/.env")
    if ":" not in key:
        fail("HIGGSFIELD_API_KEY must be in the format KEY_ID:KEY_SECRET "
             "(Higgsfield gives you both values when you create a key).")
    return key


def headers(key: str, idempotency_key: str | None = None) -> dict:
    h = {"Authorization": f"Key {key}", "Content-Type": "application/json"}
    if idempotency_key:
        h["Idempotency-Key"] = idempotency_key
    return h


def describe_error(resp: requests.Response) -> str:
    """Turn an HTTP error into a clear message, based on the documented status codes."""
    try:
        detail = resp.json().get("detail", resp.text)
    except ValueError:
        detail = resp.text[:300]
    meaning = {
        400: "Invalid parameters, rejected input, or concurrency limit reached",
        401: "Invalid credentials. Check HIGGSFIELD_API_KEY in .env",
        403: "Insufficient credits",
        404: "Model or request not found for this account",
        422: "Request validation failed",
        423: "Model is temporarily blocked. Try again later",
        503: "Model is disabled or not ready. Try again later",
    }.get(resp.status_code, "Unexpected server error")
    corr = resp.headers.get("X-Correlation-ID")
    corr_txt = f"\n  Correlation ID (for support): {corr}" if corr else ""
    return f"HTTP {resp.status_code}: {meaning}\n  Detail: {detail}{corr_txt}"


def save_job(data: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    JOB_FILE.write_text(json.dumps(data, indent=2))


def load_job() -> dict | None:
    if JOB_FILE.exists():
        try:
            return json.loads(JOB_FILE.read_text())
        except ValueError:
            fail(f"{JOB_FILE.name} is corrupted. Inspect it manually before doing anything else.")
    return None


def ask_yes_no(question: str) -> bool:
    try:
        return input(f"\n{question} ").strip().lower() == "y"
    except (EOFError, KeyboardInterrupt):
        return False


# ─────────────────────────────────────────────────────────────
# Steps
# ─────────────────────────────────────────────────────────────

def show_config() -> None:
    print("=" * 64)
    print(" PresenceAI · Scene 1: Higgsfield video generation")
    print("=" * 64)
    print(f"  Model         : Kling O3 · Image reference")
    print(f"  Model ID      : {MODEL_ID}")
    print(f"  Endpoint      : POST {GENERATE_URL}")
    print(f"  Mode          : {PAYLOAD['mode']} (no resolution parameter; docs don't state the exact resolution)")
    print(f"  Videos        : exactly 1")
    print(f"  Duration      : {PAYLOAD['duration']} seconds")
    print(f"  Aspect ratio  : {PAYLOAD['aspect_ratio']}")
    print(f"  Audio         : {PAYLOAD['sound']}")
    for i, img in enumerate(REFERENCE_IMAGES, 1):
        print(f"  Reference {i}   : references/{img.name}")
    print(f"  Prompt length : {len(FULL_PROMPT)} / 2500 characters")
    print(f"  Output file   : {OUTPUT_FILE}")
    print(f"  Spending cap  : ${MAX_USD:.2f} (script refuses above this)")


def upload_references(key: str, images: list[Path] | None = None) -> list[str]:
    """Upload reference images via Higgsfield's presigned upload flow. Free; does not generate.
    Defaults to this scene's REFERENCE_IMAGES; other scripts may pass their own list."""
    print("\n→ Uploading reference images (free, no generation)…")
    urls = []
    for img in images or REFERENCE_IMAGES:
        if not img.exists():
            fail(f"Reference image not found: {img}")
        content_type = "image/png" if img.suffix.lower() == ".png" else "image/jpeg"
        try:
            resp = requests.post(UPLOAD_URL_ENDPOINT, headers=headers(key),
                                 json={"content_type": content_type}, timeout=30)
            if not resp.ok:
                fail(f"Could not create an upload URL for {img.name}.\n  " + describe_error(resp))
            info = resp.json()
            # Presigned storage URL: send ONLY the returned headers, never the API credentials.
            put = requests.put(info["upload_url"], headers=info.get("upload_headers", {}),
                               data=img.read_bytes(), timeout=120)
            put.raise_for_status()
        except requests.RequestException as e:
            fail(f"Uploading {img.name} failed ({e.__class__.__name__}). Nothing was submitted or charged.")
        except KeyError:
            fail(f"Unexpected upload response format for {img.name}. Nothing was submitted.")
        urls.append(info["public_url"])
        print(f"  ✓ {img.name}")
    return urls


def estimate_cost(key: str, payload: dict) -> float:
    """Ask Higgsfield for the exact estimated cost of this request. Free; does not generate."""
    print("\n→ Requesting cost estimate (free, no generation)…")
    try:
        resp = requests.post(ESTIMATE_URL, headers=headers(key), json=payload, timeout=30)
    except requests.RequestException as e:
        fail(f"Could not reach the estimate endpoint: {e.__class__.__name__}. Nothing was charged.")
    if not resp.ok:
        fail("Cost estimate failed, so nothing was submitted or charged.\n  " + describe_error(resp))

    data = resp.json()
    try:
        usd = float(data["usd"])
    except (KeyError, TypeError, ValueError):
        fail(f"Unexpected estimate response format: {data}. Nothing was submitted.")
    print(f"  Estimated cost: ${usd:.3f} USD  ({data.get('credits', '?')} credits)")
    return usd


def submit(key: str, idempotency_key: str, payload: dict) -> dict:
    """Send exactly ONE generation request. No automatic retries."""
    print("\n→ Submitting generation (one job)…")
    try:
        resp = requests.post(GENERATE_URL, headers=headers(key, idempotency_key), json=payload, timeout=60)
    except requests.RequestException as e:
        # Ambiguous: Higgsfield may or may not have accepted it. Keep the idempotency key
        # so the next run can safely re-send with the SAME key (no double charge possible).
        fail(f"Network problem during submission ({e.__class__.__name__}).\n"
             f"  It is unclear whether the job was accepted. Run the script again: it will offer to\n"
             f"  re-send with the SAME idempotency key, which cannot create a second job or charge.")

    if resp.status_code >= 500:
        fail("Server error during submission. It is unclear whether the job was accepted.\n  "
             + describe_error(resp)
             + "\n  Run the script again later: it re-sends with the SAME idempotency key (no double charge).")
    if not resp.ok:
        # Rejected before acceptance: nothing was created, the key is not consumed.
        JOB_FILE.unlink(missing_ok=True)
        fail("Generation request rejected. Nothing was created or charged.\n  " + describe_error(resp))

    data = resp.json()
    if "request_id" not in data or "status_url" not in data:
        fail(f"Unexpected submission response: {data}")
    return data


def poll(key: str, status_url: str) -> dict:
    """Poll the SAME job until it reaches a terminal status. Only GET requests, never re-submits."""
    print("\n→ Waiting for the video (this usually takes a few minutes)…")
    start = time.time()
    delay = 2.0
    last_status = None
    while True:
        elapsed = int(time.time() - start)
        if elapsed > POLL_TIMEOUT_SECONDS:
            fail("Polling timed out, but the job is still on Higgsfield's side.\n"
                 "  Run the script again to resume checking the SAME job (no new charge).")
        try:
            resp = requests.get(status_url, headers=headers(key), timeout=30)
        except requests.RequestException as e:
            print(f"  [{elapsed:>4}s] network hiccup ({e.__class__.__name__}), retrying status check…")
            time.sleep(delay)
            delay = min(delay * 1.5, 10.0)
            continue

        if resp.status_code >= 500:
            print(f"  [{elapsed:>4}s] server error {resp.status_code}, retrying status check…")
        elif not resp.ok:
            fail("Status check failed. The job record is kept, so you can rerun to resume.\n  "
                 + describe_error(resp))
        else:
            data = resp.json()
            status = data.get("status")
            if status != last_status:
                print(f"  [{elapsed:>4}s] status: {status}")
                last_status = status
            else:
                print(f"  [{elapsed:>4}s] still {status}…", end="\r")
            if status in TERMINAL_STATUSES:
                print()
                return data

        time.sleep(delay + random.uniform(0, 0.5))
        delay = min(delay * 1.5, 10.0)


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
        fail(f"Download failed ({e.__class__.__name__}). The video is still available for at least 7 days.\n"
             f"  Run the script again to retry the download (no new generation).")
    tmp.replace(OUTPUT_FILE)


# ─────────────────────────────────────────────────────────────
# Main flow
# ─────────────────────────────────────────────────────────────

def finish(key: str, job: dict) -> None:
    """Poll an existing job, then download the result."""
    result = poll(key, job["status_url"])
    status = result.get("status")
    job["status"] = status
    save_job(job)

    if status == "completed":
        video_url = (result.get("video") or {}).get("url")
        if not video_url:
            fail(f"Job completed but no video URL was found in the response: {result}")
        job["video_url"] = video_url
        save_job(job)
        download(video_url)
        print(f"\n✓ Done! Scene 1 saved to:\n  {OUTPUT_FILE}")
    elif status in ("failed", "nsfw"):
        fail(f"Job ended with status '{status}'. {result.get('error', '')}\n"
             f"  Failed and NSFW jobs are not charged. The script will NOT retry automatically.\n"
             f"  Delete {JOB_FILE.name} if you deliberately want to try a new generation.")
    else:
        fail(f"Job ended with status '{status}'. Not retrying automatically.")


def main() -> None:
    key = load_credentials()

    # 1. Already have the video? Then do nothing.
    if OUTPUT_FILE.exists():
        print(f"✓ {OUTPUT_FILE.name} already exists:\n  {OUTPUT_FILE}\n"
              f"  Nothing to do. Delete it (and {JOB_FILE.name}) only if you want a new generation.")
        return

    job = load_job()

    # Safety: never resume or replay a job that belongs to a different model.
    if job and job.get("model_id") != MODEL_ID:
        fail(f"{JOB_FILE.name} belongs to a different model ({job.get('model_id')}).\n"
             f"  Check that job manually. Delete {JOB_FILE} only if you are sure it is finished or unwanted.")

    # 2. A job was already created earlier: resume it. NEVER create a new one.
    if job and job.get("request_id"):
        print(f"→ Found existing job {job['request_id']} (status last seen: {job.get('status', '?')}).")
        if job.get("status") in ("failed", "nsfw", "canceled"):
            fail(f"That job ended as '{job['status']}'. Not retrying automatically.\n"
                 f"  Delete {JOB_FILE} if you deliberately want a new generation.")
        print("  Resuming the SAME job. No new generation and no new charge.")
        if job.get("video_url"):
            try:
                download(job["video_url"])
                print(f"\n✓ Done! Scene 1 saved to:\n  {OUTPUT_FILE}")
                return
            except SystemExit:
                print("  Saved video URL didn't work, checking job status instead…")
        finish(key, job)
        return

    # 3. A submission was sent but the answer was lost: offer a SAFE replay.
    if job and job.get("idempotency_key"):
        show_config()
        print("\n⚠ A previous submission may have been accepted, but no job ID was received.")
        print("  Re-sending uses the SAME idempotency key: Higgsfield returns the original job")
        print("  if it exists and cannot create or charge a second one.")
        if not ask_yes_no("Re-send the same Scene 1 request safely? (y/n)"):
            print("Cancelled. Nothing was sent.")
            return
        # Must be byte-for-byte the same request, so reuse the SAME uploaded image URLs.
        data = submit(key, job["idempotency_key"], build_payload(job.get("image_urls", [])))
        job.update(request_id=data["request_id"], status_url=data["status_url"], status=data.get("status"))
        save_job(job)
        print(f"  Job ID: {data['request_id']}  (saved to {JOB_FILE.name})")
        finish(key, job)
        return

    # 4. Fresh run: show config → upload references → estimate → confirm → submit once.
    show_config()
    image_urls = upload_references(key)
    payload = build_payload(image_urls)
    usd = estimate_cost(key, payload)   # estimate of the EXACT request that would be submitted
    if usd > MAX_USD:
        fail(f"Estimated cost ${usd:.3f} is above the spending cap of ${MAX_USD:.2f}. Nothing was submitted.")

    if not ask_yes_no("Generate Scene 1? (y/n)"):
        print("Cancelled. Nothing was submitted or charged.")
        return

    idem = str(uuid.uuid4())
    job = {"scene": 1, "model_id": MODEL_ID, "idempotency_key": idem, "image_urls": image_urls,
           "estimated_usd": usd, "created": time.strftime("%Y-%m-%d %H:%M:%S")}
    save_job(job)   # stored BEFORE sending, so a lost response can be replayed safely

    data = submit(key, idem, payload)
    job.update(request_id=data["request_id"], status_url=data["status_url"], status=data.get("status"))
    save_job(job)
    print(f"  ✓ Job created. Job ID: {data['request_id']}")
    print(f"    Saved to {JOB_FILE}")

    finish(key, job)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nStopped by you. If a job was created, run the script again to resume the SAME job.")
        sys.exit(130)
