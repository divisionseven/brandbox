"""Tests for brandbox.logos — domain extraction, image processing, fetch, and cache."""

from __future__ import annotations

import io
from collections import namedtuple
from pathlib import Path

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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ExtractResult = namedtuple("ExtractResult", ["subdomain", "domain", "suffix"])


def _large_png_bytes() -> bytes:
    """Create a valid PNG image larger than 800 bytes for _fetch_raw tests."""
    img = Image.new("RGBA", (150, 150))
    pixels = img.load()
    assert pixels is not None, "PixelAccess should not be None for a new image"
    for x in range(150):
        for y in range(150):
            pixels[x, y] = (x * 2 % 256, y * 2 % 256, (x + y) % 256, 255)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()
    assert len(data) > 800, f"Test PNG too small: {len(data)} bytes"
    return data


_VALID_LARGE_PNG = _large_png_bytes()


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
        assert result == _VALID_LARGE_PNG
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
        assert result == _VALID_LARGE_PNG
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
        assert result is None
        assert mock_get.call_count == 3

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
        assert result == _VALID_LARGE_PNG
        assert mock_get.call_count == 2


# ---------------------------------------------------------------------------
# Pipeline: get_logo()
# ---------------------------------------------------------------------------


class TestGetLogo:
    """Tests for get_logo() — the cache+fetch pipeline."""

    def test_cache_hit_returns_cached_bytes(self, cache_dir: Path) -> None:
        """When a .png cache file exists, its bytes are returned directly."""
        # Arrange
        (cache_dir / "stripe.com.png").write_bytes(b"cached-png-data")

        # Act
        result = get_logo(cache_dir, "stripe.com")

        # Assert
        assert result == b"cached-png-data"

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
        mocker.patch("brandbox.logos._fetch_raw", return_value=_VALID_LARGE_PNG)

        # Act
        result = get_logo(cache_dir, "stripe.com")

        # Assert
        assert result is not None
        assert isinstance(result, bytes)
        # A .png file should now exist in the cache
        assert (cache_dir / "stripe.com.png").exists()
        # The cached content should match the returned value
        assert (cache_dir / "stripe.com.png").read_bytes() == result

    def test_no_cache_fetch_fails_writes_miss(self, cache_dir: Path, mocker: MockerFixture) -> None:
        """When no cache and fetch fails, returns None and writes .miss file."""
        # Arrange
        mocker.patch("brandbox.logos._fetch_raw", return_value=None)

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
        mocker.patch("brandbox.logos._fetch_raw", return_value=_VALID_LARGE_PNG)
        # Make logo_to_png return None by patching it
        mocker.patch("brandbox.logos.logo_to_png", return_value=None)

        # Act
        result = get_logo(cache_dir, "stripe.com")

        # Assert
        assert result is None
        assert (cache_dir / "stripe.com.miss").exists()


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
