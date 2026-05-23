"""Tests for image-processing functions in brandbox.cli.

Covers _autocrop_logo_png and _prepare_logo_for_braille — both operate on
in-memory RGBA PNG bytes. All tests create pixel fixtures with Pillow in
memory, so they are fast and have no disk I/O beyond BytesIO.
"""

from __future__ import annotations

import io

from PIL import Image

from brandbox.cli import _autocrop_logo_png, _prepare_logo_for_braille

# ── helpers ──────────────────────────────────────────────────────────


def _make_rgba_png(
    width: int,
    height: int,
    pixels: list[tuple[int, int, int, int]],
) -> bytes:
    """Create a small RGBA PNG from pixel data.

    Args:
        width: Image width in pixels.
        height: Image height in pixels.
        pixels: Flat list of RGBA tuples, row-major order.
            Must have exactly width × height entries.

    Returns:
        PNG-encoded bytes.
    """
    img = Image.new("RGBA", (width, height))
    img.putdata(pixels)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════
#  _autocrop_logo_png
# ═══════════════════════════════════════════════════════════════════


def test_autocrop_fully_transparent_returns_original() -> None:
    """Fully transparent image → returns original bytes unchanged.

    Root cause: _autocrop_logo_png:207-210 — ``alpha.getbbox()`` returns
    ``None`` (no non-zero alpha pixels), so the function short-circuits
    with ``return png_bytes``. If this path were missing or returned a
    re-encoded image instead, the identity assertion would fail.
    """
    png = _make_rgba_png(3, 3, [(0, 0, 0, 0)] * 9)
    result = _autocrop_logo_png(png)
    assert result is png  # identity — same bytes object returned


def test_autocrop_no_transparent_padding_returns_original() -> None:
    """Fully opaque image (no transparent padding) → returns original bytes.

    Root cause: _autocrop_logo_png:212-215 — ``bbox`` equals
    ``(0, 0, img.width, img.height)``, so the function short-circuits
    with ``return png_bytes``. If the equality check were wrong (e.g.
    comparing against a tuple with alpha channel instead of RGB coords),
    a non-padded image would be unnecessarily re-encoded.
    """
    png = _make_rgba_png(3, 3, [(255, 0, 0, 255)] * 9)
    result = _autocrop_logo_png(png)
    assert result is png  # identity — same bytes object returned


def test_autocrop_with_transparent_padding_returns_cropped() -> None:
    """Image with transparent border → returns cropped (smaller) bytes.

    Root cause: _autocrop_logo_png:217-221 — ``bbox`` is a sub-region of
    the full canvas, so the image is cropped and re-saved. If the crop
    logic were wrong (e.g. using the wrong bbox or ignoring it), the
    output would still be 5×5 instead of 3×3.

    Scenario: A 5×5 image where the center 3×3 is opaque red and the
    outer ring is transparent. The bbox should be (1, 1, 4, 4), giving
    a cropped result of 3×3.
    """
    # 5×5 image: center 3×3 is opaque red (255,0,0,255), outer ring
    # is fully transparent (0,0,0,0).
    pixels: list[tuple[int, int, int, int]] = []
    for y in range(5):
        for x in range(5):
            if 1 <= x <= 3 and 1 <= y <= 3:
                pixels.append((255, 0, 0, 255))
            else:
                pixels.append((0, 0, 0, 0))

    png = _make_rgba_png(5, 5, pixels)
    result = _autocrop_logo_png(png)

    # Result differs from input (transparent border cropped away)
    assert result != png

    # Round-trip through Pillow to verify the actual crop dimensions
    buf = io.BytesIO(result)
    img = Image.open(buf)
    assert img.size == (3, 3), f"Expected (3, 3), got {img.size}"

    # Verify all pixels are the opaque red we expect
    expected_pixels = [(255, 0, 0, 255)] * 9
    assert list(img.getdata()) == expected_pixels


# ═══════════════════════════════════════════════════════════════════
#  _prepare_logo_for_braille
# ═══════════════════════════════════════════════════════════════════


def test_prepare_braille_fully_transparent_returns_original() -> None:
    """Fully transparent image → returns original bytes unchanged.

    Root cause: _prepare_logo_for_braille:238-240 — ``alpha.getbbox()``
    returns ``None``, so the function short-circuits with
    ``return png_bytes``.
    """
    png = _make_rgba_png(3, 3, [(0, 0, 0, 0)] * 9)
    result = _prepare_logo_for_braille(png)
    assert result is png  # identity — same bytes object returned


def test_prepare_braille_no_visible_pixels_returns_original() -> None:
    """All visible pixels have alpha ≤ 10 → returns original bytes unchanged.

    Root cause: _prepare_logo_for_braille:246-253 — the luminance loop
    skips pixels where ``a <= 10``, so ``count`` stays at 0 and the
    function short-circuits. If the threshold check were inverted or
    missing, these barely-visible pixels would still be counted and
    might trigger unnecessary compositing.

    Alpha=5 is non-zero (so ``getbbox()`` returns a valid bbox) but
    below the threshold (so the loop skips it).
    """
    png = _make_rgba_png(3, 3, [(255, 0, 0, 5)] * 9)
    result = _prepare_logo_for_braille(png)
    assert result is png  # identity — same bytes object returned


def test_prepare_braille_bright_image_returns_original() -> None:
    """Image with avg luminance > 50 → returns original bytes unchanged.

    Root cause: _prepare_logo_for_braille:260-261 — the ``avg_lum > 50``
    check short-circuits bright images. If this condition were wrong
    (e.g. ``>= 50`` or a different threshold), bright images would be
    unnecessarily composited onto white.
    """
    # All-white pixels have luminance = 255.0, avg = 255.0 > 50
    png = _make_rgba_png(3, 3, [(255, 255, 255, 255)] * 9)
    result = _prepare_logo_for_braille(png)
    assert result is png  # identity — same bytes object returned


def test_prepare_braille_nearly_bright_image_returns_original() -> None:
    """Image with avg luminance just above 50 → returns original bytes.

    Verifies the boundary condition of the luminance threshold. A pixel
    with luminance just above 50 must NOT trigger compositing.
    """
    # Luminance of (0, 86, 0) = 0 + 0.587*86 + 0 = 50.482 ≈ 50.5 > 50
    png = _make_rgba_png(3, 3, [(0, 86, 0, 255)] * 9)
    result = _prepare_logo_for_braille(png)
    assert result is png


def test_prepare_braille_dark_image_composites_on_white() -> None:
    """Dark image (avg_lum ≤ 50) → composited onto white, returns different bytes.

    Root cause: _prepare_logo_for_braille:263-269 — when ``avg_lum <= 50``,
    the function composites the RGBA image onto a solid white RGB background
    and re-encodes. The output must differ from the input in both pixel
    content and image mode (RGB vs RGBA).

    Scenario: A 3×3 all-black image (luminance = 0.0, avg = 0.0 ≤ 50).
    The function should produce an RGB image with the black pixels on
    a white background.
    """
    # All-black pixels have luminance = 0.0, avg = 0.0 ≤ 50
    png = _make_rgba_png(3, 3, [(0, 0, 0, 255)] * 9)
    result = _prepare_logo_for_braille(png)

    # Result must differ from input (composited onto white)
    assert result != png

    # Round-trip through Pillow to verify mode and content
    buf = io.BytesIO(result)
    img = Image.open(buf)
    # After compositing onto RGB background, mode should be RGB (no alpha)
    assert img.mode == "RGB", f"Expected RGB mode, got {img.mode}"

    # Verify the pixel content: black logo on white background
    # (exactly what we'd expect from compositing black onto white)
    pixel = img.getpixel((1, 1))
    assert pixel == (0, 0, 0), f"Expected black pixel, got {pixel}"


def test_prepare_braille_edge_luminance_at_threshold_composites() -> None:
    """Image with avg luminance exactly 50 → composited (≤ 50 branch).

    Root cause: _prepare_logo_for_braille uses strict ``> 50`` for the
    early-return. At exactly 50, we must go through the composite path.
    If the condition were ``>= 50`` instead, this image would be wrongly
    skipped.
    """
    # We need pixels whose average luminance = 50.0.
    # Using R=0, G=85, B=0: lum = 0 + 0.587*85 + 0 = 49.895
    # That's below 50. Good for testing the ≤ 50 path.
    # Let me be more precise: 50 / 0.587 ≈ 85.18
    # So (0, 85, 0) gives lum = 49.895 < 50 → composites
    png = _make_rgba_png(3, 3, [(0, 85, 0, 255)] * 9)
    result = _prepare_logo_for_braille(png)

    # Must go through the composite path (avg_lum ≈ 49.9 ≤ 50)
    assert result != png

    # Verify the result is RGB (composited onto white background)
    buf = io.BytesIO(result)
    img = Image.open(buf)
    assert img.mode == "RGB", f"Expected RGB mode, got {img.mode}"


def test_prepare_braille_dark_logo_on_partial_transparency() -> None:
    """Dark logo with mixed transparent/opaque pixels → composites correctly.

    Tests the scenario that triggered the real bug: a logo that has both
    visible dark pixels AND some fully transparent pixels. The luminance
    calculation should only count visible (alpha > 10) pixels, but the
    composite should use the full alpha channel so the transparent parts
    become white.
    """
    # 3×3 image: center pixel is black opaque, corners are transparent
    # Row 0: transparent, transparent, transparent
    # Row 1: transparent, (0,0,0,255), transparent
    # Row 2: transparent, transparent, transparent
    pixels = [(0, 0, 0, 0)] * 9
    pixels[4] = (0, 0, 0, 255)  # center pixel (index 4 in row-major 3×3)

    png = _make_rgba_png(3, 3, pixels)
    result = _prepare_logo_for_braille(png)

    # Must go through composite path (one visible dark pixel)
    assert result != png

    buf = io.BytesIO(result)
    img = Image.open(buf)
    assert img.mode == "RGB"
    # Center pixel should be black
    assert img.getpixel((1, 1)) == (0, 0, 0)
    # Corner pixels should be white (composited from transparent)
    assert img.getpixel((0, 0)) == (255, 255, 255), (
        f"Expected white corner, got {img.getpixel((0, 0))}"
    )
