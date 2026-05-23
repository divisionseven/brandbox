# Changelog

All notable changes to brandbox are documented here.

This project follows [Semantic Versioning](https://semver.org) and
[Conventional Commits](https://www.conventionalcommits.org).

---

## [Unreleased]

## [0.3.0] — 2026-05-22

### Added

- **Interactive logo selection**: New `--interactive` flag fetches all 7 logo sources in
  parallel per domain, renders candidate logos as terminal braille art via `artty`, and
  lets users pick with arrow keys when multiple logos are found. Falls back to
  `[auto: only 1 source]` when a single logo is found — no prompt needed.
- **`get_all_logos()`**: New parallel logo fetch function in `logos.py` — tries all
  7 sources concurrently via `ThreadPoolExecutor` and returns every successful
  `LogoSrc` instead of stopping at the first match.
- **Dependencies**: `artty >= 0.1.6` (PNG-to-braille rendering), `questionary >= 2.0.0`
  (arrow-key selection prompt).

### Fixed

- **Empty braille panels for dark SVG logos (SimpleIcons, VectorLogoZone, Wikimedia)**:
  Dark/black SVG logos (e.g., SimpleIcons squarespace with `fill="#000000"`) produced empty
  braille output because artty composites transparent→(1,1,1) and its threshold=50 treats both
  the dark logo (luminance ~0) and composited background (luminance ~1) as background → zero
  braille dots. Added `_prepare_logo_for_braille()` that detects dark logos (avg luminance
  < 50) and composites them onto a white background before passing to artty. This makes them
  render as negative-space braille (background = dots, logo = blank shape), consistent with
  raster-source logos. Some logo panels appeared completely empty (no braille characters) in
  the interactive selector.

## [0.2.0] — 2026-05-20

### Added

- **How It Works doc**: New `docs/how-it-works.md` — a technical deep dive explaining
  the logo pipeline, SVG rasterization, image processing, contact discovery, provider
  architecture, and key design decisions.
- **Content-fill test**: `test_tiny_image_is_upscaled_to_fill_canvas` verifies a 24×24
  input is upscaled to fill ≥95% of the 200×200 canvas.
- **Alpha bbox assertions**: Existing tests `test_valid_rgb_bytes_returns_rgba_png` and
  `test_svg_png_processed_through_logo_to_png` now verify output content fills the canvas.
- **SVG logo sources**: Added SimpleIcons, VectorLogo.Zone, and Wikimedia Commons as
  primary logo sources. SVGs are inherently transparent — logos now display without
  white backgrounds. Falls back to raster APIs (Hunter, DeBounce, LogoKit, Brandfetch)
  when SVG coverage is unavailable.
- **Logo provider label**: New `--logo-provider` flag shows the logo source name
  (e.g. `[hunter]`, `[simpleicons]`) next to each logo in the progress output.
  Default off — no output change unless flag is used.
- **Logo source tracking**: `get_logo()` now returns a `LogoSrc` namedtuple with
  `.png`, `.source`, and `.dims` fields for internal caller awareness.
- Professional test suite with 241 unit tests and 99.47% code coverage
  (state, logos, CLI, Microsoft, Google, base, and provider registry modules)
- GitHub Actions CI workflow (Python 3.11, 3.12, 3.13 with ruff, mypy, pytest)
- pytest and coverage configuration in pyproject.toml (fail_under=90, branch=true)
- shields.io badges for CI status and supported platforms in README

### Changed

- **README and documentation**: Updated pipeline description, added SVG
  high-resolution rendering note, added processing time guidance, and linked to
  `docs/how-it-works.md`.
- **Processing stage headers**: Added Rich `Rule` section headers
  (`Inbox Scan: Creating contacts from recent senders` and
  `Contact Photos: Setting logos on existing contacts`) to separate the two
  processing phases so users can see what's happening at each stage.
- **Logo scaling**: Replaced `PIL.Image.thumbnail()` (downscale-only) with proportional
  `resize()` in `logo_to_png()`. Images smaller than the canvas are now properly upscaled
  to fill the output, not left as tiny specs on a 200×200 transparent canvas.
- **Removed repadding**: Deleted `REPAD_PX = 1` and its logic. After auto-crop strips
  transparent padding, no padding is re-added — logos fill the canvas maximally.
- **Module docstring**: Updated to reflect the current pipeline (no more repadding step).
- **Logo pipeline**: Replaced Google Favicon fallback with higher-quality logo sources
  (Hunter.io, DeBounce). New SVG-first ordering: SVG sources tried before raster,
  guaranteeing transparent logos when SVG coverage is available.
- **Scan-inbox progress**: Replaced static `console.status()` spinner with a full
  Rich `Progress` bar showing per-sender progress, `MofNCompleteColumn`, and elapsed
  time during the contact-creation loop.
- **Domain deduplication**: Logo is now fetched once per unique domain, not once per
  sender email — dramatically reducing redundant API calls.
- **Logo pipeline**: Replaced Google Favicon fallback with higher-quality logo sources.
  Added Hunter.io and DeBounce as primary logo sources (try-before LogoKit/Brandfetch),
  delivering proper 128×128–512×512 company logos instead of blurred favicons.
  Favicon fallback removed entirely.
- Complete README rewrite with centered header, logo placeholder, badges row,
  navigation links, and ASCII box-drawing flowchart
- Strict type annotations on all function signatures for mypy compliance
- Type annotations in test files for Pyright/Pylance compliance

### Fixed

- **Logo braille preview rendered tiny with excessive blank space**: Logo PNGs were centered on a
  200×200 transparent canvas by the fetch pipeline. `artty` composites transparent → (1,1,1) before
  calling `getbbox()`, so the bounding box always covered the full canvas and the logo rendered very
  small with wasted terminal space. Added `_autocrop_logo_png()` helper that uses Pillow
  `Image.getbbox()` on the alpha channel to crop transparent padding from the PNG bytes before
  passing the image to artty — reused the existing `_autocrop_alpha_padding()` pattern from
  `logos.py`.
- **Raw Rich markup displayed in questionary prompt**: The `questionary.select()` dialog message
  contained Rich markup syntax (`[bold cyan]{domain}[/bold cyan]`), but questionary delegates to
  prompt_toolkit's formatted text system which does not understand Rich markup — brackets and tags
  were rendered as literal text. Removed the inline Rich markup; the question text retains its bold
  weight via the `("question", "bold")` style in the `Style` object, so no visual regression.
- **Raw ANSI color codes visible as text**: `Text.from_ansi()` now wraps the braille art
  output from `artty.image_to_braille()` before passing it to Rich's `Panel()`. Rich
  previously treated raw ANSI escape sequences (`\033[38;2;R;G;Bm`) as plain text rather
  than colour instructions, rendering the codes as visible garbage characters.
- **Distorted braille art in Panel**: `Panel()` received raw ANSI-escaped strings from
  `artty.image_to_braille()`, causing Rich's `cell_len()` to count ANSI escape characters
  (~20 per colour span) as visible cells, inflating the panel width and breaking the
  layout. Fixed by wrapping with `Text.from_ansi(artty_output)` so Rich parses the codes
  into native styled spans with correct cell widths.
- **`use_emojis=False` crashes questionary select**: `questionary.select()` does not
  support a `use_emojis` keyword argument in prompt_toolkit 3.0.52 — passing it raised
  `TypeError: PromptSession.__init__() got an unexpected keyword argument 'use_emojis'`.
  Removed the unsupported kwarg from the interactive selection call.
- **Ugly Ctrl-C stack trace**: Wrapped the account processing loop in
  `try/except KeyboardInterrupt`. Hitting Ctrl-C now prints a clean
  `"Interrupted by user. Exiting..."` message and exits with code 130 instead of
  dumping a raw `KeyboardInterrupt` traceback.
- **SVG logo rendering resolution**: SVGs from SimpleIcons and VectorLogo.Zone now
  rasterize at 400px via `cairosvg.svg2png(output_width=CANVAS_SIZE * 2)`. Previously
  they rendered at their viewBox size (24×24 or 64×64), producing tiny pixelated logos
  when placed on a 200×200 canvas. SVGs are vector graphics — high-res rendering
  keeps them crisp at any output size.
- **Wikimedia Commons 403**: Added `User-Agent: Brandbox/1.0` header to SVG fetch
  requests, which were being blocked by Wikimedia's bot policy.
- **Scan-inbox hang**: Long-running contact creation loop now shows live progress
  instead of a static spinner for 15+ minutes.
- **Zero-contacts progress bar**: When no contacts exist and `--scan-inbox` creates
  new ones, the Stage 4 progress bar no longer shows `0/0`. Contacts are re-fetched
  after scan, and an early return guard handles the empty case.
- **Missing summary counts**: `counts["set"]`, `counts["failed"]`, `counts["no_logo"]`,
  and `counts["domain"]` are now correctly tracked during inbox scan — previously they
  were only updated in the existing-contacts loop.
- **State save batching**: `state.save()` is now called once at the end of the
  scan-inbox loop instead of after every single contact creation.
- `get_recent_senders()` in Microsoft provider now catches `AttributeError`
  when email address value is `None`

## [0.1.0] — 2026-05-18

### Initial release

- Multi-account Microsoft 365 authentication via MSAL device code flow
- Fetches company logos from LogoKit → Brandfetch → Google favicon (in order)
- Auto-crops transparent pixel padding from logos and re-adds uniform padding
- Root domain extraction via `tldextract` — resolves mail prefixes correctly
  (e.g. `mail.whitehouse.gov` → `whitehouse.gov`)
- Uploads logos as PNG contact photos via Microsoft Graph API
- `--scan-inbox`: creates contacts for recent senders — only if a logo exists
- Local PNG cache and processed-contact state for fast re-runs
- Rich terminal UI with progress bars, spinners, and summary tables
- `--dry-run`, `--overwrite`, `--clear-cache`, `--reset-state` flags
- Platform-aware data directory (`~/Library/Application Support/brandbox` on macOS)
