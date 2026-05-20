"""
Logo fetching, image processing, and local disk cache.

Processing pipeline per domain:
  1. Try logo APIs in order (LogoKit → Brandfetch → Google favicon)
  2. If the image has an alpha channel, auto-crop transparent pixel padding
  3. If padding was removed, re-add a small uniform amount so content isn't edge-to-edge
  4. Scale to fit the output canvas
  5. Center on a transparent RGBA canvas and save as PNG
"""

from __future__ import annotations

import io
from pathlib import Path

import requests
import tldextract
from PIL import Image

# Output image size
CANVAS_SIZE = 200

# Pixels of padding re-added after transparent-crop (out of CANVAS_SIZE).
# Only applied to images that had transparent padding stripped.
REPAD_PX = 10

# Logo API sources, tried in order. First valid response wins.
LOGO_SOURCES = [
    "https://img.logokit.com/{domain}?token=free",
    "https://logo.brandfetch.io/{domain}",
    "https://www.google.com/s2/favicons?domain={domain}&sz=128",
]

# Free/personal email domains — no company logo to fetch
SKIP_DOMAINS: frozenset[str] = frozenset(
    {
        "gmail.com",
        "yahoo.com",
        "hotmail.com",
        "outlook.com",
        "live.com",
        "msn.com",
        "icloud.com",
        "me.com",
        "mac.com",
        "aol.com",
        "protonmail.com",
        "proton.me",
        "fastmail.com",
        "fastmail.fm",
        "hey.com",
        "zoho.com",
        "yandex.com",
        "mail.com",
    }
)


# Domain extraction


def root_domain(email_or_domain: str) -> str | None:
    """
    Extract the registrable root domain from an email address or hostname.

    Examples:
        john@stripe.com               → stripe.com
        noreply@mail.whitehouse.gov   → whitehouse.gov
        info@subscriptions.war.gov    → war.gov
        user@bbc.co.uk               → bbc.co.uk
    """
    try:
        s = email_or_domain.strip().lower()
        host = s.split("@")[1] if "@" in s else s
        parsed = tldextract.extract(host)
        if parsed.domain and parsed.suffix:
            return f"{parsed.domain}.{parsed.suffix}"
    except Exception:
        pass
    return None


def is_personal_domain(domain: str) -> bool:
    return domain in SKIP_DOMAINS


# Image processing


def _autocrop_alpha_padding(img: Image.Image) -> tuple[Image.Image, bool]:
    """
    Crop transparent pixel padding from an RGBA image.

    Returns (cropped_image, was_cropped).
    Images without an alpha channel, or with no transparent padding, are
    returned unchanged with was_cropped=False.
    """
    if img.mode != "RGBA":
        return img, False

    alpha = img.split()[3]
    bbox = alpha.getbbox()  # tight bounding box of non-transparent pixels

    if bbox is None:
        return img, False  # fully transparent — nothing to show

    full_bbox = (0, 0, img.width, img.height)
    if bbox == full_bbox:
        return img, False  # no transparent padding present

    return img.crop(bbox), True


def logo_to_png(image_bytes: bytes) -> bytes | None:
    """
    Convert raw logo bytes (any format) to a square RGBA PNG for Outlook.

    Pipeline:
      - Auto-crop transparent padding if present
      - Re-add a small fixed padding (REPAD_PX) only if padding was stripped
      - Scale to fit CANVAS_SIZE × CANVAS_SIZE preserving aspect ratio
      - Center on a transparent CANVAS_SIZE × CANVAS_SIZE canvas
    """
    try:
        src = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

        src, was_cropped = _autocrop_alpha_padding(src)

        # Scale to fit — leave room for re-padding if we cropped
        inner = CANVAS_SIZE - (REPAD_PX * 2) if was_cropped else CANVAS_SIZE
        src.thumbnail((inner, inner), Image.Resampling.LANCZOS)

        canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
        x = (CANVAS_SIZE - src.width) // 2
        y = (CANVAS_SIZE - src.height) // 2
        canvas.paste(src, (x, y), mask=src.split()[3])

        buf = io.BytesIO()
        canvas.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


# Logo fetching


def _fetch_raw(domain: str) -> bytes | None:
    """Try each logo source in order; return the first valid image bytes."""
    for template in LOGO_SOURCES:
        url = template.format(domain=domain)
        try:
            resp = requests.get(url, timeout=10, allow_redirects=True)
            if resp.status_code == 200 and len(resp.content) > 800:
                Image.open(io.BytesIO(resp.content))  # validate it's a real image
                return resp.content
        except Exception:
            continue
    return None


# Cache


def _png_path(cache_dir: Path, domain: str) -> Path:
    return cache_dir / f"{domain}.png"


def _miss_path(cache_dir: Path, domain: str) -> Path:
    return cache_dir / f"{domain}.miss"


def is_known_miss(cache_dir: Path, domain: str) -> bool:
    return _miss_path(cache_dir, domain).exists()


def get_logo(cache_dir: Path, domain: str) -> bytes | None:
    """
    Return processed PNG bytes for the domain, using the local cache when available.
    Records a .miss sentinel for domains with no logo so they aren't retried.
    """
    if is_known_miss(cache_dir, domain):
        return None

    cached = _png_path(cache_dir, domain)
    if cached.exists():
        return cached.read_bytes()

    raw = _fetch_raw(domain)
    if not raw:
        _miss_path(cache_dir, domain).touch()
        return None

    png = logo_to_png(raw)
    if not png:
        _miss_path(cache_dir, domain).touch()
        return None

    cached.write_bytes(png)
    return png


def clear_cache(cache_dir: Path) -> int:
    """Delete all cached logos and miss sentinels. Returns number of files removed."""
    removed = 0
    for f in cache_dir.glob("*"):
        if f.is_file() and f.name != ".gitkeep":
            f.unlink()
            removed += 1
    return removed
