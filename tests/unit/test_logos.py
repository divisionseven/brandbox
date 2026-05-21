"""Tests for brandbox.logos — domain extraction, image processing, fetch, and cache."""

from __future__ import annotations

import builtins
import io
from collections import namedtuple
from pathlib import Path
from typing import Any

import pytest
import requests
from PIL import Image
from pytest_mock import MockerFixture

from brandbox.logos import (
    CANVAS_SIZE,
    _autocrop_alpha_padding,
    _fetch_raw,
    _miss_path,
    _png_path,
    clear_cache,
    get_logo,
    is_known_miss,
    is_personal_domain,
    logo_to_png,
    root_domain,
)

# ── cairosvg availability check ───────────────────────────────────────────
try:
    import cairosvg  # noqa: F401 — import is for availability check only

    CAIRO_AVAILABLE = True
except (ImportError, OSError):
    CAIRO_AVAILABLE = False

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ExtractResult = namedtuple("ExtractResult", ["subdomain", "domain", "suffix"])


def _large_png_bytes() -> bytes:
    """Create a valid RGBA PNG image for _fetch_raw test fixtures."""
    img = Image.new("RGBA", (300, 300))
    pixels = img.load()
    assert pixels is not None, "PixelAccess should not be None for a new image"
    for x in range(300):
        for y in range(300):
            pixels[x, y] = (x * 2 % 256, y * 2 % 256, (x + y) % 256, 255)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()
    assert len(data) > 400, f"Test PNG too small: {len(data)} bytes"
    return data


_VALID_LARGE_PNG = _large_png_bytes()


@pytest.fixture(autouse=True)
def _mock_svg_logo(mocker: MockerFixture) -> None:
    """Prevent _fetch_svg_logo from hitting real SVG CDNs during tests."""
    mocker.patch("brandbox.logos._fetch_svg_logo", return_value=(None, None))


# ---------------------------------------------------------------------------
# Domain extraction: root_domain()
# ---------------------------------------------------------------------------


class TestRootDomain:
    """Tests for root_domain() — extracting the registrable root domain."""

    def test_standard_email_returns_domain(self, mocker: MockerFixture) -> None:
        """Standard email alice@company.com → company.com."""
        # Arrange
        mocker.patch(
            "brandbox.logos.tldextract.extract",
            return_value=ExtractResult("", "company", "com"),
        )

        # Act
        result = root_domain("alice@company.com")

        # Assert
        assert result == "company.com"

    def test_email_with_subdomain_returns_root_domain(self, mocker: MockerFixture) -> None:
        """Email with subdomain bob@sub.example.co.uk → example.co.uk."""
        # Arrange
        mocker.patch(
            "brandbox.logos.tldextract.extract",
            return_value=ExtractResult("sub", "example", "co.uk"),
        )

        # Act
        result = root_domain("bob@sub.example.co.uk")

        # Assert
        assert result == "example.co.uk"

    def test_plain_domain_passes_through(self, mocker: MockerFixture) -> None:
        """Plain domain example.com → example.com."""
        # Arrange
        mocker.patch(
            "brandbox.logos.tldextract.extract",
            return_value=ExtractResult("", "example", "com"),
        )

        # Act
        result = root_domain("example.com")

        # Assert
        assert result == "example.com"

    def test_email_with_plus_tag_extracts_domain(self, mocker: MockerFixture) -> None:
        """Email with +tag user+tag@domain.com → domain.com."""
        # Arrange
        mocker.patch(
            "brandbox.logos.tldextract.extract",
            return_value=ExtractResult("", "domain", "com"),
        )

        # Act
        result = root_domain("user+tag@domain.com")

        # Assert
        assert result == "domain.com"

    def test_idn_domain_returns_unicode(self, mocker: MockerFixture) -> None:
        """Internationalised domain (IDN) works with Unicode characters."""
        # Arrange
        mocker.patch(
            "brandbox.logos.tldextract.extract",
            return_value=ExtractResult("", "münchen", "de"),
        )

        # Act
        result = root_domain("user@münchen.de")

        # Assert
        assert result == "münchen.de"

    def test_empty_string_returns_none(self, mocker: MockerFixture) -> None:
        """Empty string input returns None."""
        # Arrange
        mocker.patch(
            "brandbox.logos.tldextract.extract",
            return_value=ExtractResult("", "", ""),
        )

        # Act
        result = root_domain("")

        # Assert
        assert result is None

    def test_only_at_symbol_returns_none(self, mocker: MockerFixture) -> None:
        """Input containing just '@' returns None (empty host after split)."""
        # Arrange
        mock_extract = mocker.patch("brandbox.logos.tldextract.extract")
        mock_extract.return_value = ExtractResult("", "", "")

        # Act
        result = root_domain("@")

        # Assert
        assert result is None
        # The host passed to extract should be empty (splits to '' on @)
        assert mock_extract.call_args[0][0] == ""

    def test_whitespace_is_stripped(self, mocker: MockerFixture) -> None:
        """Leading/trailing whitespace is stripped before extraction."""
        # Arrange
        mocker.patch(
            "brandbox.logos.tldextract.extract",
            return_value=ExtractResult("", "company", "com"),
        )

        # Act
        result = root_domain("  alice@company.com  ")

        # Assert
        assert result == "company.com"

    def test_input_is_lowered(self, mocker: MockerFixture) -> None:
        """Input is lowercased before extraction."""
        # Arrange
        mock_extract = mocker.patch("brandbox.logos.tldextract.extract")
        mock_extract.return_value = ExtractResult("", "company", "com")

        # Act
        root_domain("ALICE@Company.COM")

        # Assert
        assert mock_extract.call_args[0][0] == "company.com"


# ---------------------------------------------------------------------------
# Personal domain detection: is_personal_domain()
# ---------------------------------------------------------------------------


class TestIsPersonalDomain:
    """Tests for is_personal_domain()."""

    def test_known_personal_domain_returns_true(self) -> None:
        """'gmail.com' is a known personal domain."""
        # Act
        result = is_personal_domain("gmail.com")

        # Assert
        assert result is True

    def test_yahoo_com_is_personal(self) -> None:
        """'yahoo.com' is a known personal domain."""
        # Act
        result = is_personal_domain("yahoo.com")

        # Assert
        assert result is True

    def test_company_domain_returns_false(self) -> None:
        """'company.com' is not a personal domain."""
        # Act
        result = is_personal_domain("company.com")

        # Assert
        assert result is False

    def test_empty_string_returns_false(self) -> None:
        """Empty string is not in the skip set."""
        # Act
        result = is_personal_domain("")

        # Assert
        assert result is False

    def test_case_sensitive_returns_false(self) -> None:
        """Comparison is case-sensitive; 'Gmail.com' is not in the lowercase set."""
        # Act
        result = is_personal_domain("Gmail.com")

        # Assert
        assert result is False


# ---------------------------------------------------------------------------
# Domain → SVG slug: _domain_to_slug()
# ---------------------------------------------------------------------------


class TestDomainToSlug:
    """Tests for _domain_to_slug() — domain → SVG icon slug conversion."""

    def test_standard_domain(self) -> None:
        """stripe.com → stripe."""
        from brandbox.logos import _domain_to_slug

        assert _domain_to_slug("stripe.com") == "stripe"

    def test_domain_with_subdomain(self) -> None:
        """mail.stripe.com → stripe."""
        from brandbox.logos import _domain_to_slug

        assert _domain_to_slug("mail.stripe.com") == "stripe"

    def test_dot_tld_domain(self) -> None:
        """linear.app → linear (via SLUG_OVERRIDES)."""
        from brandbox.logos import _domain_to_slug

        assert _domain_to_slug("linear.app") == "linear"

    def test_empty_domain_returns_none(self) -> None:
        """Empty string returns None."""
        from brandbox.logos import _domain_to_slug

        assert _domain_to_slug("") is None

    def test_minimal_domain(self) -> None:
        """Single-part input 'localhost' returns None."""
        from brandbox.logos import _domain_to_slug

        assert _domain_to_slug("localhost") is None

    def test_case_insensitive(self) -> None:
        """Stripe.Com → stripe (input is lowered)."""
        from brandbox.logos import _domain_to_slug

        assert _domain_to_slug("Stripe.Com") == "stripe"

    def test_domain_with_hyphen(self) -> None:
        """mega-corp.co.uk → mega-corp."""
        from brandbox.logos import _domain_to_slug

        assert _domain_to_slug("mega-corp.co.uk") == "mega-corp"


# ---------------------------------------------------------------------------
# Path helpers: _png_path() and _miss_path()
# ---------------------------------------------------------------------------


class TestPngPath:
    """Tests for _png_path()."""

    def test_returns_path_with_png_extension(self, cache_dir: Path) -> None:
        """_png_path returns a path with .png extension."""
        # Act
        result = _png_path(cache_dir, "stripe.com")

        # Assert
        assert result == cache_dir / "stripe.com.png"
        assert result.suffix == ".png"

    def test_handles_domain_with_special_chars(self, cache_dir: Path) -> None:
        """_png_path handles domains with unusual characters."""
        # Act
        result = _png_path(cache_dir, "some-domain.io")

        # Assert
        assert result == cache_dir / "some-domain.io.png"


class TestMissPath:
    """Tests for _miss_path()."""

    def test_returns_path_with_miss_extension(self, cache_dir: Path) -> None:
        """_miss_path returns a path with .miss extension."""
        # Act
        result = _miss_path(cache_dir, "stripe.com")

        # Assert
        assert result == cache_dir / "stripe.com.miss"
        assert result.suffix == ".miss"

    def test_handles_domain_with_special_chars(self, cache_dir: Path) -> None:
        """_miss_path handles domains with unusual characters."""
        # Act
        result = _miss_path(cache_dir, "some-domain.io")

        # Assert
        assert result == cache_dir / "some-domain.io.miss"


# ---------------------------------------------------------------------------
# Cache sentinel: is_known_miss()
# ---------------------------------------------------------------------------


class TestIsKnownMiss:
    """Tests for is_known_miss()."""

    def test_miss_file_exists_returns_true(self, cache_dir: Path) -> None:
        """When a .miss file exists, the domain is a known miss."""
        # Arrange
        (cache_dir / "stripe.com.miss").touch()

        # Act
        result = is_known_miss(cache_dir, "stripe.com")

        # Assert
        assert result is True

    def test_miss_file_absent_returns_false(self, cache_dir: Path) -> None:
        """When no .miss file exists, the domain is not a known miss."""
        # Act
        result = is_known_miss(cache_dir, "stripe.com")

        # Assert
        assert result is False


# ---------------------------------------------------------------------------
# Image processing: _autocrop_alpha_padding()
# ---------------------------------------------------------------------------


class TestAutocropAlphaPadding:
    """Tests for _autocrop_alpha_padding()."""

    def test_rgba_with_padding_crops(self) -> None:
        """RGBA image with transparent borders is cropped to non-transparent area."""
        # Arrange
        img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        for x in range(25, 75):
            for y in range(25, 75):
                img.putpixel((x, y), (255, 0, 0, 255))

        # Act
        cropped, was_cropped = _autocrop_alpha_padding(img)

        # Assert
        assert was_cropped is True
        assert cropped.size == (50, 50)

    def test_rgba_no_padding_returns_unchanged(self) -> None:
        """RGBA image with no transparent padding is returned unchanged."""
        # Arrange
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 255))

        # Act
        cropped, was_cropped = _autocrop_alpha_padding(img)

        # Assert
        assert was_cropped is False
        assert cropped is img

    def test_rgb_mode_returns_unchanged(self) -> None:
        """Non-RGBA image (RGB) is returned unchanged with was_cropped=False."""
        # Arrange
        img = Image.new("RGB", (100, 100), (255, 0, 0))

        # Act
        cropped, was_cropped = _autocrop_alpha_padding(img)

        # Assert
        assert was_cropped is False
        assert cropped is img

    def test_fully_transparent_returns_unchanged(self) -> None:
        """Fully transparent RGBA image is returned unchanged (bbox is None)."""
        # Arrange
        img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))

        # Act
        cropped, was_cropped = _autocrop_alpha_padding(img)

        # Assert
        assert was_cropped is False
        assert cropped is img

    def test_single_opaque_pixel_crops_to_one_by_one(self) -> None:
        """Image with a single non-transparent pixel crops to 1x1."""
        # Arrange
        img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        img.putpixel((50, 50), (0, 255, 0, 255))

        # Act
        cropped, was_cropped = _autocrop_alpha_padding(img)

        # Assert
        assert was_cropped is True
        assert cropped.size == (1, 1)


# ---------------------------------------------------------------------------
# Image processing: logo_to_png()
# ---------------------------------------------------------------------------


class TestLogoToPng:
    """Tests for logo_to_png()."""

    def test_valid_rgb_bytes_returns_rgba_png(self) -> None:
        """Valid RGB image bytes are converted to a square RGBA PNG."""
        # Arrange
        img = Image.new("RGB", (50, 50), (0, 100, 200))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        input_bytes = buf.getvalue()

        # Act
        result = logo_to_png(input_bytes)

        # Assert
        assert result is not None
        assert isinstance(result, bytes)
        # The result should be a valid PNG, RGBA, at CANVAS_SIZE
        result_img = Image.open(io.BytesIO(result))
        assert result_img.format == "PNG"
        assert result_img.mode == "RGBA"
        assert result_img.size == (CANVAS_SIZE, CANVAS_SIZE)

        # Verify the 50×50 image (upscaled) fills most of the canvas
        alpha_result = result_img.split()[3]
        bbox_result = alpha_result.getbbox()
        assert bbox_result is not None
        bbox_width = bbox_result[2] - bbox_result[0]
        bbox_height = bbox_result[3] - bbox_result[1]
        assert bbox_width >= 190  # at least 95% of canvas width
        assert bbox_height >= 190  # at least 95% of canvas height

    def test_empty_bytes_returns_none(self) -> None:
        """Empty bytes input returns None."""
        # Act
        result = logo_to_png(b"")

        # Assert
        assert result is None

    def test_garbage_bytes_returns_none(self) -> None:
        """Garbage (non-image) bytes return None."""
        # Act
        result = logo_to_png(b"this is not an image file")

        # Assert
        assert result is None

    def test_tiny_image_is_upscaled_to_fill_canvas(self) -> None:
        """A tiny 24×24 image (like SimpleIcons rasterization) gets upscaled to fill the canvas."""
        img = Image.new("RGBA", (24, 24), (255, 0, 0, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        raw_bytes = buf.getvalue()

        result = logo_to_png(raw_bytes)
        assert result is not None

        result_img = Image.open(io.BytesIO(result))
        assert result_img.size == (CANVAS_SIZE, CANVAS_SIZE)
        assert result_img.mode == "RGBA"

        # Verify content fills the canvas (not a tiny 24×24 speck)
        alpha = result_img.split()[3]
        bbox = alpha.getbbox()
        assert bbox is not None
        bbox_w = bbox[2] - bbox[0]
        bbox_h = bbox[3] - bbox[1]
        assert bbox_w >= 190  # fills ≥95% of canvas
        assert bbox_h >= 190


# ---------------------------------------------------------------------------
# SVG logo fetching: _fetch_svg_logo()
# ---------------------------------------------------------------------------


class TestFetchSvgLogo:
    """Tests for _fetch_svg_logo() — SVG logo fetching and rasterization."""

    # Override the module-level _mock_svg_logo fixture: we want the real function.
    @pytest.fixture(autouse=True)
    def _mock_svg_logo(self) -> None:
        """Don't mock _fetch_svg_logo — we test the real function here."""

    SVG_CONTENT = (
        b"<svg xmlns='http://www.w3.org/2000/svg'><rect width='100' height='100' fill='red'/></svg>"
    )

    @staticmethod
    def _mock_cairosvg(mocker: MockerFixture) -> None:
        """Replace cairosvg in sys.modules so _fetch_svg_logo uses a mock."""
        mock_cairosvg = mocker.MagicMock()
        mock_cairosvg.svg2png.return_value = b"x" * 100
        mocker.patch.dict("sys.modules", {"cairosvg": mock_cairosvg})

    def test_first_source_returns_svg(self, mocker: MockerFixture) -> None:
        """When SimpleIcons returns valid SVG, PNG bytes are returned."""
        from brandbox.logos import _fetch_svg_logo

        mock_get = mocker.patch("brandbox.logos.requests.get")
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = self.SVG_CONTENT

        self._mock_cairosvg(mocker)
        result = _fetch_svg_logo("stripe.com")
        assert result[0] is not None

    def test_all_svg_sources_fail_returns_none(self, mocker: MockerFixture) -> None:
        """When all SVG sources return 404, returns (None, None)."""
        from brandbox.logos import _fetch_svg_logo

        mock_get = mocker.patch("brandbox.logos.requests.get")
        mock_get.return_value.status_code = 404
        mock_get.return_value.content = b""

        result = _fetch_svg_logo("stripe.com")
        assert result == (None, None)

    def test_non_svg_response_skipped(self, mocker: MockerFixture) -> None:
        """HTML response (starts with <html) is skipped, next source tried."""
        from brandbox.logos import _fetch_svg_logo

        mock_get = mocker.patch("brandbox.logos.requests.get")
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b"<html><body>error</body></html>"

        result = _fetch_svg_logo("stripe.com")
        assert result == (None, None)

    def test_small_svg_accepted(self, mocker: MockerFixture) -> None:
        """Very small SVG (147 bytes, like Vercel) is accepted — no min-size filter."""
        from brandbox.logos import _fetch_svg_logo

        small_svg = b"<svg viewBox='0 0 24 24'><path d='M0 0h24v24H0z'/></svg>"
        mock_get = mocker.patch("brandbox.logos.requests.get")
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = small_svg

        self._mock_cairosvg(mocker)
        result = _fetch_svg_logo("vercel.com")
        assert result[0] is not None

    def test_slug_none_returns_none(self, mocker: MockerFixture) -> None:
        """When domain is unparseable, returns None without making HTTP calls."""
        from brandbox.logos import _fetch_svg_logo

        mock_get = mocker.patch("brandbox.logos.requests.get")
        result = _fetch_svg_logo("")
        assert result == (None, None)
        mock_get.assert_not_called()

    def test_source_exception_continues(self, mocker: MockerFixture) -> None:
        """When first source raises exception, next source is tried."""
        from brandbox.logos import _fetch_svg_logo

        mocker.patch(
            "brandbox.logos.requests.get",
            side_effect=requests.RequestException("Connection error"),
        )

        result = _fetch_svg_logo("stripe.com")
        assert result == (None, None)

    def test_cairosvg_missing_returns_none(self, mocker: MockerFixture) -> None:
        """When cairosvg is not installed, returns None gracefully."""
        from brandbox.logos import _fetch_svg_logo

        # Make requests.get return valid SVG
        mock_get = mocker.patch("brandbox.logos.requests.get")
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = self.SVG_CONTENT

        # Raise ImportError only for cairosvg; delegate everything else to real __import__
        original_import = builtins.__import__

        def mock_import(name: str, *args: Any) -> object:
            if name == "cairosvg":
                raise ImportError("No module named cairosvg")
            return original_import(name, *args)

        mocker.patch("builtins.__import__", side_effect=mock_import)

        result = _fetch_svg_logo("stripe.com")
        assert result == (None, None)

    def test_svg_sources_ordered_correctly(self) -> None:
        """SVG_SOURCES has SimpleIcons first, VectorLogo second."""
        from brandbox.logos import SVG_SOURCES

        assert "simpleicons" in SVG_SOURCES[0]
        assert "vectorlogo" in SVG_SOURCES[1]


# ---------------------------------------------------------------------------
# SVG transparency: cairosvg rasterization produces real alpha
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not CAIRO_AVAILABLE, reason="cairosvg/system cairo not available")
class TestSvgTransparency:
    """Tests that SVG-originated PNGs have real alpha transparency."""

    SVG_RED_CIRCLE = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r="40" fill="red"/>
    </svg>"""

    def test_svg_originated_png_has_real_alpha(self) -> None:
        """SVG→PNG rasterization produces RGBA with transparent pixels."""
        import cairosvg

        png_bytes = cairosvg.svg2png(bytestring=self.SVG_RED_CIRCLE)
        assert png_bytes is not None
        img = Image.open(io.BytesIO(png_bytes))
        assert img.mode == "RGBA"
        alpha = img.split()[3]
        assert alpha.getextrema()[0] == 0, "SVG-originated PNG must have transparent pixels"

    def test_svg_png_processed_through_logo_to_png(self) -> None:
        """SVG→PNG → logo_to_png produces valid 200×200 RGBA output."""
        import cairosvg

        from brandbox.logos import logo_to_png

        png_bytes = cairosvg.svg2png(bytestring=self.SVG_RED_CIRCLE)
        assert png_bytes is not None
        result = logo_to_png(png_bytes)
        assert result is not None
        result_img = Image.open(io.BytesIO(result))
        assert result_img.mode == "RGBA"
        assert result_img.size == (200, 200)

        # With the 100×100 circle upscaled to fill 200×200, content fills the canvas
        alpha_result = result_img.split()[3]
        bbox_result = alpha_result.getbbox()
        assert bbox_result is not None
        bbox_width = bbox_result[2] - bbox_result[0]
        bbox_height = bbox_result[3] - bbox_result[1]
        assert bbox_width >= 190
        assert bbox_height >= 190


# ---------------------------------------------------------------------------
# SVG content detection (startswith checks in _fetch_svg_logo)
# ---------------------------------------------------------------------------


class TestSvgDetection:
    """Tests for SVG content detection (_fetch_svg_logo's startswith check)."""

    # Override the module-level _mock_svg_logo fixture: we want the real function.
    @pytest.fixture(autouse=True)
    def _mock_svg_logo(self) -> None:
        """Don't mock _fetch_svg_logo — we test the real function here."""

    @staticmethod
    def _mock_cairosvg(mocker: MockerFixture) -> None:
        """Replace cairosvg in sys.modules so _fetch_svg_logo uses a mock."""
        mock_cairosvg = mocker.MagicMock()
        mock_cairosvg.svg2png.return_value = b"x" * 100
        mocker.patch.dict("sys.modules", {"cairosvg": mock_cairosvg})

    def test_detects_svg_start_tag(self, mocker: MockerFixture) -> None:
        """Content starting with <svg is detected as SVG."""
        from brandbox.logos import _fetch_svg_logo

        mock_get = mocker.patch("brandbox.logos.requests.get")
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b"<svg xmlns='...'><path/></svg>"

        self._mock_cairosvg(mocker)
        result = _fetch_svg_logo("stripe.com")
        assert result[0] is not None

    def test_detects_xml_declaration(self, mocker: MockerFixture) -> None:
        """Content starting with <?xml is detected as SVG."""
        from brandbox.logos import _fetch_svg_logo

        mock_get = mocker.patch("brandbox.logos.requests.get")
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b"<?xml version='1.0'?><svg>...</svg>"

        self._mock_cairosvg(mocker)
        result = _fetch_svg_logo("stripe.com")
        assert result[0] is not None

    def test_rejects_html(self, mocker: MockerFixture) -> None:
        """Content starting with <html is rejected."""
        from brandbox.logos import _fetch_svg_logo

        mock_get = mocker.patch("brandbox.logos.requests.get")
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b"<html><body>Not SVG</body></html>"

        result = _fetch_svg_logo("stripe.com")
        assert result == (None, None)

    def test_rejects_empty(self, mocker: MockerFixture) -> None:
        """Empty content is rejected."""
        from brandbox.logos import _fetch_svg_logo

        mock_get = mocker.patch("brandbox.logos.requests.get")
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b""

        result = _fetch_svg_logo("stripe.com")
        assert result == (None, None)


# ---------------------------------------------------------------------------
# Fetching: _fetch_raw()
# ---------------------------------------------------------------------------


class TestFetchRaw:
    """Tests for _fetch_raw()."""

    def test_first_source_returns_valid_image(self, mocker: MockerFixture) -> None:
        """When the first source returns valid image data, those bytes are returned."""
        # Arrange
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.content = _VALID_LARGE_PNG

        mock_get = mocker.patch("brandbox.logos.requests.get", return_value=mock_response)

        # Act
        result = _fetch_raw("stripe.com")

        # Assert
        assert result[0] == _VALID_LARGE_PNG
        assert mock_get.call_count >= 1

    def test_third_source_succeeds_after_failures(self, mocker: MockerFixture) -> None:
        """When the first two sources fail, the third is tried and returned."""
        # Arrange
        success = mocker.Mock()
        success.status_code = 200
        success.content = _VALID_LARGE_PNG

        failed = mocker.Mock()
        failed.status_code = 404
        failed.content = b""

        mock_get = mocker.patch(
            "brandbox.logos.requests.get",
            side_effect=[failed, failed, success],
        )

        # Act
        result = _fetch_raw("stripe.com")

        # Assert
        assert result[0] == _VALID_LARGE_PNG
        assert mock_get.call_count == 3

    def test_all_sources_fail_returns_none(self, mocker: MockerFixture) -> None:
        """When all sources raise or return errors, returns None."""
        # Arrange
        mock_get = mocker.patch(
            "brandbox.logos.requests.get",
            side_effect=requests.RequestException("Connection error"),
        )

        # Act
        result = _fetch_raw("stripe.com")

        # Assert
        assert result == (None, None)
        assert mock_get.call_count == 4

    def test_response_too_small_skips_source(self, mocker: MockerFixture) -> None:
        """Content ≤800 bytes is treated as invalid and the next source is tried."""
        # Arrange
        small = mocker.Mock()
        small.status_code = 200
        small.content = b"\x00" * 800  # exactly 800 — not > 800

        success = mocker.Mock()
        success.status_code = 200
        success.content = _VALID_LARGE_PNG

        mock_get = mocker.patch(
            "brandbox.logos.requests.get",
            side_effect=[small, success],
        )

        # Act
        result = _fetch_raw("stripe.com")

        # Assert
        assert result[0] == _VALID_LARGE_PNG
        assert mock_get.call_count == 2


# ---------------------------------------------------------------------------
# Pipeline: get_logo()
# ---------------------------------------------------------------------------


class TestGetLogo:
    """Tests for get_logo() — the cache+fetch pipeline."""

    def test_cache_hit_returns_logo_src(self, cache_dir: Path) -> None:
        """When a .png cache file exists, LogoSrc is returned."""
        # Arrange
        (cache_dir / "stripe.com.png").write_bytes(b"cached-png-data")

        # Act
        result = get_logo(cache_dir, "stripe.com")

        # Assert
        assert result is not None
        assert result.png == b"cached-png-data"
        assert result.source == "cache"
        assert result.dims == "unknown"

    def test_known_miss_returns_none(self, cache_dir: Path) -> None:
        """When a .miss sentinel exists, get_logo returns None without fetching."""
        # Arrange
        (cache_dir / "stripe.com.miss").touch()

        # Act
        result = get_logo(cache_dir, "stripe.com")

        # Assert
        assert result is None

    def test_no_cache_fetch_succeeds_returns_png_and_writes_cache(
        self, cache_dir: Path, mocker: MockerFixture
    ) -> None:
        """When no cache and fetch succeeds, returns PNG bytes and writes cache."""
        # Arrange
        mocker.patch("brandbox.logos._fetch_raw", return_value=(_VALID_LARGE_PNG, "hunter"))

        # Act
        result = get_logo(cache_dir, "stripe.com")

        # Assert
        assert result is not None
        assert result.png is not None
        assert isinstance(result.png, bytes)
        # A .png file should now exist in the cache
        assert (cache_dir / "stripe.com.png").exists()
        # The cached content should match the returned value
        assert (cache_dir / "stripe.com.png").read_bytes() == result.png

    def test_no_cache_fetch_fails_writes_miss(self, cache_dir: Path, mocker: MockerFixture) -> None:
        """When no cache and fetch fails, returns None and writes .miss file."""
        # Arrange
        mocker.patch("brandbox.logos._fetch_raw", return_value=(None, None))

        # Act
        result = get_logo(cache_dir, "stripe.com")

        # Assert
        assert result is None
        assert (cache_dir / "stripe.com.miss").exists()

    def test_no_cache_fetch_returns_invalid_image_writes_miss(
        self, cache_dir: Path, mocker: MockerFixture
    ) -> None:
        """When fetch returns bytes that fail logo_to_png, writes .miss and returns None."""
        # Arrange
        # _fetch_raw validates images, so to get past it with invalid data we
        # need to mock it directly. Return bytes that are valid enough for
        # _fetch_raw's Image.open check but that logo_to_png processes into None.
        # Since logo_to_png catches all exceptions and returns None, any
        # non-image bytes that also pass _fetch_raw's Image.open test would
        # work. The easiest approach: make the image fail during thumbnail/paste.
        # We can instead just mock _fetch_raw to return something _it_ considers
        # valid but that logo_to_png can't handle.
        mocker.patch("brandbox.logos._fetch_raw", return_value=(_VALID_LARGE_PNG, "hunter"))
        # Make logo_to_png return None by patching it
        mocker.patch("brandbox.logos.logo_to_png", return_value=None)

        # Act
        result = get_logo(cache_dir, "stripe.com")

        # Assert
        assert result is None
        assert (cache_dir / "stripe.com.miss").exists()


# ---------------------------------------------------------------------------
# Full fallback chain: SVG → raster integration tests
# ---------------------------------------------------------------------------


class TestFullFallbackChain:
    """Integration tests for SVG→raster fallback in get_logo()."""

    def test_svg_fails_raster_succeeds(self, cache_dir: Path, mocker: MockerFixture) -> None:
        """SVG returns None → raster returns valid PNG → PNG returned."""
        from brandbox.logos import get_logo

        mocker.patch("brandbox.logos._fetch_svg_logo", return_value=(None, None))
        mocker.patch("brandbox.logos._fetch_raw", return_value=(_VALID_LARGE_PNG, "hunter"))

        result = get_logo(cache_dir, "stripe.com")
        assert result is not None
        assert result.png is not None

    def test_svg_succeeds_raster_not_called(self, cache_dir: Path, mocker: MockerFixture) -> None:
        """SVG returns PNG bytes → _fetch_raw is NOT called."""
        from brandbox.logos import get_logo

        mocker.patch(
            "brandbox.logos._fetch_svg_logo", return_value=(_VALID_LARGE_PNG, "simpleicons:stripe")
        )
        mock_raw = mocker.patch("brandbox.logos._fetch_raw")

        result = get_logo(cache_dir, "stripe.com")
        assert result is not None
        assert result.png is not None
        mock_raw.assert_not_called()

    def test_both_fail_writes_miss(self, cache_dir: Path, mocker: MockerFixture) -> None:
        """Both SVG and raster fail → None returned and .miss file written."""
        from brandbox.logos import get_logo, is_known_miss

        mocker.patch("brandbox.logos._fetch_svg_logo", return_value=(None, None))
        mocker.patch("brandbox.logos._fetch_raw", return_value=(None, None))

        result = get_logo(cache_dir, "stripe.com")
        assert result is None
        assert is_known_miss(cache_dir, "stripe.com")


# ---------------------------------------------------------------------------
# Cache management: clear_cache()
# ---------------------------------------------------------------------------


class TestClearCache:
    """Tests for clear_cache()."""

    def test_removes_png_and_miss_files(self, cache_dir: Path) -> None:
        """clear_cache removes .png and .miss files from the cache directory."""
        # Arrange
        (cache_dir / "stripe.com.png").write_text("data")
        (cache_dir / "github.com.png").write_text("data")
        (cache_dir / "stripe.com.miss").touch()

        # Act
        removed = clear_cache(cache_dir)

        # Assert
        assert removed == 3
        assert not list(cache_dir.iterdir()), "Cache dir should be empty"

    def test_preserves_gitkeep(self, cache_dir: Path) -> None:
        """clear_cache preserves a .gitkeep file and does not count it."""
        # Arrange
        (cache_dir / ".gitkeep").write_text("")
        (cache_dir / "logo.png").write_text("data")

        # Act
        removed = clear_cache(cache_dir)

        # Assert
        assert removed == 1
        assert (cache_dir / ".gitkeep").exists()

    def test_empty_directory_returns_zero(self, cache_dir: Path) -> None:
        """clear_cache on an empty directory returns 0."""
        # Act
        removed = clear_cache(cache_dir)

        # Assert
        assert removed == 0

    def test_returns_correct_count_mixed_files(self, cache_dir: Path) -> None:
        """clear_cache returns the correct count when multiple file types exist."""
        # Arrange
        (cache_dir / "a.png").write_text("a")
        (cache_dir / "b.png").write_text("b")
        (cache_dir / "c.png").write_text("c")
        (cache_dir / "d.miss").touch()
        (cache_dir / "e.miss").touch()
        (cache_dir / ".gitkeep").touch()  # should be ignored

        # Act
        removed = clear_cache(cache_dir)

        # Assert
        assert removed == 5
