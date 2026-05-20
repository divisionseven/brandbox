"""
Logo fetching, image processing, and local disk cache.

Processing pipeline per domain:
  1. Try SVG logo services (SimpleIcons → VectorLogo.Zone → Wikimedia Commons)
  2. Try raster logo APIs (Hunter → DeBounce → LogoKit → Brandfetch)
  3. Auto-crop transparent pixel padding from alpha-channel images
  4. Scale to fill the output canvas preserving aspect ratio
  5. Center on a transparent RGBA canvas and save as PNG
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import NamedTuple

import requests
import tldextract
from PIL import Image

# Output image size
CANVAS_SIZE = 200


class LogoSrc(NamedTuple):
    """Logo bytes with provenance metadata."""

    png: bytes
    source: str
    dims: str


# Logo API sources, tried in order. First valid response wins.
LOGO_SOURCES = [
    "https://logos.hunter.io/{domain}",
    "https://logo.debounce.com/{domain}",
    "https://img.logokit.com/{domain}?token=free",
    "https://logo.brandfetch.io/{domain}",
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

# SVG logo sources, tried in order before raster APIs.
# SVGs are inherently transparent — no white-background issues.
SVG_SOURCES = [
    "https://cdn.simpleicons.org/{slug}",
    "https://www.vectorlogo.zone/logos/{slug}/{slug}-icon.svg",
]

# Wikimedia Commons filenames for domains not in SimpleIcons/VectorLogo.
# Grown organically as users encounter uncovered domains.
WIKIMEDIA_FILENAMES: dict[str, str] = {
    "slack.com": "Slack_Technologies_Logo.svg",
    "linear.app": "Linear_logo.svg",
}

# Domain → SimpleIcons slug overrides (domains where slug ≠ domain minus TLD).
SLUG_OVERRIDES: dict[str, str] = {
    "linear.app": "linear",
}


def _domain_to_slug(domain: str) -> str | None:
    """Derive a SimpleIcons-style slug from a root domain.

    SimpleIcons slugs are usually the registered domain name minus the TLD,
    lowercased. Exceptions are handled via SLUG_OVERRIDES.

    Uses tldextract to handle multi-part TLDs correctly (e.g. ``mega-corp.co.uk``
    → ``mega-corp``, not ``co``).

    Examples:
        stripe.com       → stripe
        mega-corp.co.uk  → mega-corp
        linear.app       → linear  (via SLUG_OVERRIDES)
        localhost        → None
    """
    try:
        if not domain:
            return None
        domain = domain.strip().lower()
        if domain in SLUG_OVERRIDES:
            return SLUG_OVERRIDES[domain]
        parsed = tldextract.extract(domain)
        if parsed.domain and parsed.suffix:
            return parsed.domain
        return None
    except Exception:
        return None


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
      - Scale to fill CANVAS_SIZE × CANVAS_SIZE preserving aspect ratio
      - Center on a transparent CANVAS_SIZE × CANVAS_SIZE canvas
    """
    try:
        src = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

        src, _ = _autocrop_alpha_padding(src)  # discard was_cropped — no repadding needed

        # Scale to fill CANVAS_SIZE × CANVAS_SIZE preserving aspect ratio
        ratio = min(CANVAS_SIZE / src.width, CANVAS_SIZE / src.height)
        new_size = (max(1, int(src.width * ratio)), max(1, int(src.height * ratio)))
        src = src.resize(new_size, Image.Resampling.LANCZOS)

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


def _fetch_svg_logo(domain: str) -> tuple[bytes, str] | tuple[None, None]:
    """Try SVG logo sources; return PNG bytes and source label.

    SVGs are inherently transparent — this avoids the white-background
    problem common with raster-only logo APIs.
    """
    slug = _domain_to_slug(domain)
    if slug:
        for template in SVG_SOURCES:
            url = template.format(slug=slug)
            try:
                resp = requests.get(url, timeout=10, allow_redirects=True)
                if resp.status_code != 200:
                    continue
                content = resp.content
                # Reject non-SVG responses (e.g. HTML error pages)
                if not content.startswith((b"<svg", b"<?xml", b"<?")):
                    continue
                # Rasterize SVG to PNG via cairosvg
                try:
                    import cairosvg
                except (ImportError, OSError):
                    return None, None  # SVG unavailable → fall through to raster
                raw_png = cairosvg.svg2png(bytestring=content, output_width=CANVAS_SIZE * 2)
                if raw_png and len(bytes(raw_png)) > 50:
                    src_label = (
                        f"simpleicons:{slug}" if "simpleicons" in template else f"vectorlogo:{slug}"
                    )
                    return bytes(raw_png), src_label
            except Exception:
                continue

    # Try Wikimedia Commons as a third SVG source (requires filename lookup)
    if domain in WIKIMEDIA_FILENAMES:
        filename = WIKIMEDIA_FILENAMES[domain]
        url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{filename}"
        try:
            headers = {"User-Agent": "Brandbox/1.0"}
            resp = requests.get(url, timeout=10, allow_redirects=True, headers=headers)
            if resp.status_code == 200:
                content = resp.content
                if content.startswith((b"<svg", b"<?xml", b"<?")):
                    try:
                        import cairosvg
                    except (ImportError, OSError):
                        return None, None
                    raw_png = cairosvg.svg2png(bytestring=content, output_width=CANVAS_SIZE * 2)
                    if raw_png and len(bytes(raw_png)) > 50:
                        src_label = f"wikimedia:{filename}"
                        return bytes(raw_png), src_label
        except Exception:
            pass

    return None, None


def _fetch_raw(domain: str) -> tuple[bytes, str] | tuple[None, None]:
    """Try each logo source in order; return image bytes and source label."""
    for template in LOGO_SOURCES:
        url = template.format(domain=domain)
        try:
            resp = requests.get(url, timeout=10, allow_redirects=True)
            if resp.status_code == 200 and len(resp.content) > 800:
                Image.open(io.BytesIO(resp.content))  # validate it's a real image
                if "hunter" in template:
                    src_label = "hunter"
                elif "debounce" in template:
                    src_label = "debounce"
                elif "logokit" in template:
                    src_label = "logokit"
                else:
                    src_label = "brandfetch"
                return resp.content, src_label
        except Exception:
            continue
    return None, None


# Cache


def _png_path(cache_dir: Path, domain: str) -> Path:
    return cache_dir / f"{domain}.png"


def _miss_path(cache_dir: Path, domain: str) -> Path:
    return cache_dir / f"{domain}.miss"


def is_known_miss(cache_dir: Path, domain: str) -> bool:
    return _miss_path(cache_dir, domain).exists()


def get_logo(cache_dir: Path, domain: str) -> LogoSrc | None:
    """Return processed PNG bytes (with provenance) for the domain.

    Uses local cache when available. Records a .miss sentinel for
    domains with no logo so they aren't retried.
    """
    if is_known_miss(cache_dir, domain):
        return None

    cached = _png_path(cache_dir, domain)
    if cached.exists():
        png_bytes = cached.read_bytes()
        return LogoSrc(png_bytes, "cache", "unknown")

    # Fetch — try SVG first, then raster
    raw_png, source = _fetch_svg_logo(domain)
    if not raw_png:
        raw_png, source = _fetch_raw(domain)

    if not raw_png:
        _miss_path(cache_dir, domain).touch()
        return None

    # Extract metadata from raw bytes before conversion
    try:
        img = Image.open(io.BytesIO(raw_png))
        dims = f"{img.width}x{img.height}"
    except Exception:
        dims = "unknown"

    png = logo_to_png(raw_png)
    if not png:
        _miss_path(cache_dir, domain).touch()
        return None

    cached.write_bytes(png)
    assert isinstance(source, str)
    return LogoSrc(png, source, dims)


def clear_cache(cache_dir: Path) -> int:
    """Delete all cached logos and miss sentinels. Returns number of files removed."""
    removed = 0
    for f in cache_dir.glob("*"):
        if f.is_file() and f.name != ".gitkeep":
            f.unlink()
            removed += 1
    return removed
