"""Visual generation pipeline for Athena.

The Gemini *Live* model only speaks. Whenever the user asks to see something, it calls
`display_visual`, which runs this pipeline using separate, free-tier-friendly models:

    image / illustration / infographic
        1. Gemini native image model(s)   (IMAGE_MODELS, e.g. gemini-2.5-flash-image)
        2. Gemini text model -> hand-written SVG   (always works on the free tier)
        3. Pollinations.ai (no key needed)

    diagram
        Mermaid (written by the live model)  ->  falls back to SVG from the text model

    chart
        SVG from the text model

Generated files are saved to ./generated and served at /generated/<file>.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
import urllib.parse
import uuid
from pathlib import Path

from google import genai
from google.genai import types

log = logging.getLogger("athena-live.visuals")

ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = ROOT / "generated"
GENERATED_DIR.mkdir(exist_ok=True)
MAX_KEPT_FILES = 60

# Comma-separated list, tried in order. Override in .env.
IMAGE_MODELS = [
    m.strip()
    for m in os.getenv(
        "IMAGE_MODELS", "gemini-2.5-flash-image,gemini-2.0-flash-preview-image-generation"
    ).split(",")
    if m.strip()
]
TEXT_MODEL = os.getenv("TEXT_MODEL", "gemini-2.5-flash")
IMAGE_TIMEOUT = float(os.getenv("IMAGE_TIMEOUT", "45"))

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client()  # reads GOOGLE_API_KEY from the environment
    return _client


# --------------------------------------------------------------------------- helpers
def _cleanup_old_files() -> None:
    files = sorted(GENERATED_DIR.glob("*"), key=lambda f: f.stat().st_mtime)
    for f in files[:-MAX_KEPT_FILES]:
        try:
            f.unlink()
        except OSError:
            pass


def _save(data: bytes, ext: str) -> str:
    _cleanup_old_files()
    name = f"{int(time.time())}-{uuid.uuid4().hex[:8]}.{ext}"
    (GENERATED_DIR / name).write_bytes(data)
    return f"/generated/{name}"


def _ext_for(mime: str) -> str:
    return {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
        "image/svg+xml": "svg",
    }.get(mime, "png")


def sanitize_svg(svg: str) -> str:
    """Strip anything executable. SVG is only ever shown through <img>, which already
    blocks scripts, but we sanitize anyway so the saved file is safe to open directly."""
    svg = re.sub(r"<script\b.*?</script>", "", svg, flags=re.S | re.I)
    svg = re.sub(r"<foreignObject\b.*?</foreignObject>", "", svg, flags=re.S | re.I)
    svg = re.sub(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*')", "", svg, flags=re.I)
    svg = re.sub(r"(href|xlink:href)\s*=\s*(\"|')\s*javascript:[^\"']*(\"|')", "", svg, flags=re.I)
    return svg


# --------------------------------------------------------------------------- backends
async def _gemini_image(prompt: str) -> tuple[bytes, str, str] | None:
    """Native Gemini image generation. Returns (bytes, mime, model) or None."""
    client = _get_client()
    for model in IMAGE_MODELS:
        try:
            resp = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
                ),
                timeout=IMAGE_TIMEOUT,
            )
            for cand in resp.candidates or []:
                for part in (cand.content.parts if cand.content else []) or []:
                    inline = getattr(part, "inline_data", None)
                    if inline and inline.data:
                        return inline.data, inline.mime_type or "image/png", model
            log.warning("Image model %s returned no image part", model)
        except Exception as exc:  # noqa: BLE001
            log.warning("Image model %s failed: %r", model, exc)
    return None


SVG_SYSTEM = (
    "You are an expert SVG illustrator and information designer. Output ONLY one complete, "
    "valid <svg> element and nothing else (no markdown fences, no commentary). Rules: "
    'viewBox="0 0 800 500"; dark-friendly design with a transparent or #0a0a0a background; '
    "use a lime (#a3ff00) accent with white/grey text; text must be legible (min 14px) and "
    "never overflow its box; use rounded rects, arrows (with <marker>), gradients and simple "
    "icons made from shapes; no external images, fonts, scripts or links."
)


async def _gemini_svg(title: str, prompt: str, visual_type: str) -> tuple[bytes, str, str] | None:
    client = _get_client()
    try:
        resp = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=TEXT_MODEL,
                contents=f"Create a {visual_type} titled '{title}'. Details: {prompt}",
                config=types.GenerateContentConfig(system_instruction=SVG_SYSTEM, temperature=0.7),
            ),
            timeout=IMAGE_TIMEOUT,
        )
        text = resp.text or ""
        m = re.search(r"<svg\b.*?</svg>", text, flags=re.S | re.I)
        if not m:
            return None
        return sanitize_svg(m.group(0)).encode(), "image/svg+xml", TEXT_MODEL
    except Exception as exc:  # noqa: BLE001
        log.warning("SVG generation failed: %r", exc)
        return None


async def _pollinations(prompt: str) -> tuple[bytes, str, str] | None:
    """Keyless community image service; best-effort last resort."""
    try:
        import httpx

        url = (
            "https://image.pollinations.ai/prompt/"
            f"{urllib.parse.quote(prompt[:400])}?width=800&height=500&nologo=true"
        )
        async with httpx.AsyncClient(timeout=40, follow_redirects=True) as http:
            r = await http.get(url)
        ctype = r.headers.get("content-type", "")
        if r.status_code == 200 and ctype.startswith("image/"):
            return r.content, ctype.split(";")[0], "pollinations"
    except Exception as exc:  # noqa: BLE001
        log.warning("Pollinations failed: %r", exc)
    return None


# --------------------------------------------------------------------------- public API
async def generate_visual(
    *,
    title: str,
    caption: str,
    visual_type: str,
    image_prompt: str,
    diagram_definition: str | None,
    key_points: list[str],
) -> dict:
    """Return a small JSON-safe dict (safe to hand back to the live model)."""
    vt = (visual_type or "image").lower()
    base = {
        "title": title,
        "caption": caption,
        "visual_type": vt,
        "key_points": key_points,
        "image_url": "",
        "diagram": "",
        "generated_by": "",
    }

    # Simple diagrams: Mermaid is instant and free, no image model needed.
    if vt == "diagram" and diagram_definition:
        return {**base, "status": "displayed", "diagram": diagram_definition, "generated_by": "mermaid"}

    if vt in ("image", "illustration", "photo", "infographic"):
        chain = (
            lambda: _gemini_image(image_prompt),
            lambda: _gemini_svg(title, image_prompt, vt),
            lambda: _pollinations(image_prompt),
        )
    else:  # diagram without mermaid, chart, anything else -> SVG first
        chain = (
            lambda: _gemini_svg(title, image_prompt, vt),
            lambda: _gemini_image(image_prompt),
        )

    for step in chain:
        found = await step()
        if found:
            data, mime, model = found
            url = _save(data, _ext_for(mime))
            log.info("Visual generated via %s -> %s", model, url)
            return {**base, "status": "displayed", "image_url": url, "generated_by": model}

    return {
        **base,
        "status": "failed",
        "error": "Could not generate the visual right now. Tell the user briefly and offer to describe it in words.",
    }
