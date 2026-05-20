# How BrandBox Works

*A technical deep dive into the logo pipeline, contact discovery, and provider architecture*

Running `brandbox --run` triggers a multi-stage pipeline that fetches logos, processes images, discovers contacts, and uploads photos — all with zero configuration beyond authentication. Here's what happens behind the scenes.

## Summary

BrandBox transforms raw company logos into crisp, transparent contact photos through a carefully ordered pipeline of seven sources, SVG-first rasterization, Pillow-based image processing, and a simple sentinel-based cache. The provider-agnostic architecture means the same pipeline works identically for Microsoft 365 and Google accounts — and any future provider that implements the `Provider` interface.

Under the hood, it's a series of deliberate design decisions about source ordering, error isolation, caching strategy, and state management that add up to a tool that *"just works"* even when individual APIs fail.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [The Logo Pipeline](#the-logo-pipeline)
- [Contact Discovery](#contact-discovery)
- [The Inbox Scan (`--scan-inbox`)](#the-inbox-scan---scan-inbox)
- [The Main Run Loop](#the-main-run-loop)
- [State Management](#state-management)
- [Error Handling Philosophy](#error-handling-philosophy)
- [Key Design Decisions](#key-design-decisions)

## Architecture Overview

BrandBox operates in two loosely coupled phases, both orchestrated by the CLI:

1. **The logo pipeline** — a resilient, source-chain system that finds a company logo for a given domain and processes it into a consistent 200×200 RGBA PNG.
2. **The contact management layer** — a provider-agnostic abstraction over Microsoft Graph API and Google People API that discovers contacts, creates new ones, and uploads photos.

The CLI (`cli.py`) is the conductor. It loads state, iterates over all authenticated accounts, and feeds each contact through the logo pipeline followed by the photo upload, with a Rich-powered progress bar for visibility.

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Logo        │     │  Image           │     │  Provider        │
│  Discovery   │ ──▶ │  Processing      │ ──▶ │  Upload          │
│  (7 sources) │     │  (Pillow pipe)   │     │  (Graph/People)  │
└──────────────┘     └──────────────────┘     └──────────────────┘
```

External dependencies are minimal: `requests` for HTTP, `Pillow` for image processing, `tldextract` for domain parsing, `cairosvg` for SVG rasterization (optional), and the provider SDKs (`google-auth-oauthlib`, `msal`). Logos come from seven independent services — no single point of failure.

## The Logo Pipeline

This section covers: [Source Chain](#source-chain--svg-first) · [Domain-to-Slug Conversion](#domain-to-slug-conversion) · [SVG Rasterization](#svg-rasterization-at-2-resolution) · [Raster API Fallbacks](#raster-api-fetching) · [Image Processing Pipeline](#the-image-processing-pipeline-logo_to_png) · [Source Tracking](#source-tracking) · [Caching](#caching)

This is the heart of BrandBox. Given a company domain (e.g. `stripe.com`), the pipeline discovers a logo, rasterizes it, cleans it, and caches the result — all in about one second.

### Source Chain — SVG First

Seven logo sources are tried in strict order. The first one to return a valid image wins:

| Priority | Source                | Type   | URL Format                                                       |
| -------- | --------------------- | ------ | ---------------------------------------------------------------- |
| 1        | **SimpleIcons**       | SVG    | `https://cdn.simpleicons.org/{slug}`                             |
| 2        | **VectorLogo.Zone**   | SVG    | `https://www.vectorlogo.zone/logos/{slug}/{slug}-icon.svg`       |
| 3        | **Wikimedia Commons** | SVG    | `https://commons.wikimedia.org/wiki/Special:FilePath/{filename}` |
| 4        | **Hunter.io**         | Raster | `https://logos.hunter.io/{domain}`                               |
| 5        | **DeBounce**          | Raster | `https://logo.debounce.com/{domain}`                             |
| 6        | **LogoKit**           | Raster | `https://img.logokit.com/{domain}?token=free`                    |
| 7        | **Brandfetch**        | Raster | `https://logo.brandfetch.io/{domain}`                            |

**SVG sources are tried first** for one critical reason: SVGs are inherently transparent. A logo fetched from an SVG source has no background at all, which means it renders perfectly in both light and dark mode. Raster APIs often return JPEGs or opaque PNGs with white backgrounds that look terrible in dark-mode Outlook or Gmail.

Raster APIs serve as fallbacks when SVG coverage is unavailable. They're still high-quality — Hunter, DeBounce, LogoKit, and Brandfetch all return proper company logos (typically 128×128 to 512×512 pixels), not favicons.

### SVG Fetching

The `_fetch_svg_logo()` function iterates through the three SVG sources. For each one, it sends an HTTP GET request with a 10-second timeout. The response is validated:

- Must return HTTP **200**
- Response body must start with `<svg`, `<?xml`, or `<?` — this rejects HTML error pages that some CDNs return as 200

When a valid SVG is found, it's rasterized to PNG at 2× resolution (see below).

### Raster API Fetching

The `_fetch_raw()` function handles the four raster sources. Each response is validated three ways:

- HTTP **200** status
- **Content length > 800 bytes** — rejects placeholder images, error pages, and SVG-based CDN responses
- **Pillow validation** — `Image.open()` must succeed, confirming the bytes represent a real image

All exceptions are caught per-source. A timeout, DNS failure, or 500 error from Hunter never prevents trying DeBounce.

> [!IMPORTANT]
> **Design Decision — SVG-first ordering**: Placing SVGs before raster APIs guarantees transparent-background logos for any company covered by SimpleIcons (~3,000 brands), VectorLogo.Zone (~2,000), or the Wikimedia Commons lookup table. Raster APIs produce opaque images that look wrong in dark mode — SVGs eliminate this problem at the source.

### Domain-to-Slug Conversion

SimpleIcons and VectorLogo.Zone identify brands by **slug** — a lowercase, hypenated identifier like `stripe` (not `stripe.com`) or `mega-corp` (not `mega-corp.co.uk`). The `_domain_to_slug()` function handles this conversion:

```python
def _domain_to_slug(domain: str) -> str | None:
```

It uses `tldextract` to correctly handle multi-part TLDs. Examples:

| Email Domain          | Root Domain       | Slug        | Why                           |
| --------------------- | ----------------- | ----------- | ----------------------------- |
| `john@stripe.com`     | `stripe.com`      | `stripe`    | TLD stripped                  |
| `dev@mega-corp.co.uk` | `mega-corp.co.uk` | `mega-corp` | `tldextract` handles `.co.uk` |
| `user@linear.app`     | `linear.app`      | `linear`    | Via `SLUG_OVERRIDES`          |

### Slug Overrides

Some domains don't map cleanly to their SimpleIcons slug. A small lookup table handles these edge cases:

```python
SLUG_OVERRIDES = {
    "linear.app": "linear",
}
```

Without this, `linear.app` would produce a slug of `app` (because `tldextract` sees `.app` as a TLD), which would fail on SimpleIcons.

> [!TIP]
> `_domain_to_slug()` wraps everything in a try/except and returns `None` on any failure — bad input never crashes the pipeline.

### SVG Rasterization at 2× Resolution

SVGs are vector graphics — resolution-independent by nature. When rasterizing one, there's no reason to render at low resolution. BrandBox renders at **400×400 pixels**, twice the final canvas size:

```python
import cairosvg
raw_png = cairosvg.svg2png(
    bytestring=content,
    output_width=CANVAS_SIZE * 2,  # 400px
)
```

This is a deliberate choice. The old behavior left SVGs at their viewBox size (often 24×24 or 64×64 pixels), producing tiny, pixelated logos when scaled up to the 200×200 canvas. Rendering at 400px gives retina-quality resolution that downsamples beautifully through the LANCZOS filter in the image processing pipeline.

> [!NOTE]
> `cairosvg` uses an **inline import** — `import cairosvg` only executes when an SVG source produces a match. If `cairosvg` is not installed, SVG support silently degrades and the pipeline falls through to the raster sources. This makes SVG support truly optional: the tool works perfectly with only raster API coverage.

### Wikimedia Commons

For domains not covered by SimpleIcons or VectorLogo.Zone, BrandBox checks a small lookup table of Wikimedia Commons SVG filenames:

```python
WIKIMEDIA_FILENAMES = {
    "slack.com": "Slack_Technologies_Logo.svg",
    "linear.app": "Linear_logo.svg",
}
```

This list grows organically as users encounter uncovered domains. The fetch URL uses a special `User-Agent` header (`Brandbox/1.0`) to avoid Wikimedia's bot-blocking policy — a fix for the 403 errors that occurred with the default `requests` user-agent.

The same cairosvg pipeline processes the response: validate as SVG, rasterize at 400px, return PNG bytes.

### The Image Processing Pipeline (`logo_to_png()`)

Once raw logo bytes arrive (from any of the seven sources), they enter `logo_to_png()` — a five-step image processing pipeline that produces a consistent 200×200 RGBA PNG.

```python
def logo_to_png(image_bytes: bytes) -> bytes | None:
```

**Step 1 — Open and convert to RGBA**

Pillow opens the image bytes and immediately converts to RGBA (4 channels: Red, Green, Blue, Alpha). This handles any input format — JPEG, PNG, GIF, WebP — and ensures a consistent 4-channel representation for the rest of the pipeline.

```python
src = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
```

**Step 2 — Auto-crop transparent padding**

Many logos have transparent padding around them — extra empty space baked into the image file. This step finds the tight bounding box of non-zero-alpha pixels and crops to it:

```python
alpha = src.split()[3]
bbox = alpha.getbbox()  # tight bounding box of non-transparent pixels
if bbox and bbox != (0, 0, img.width, img.height):
    src = src.crop(bbox)
```

`alpha.getbbox()` scans the alpha channel and returns the smallest rectangle that contains all non-transparent pixels. If the logo is already flush against the edges, no cropping occurs. Fully transparent images return `None` and pass through unchanged.

**Step 3 — Scale to fill the canvas**

After cropping, the image is scaled to fill the 200×200 canvas while preserving its aspect ratio:

```python
ratio = min(CANVAS_SIZE / src.width, CANVAS_SIZE / src.height)
new_size = (max(1, int(src.width * ratio)), max(1, int(src.height * ratio)))
src = src.resize(new_size, Image.Resampling.LANCZOS)
```

The `min()` formula handles both directions:
- **Wide images**: `200 / width` is the smaller ratio, constraining the width
- **Tall images**: `200 / height` is the smaller ratio, constraining the height

This means small images (e.g., 24×24 favicons) are **upscaled** to fill the canvas, and large images (e.g., 512×512 logos) are **downscaled** to fit within it. The `max(1, ...)` guard prevents zero-dimension images from crashing the pipeline.

LANCZOS resampling provides the highest quality downscaling — especially important for the 400px SVG renders being halved to 200px.

**Step 4 — Center on a transparent canvas**

A fresh 200×200 transparent RGBA canvas is created, and the scaled image is pasted dead-center:

```python
canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
x = (CANVAS_SIZE - src.width) // 2
y = (CANVAS_SIZE - src.height) // 2
canvas.paste(src, (x, y), mask=src.split()[3])
```

The image's own alpha channel is used as the paste **mask** — this preserves anti-aliasing and any internal transparency (e.g., rounded corners, cutout designs).

**Step 5 — Save to PNG bytes**

The final canvas is saved to an in-memory bytes buffer:

```python
buf = io.BytesIO()
canvas.save(buf, format="PNG")
return buf.getvalue()
```

No file I/O — the result is returned as raw bytes, ready to be cached to disk or uploaded directly to the provider API.

> [!IMPORTANT]
> **Design Decision — No repadding**: Earlier versions re-added a 1px transparent border after cropping (`REPAD_PX`). This was removed to maximize usable logo area. After auto-crop strips transparent borders, the logo is scaled to fill the canvas edge-to-edge with no extra padding. The resulting 200×200 PNG fits perfectly as a contact photo.

### Source Tracking

Each processed logo carries provenance metadata via the `LogoSrc` namedtuple:

```python
class LogoSrc(NamedTuple):
    png: bytes
    source: str      # e.g. "simpleicons:stripe", "hunter", "cache", "wikimedia:Slack_Technologies_Logo.svg"
    dims: str        # e.g. "128x128", "400x400"
```

The `source` field flows all the way to the CLI output when `--logo-provider` is enabled. Each completed contact shows a green checkmark, the contact name, the domain, and optionally the logo source label in dim text — for example: Alice Johnson at stripe.com from SimpleIcons, or Bob Smith at acmecorp.com from Hunter.

This is invaluable for debugging which sources produce good or bad logos for which domains.

### Caching

BrandBox maintains two types of cache files per domain in the data directory's `cache/` folder:

| File              | Purpose                                              |
| ----------------- | ---------------------------------------------------- |
| `stripe.com.png`  | Processed 200×200 PNG — ready to upload              |
| `stripe.com.miss` | Zero-byte sentinel — domain has no logo, never retry |

**The `.png` cache** stores the final output of `logo_to_png()`. On subsequent runs, `get_logo()` reads the cached file directly and returns it with `source="cache"` — no HTTP requests, no image processing. The entire lookup takes microseconds.

**The `.miss` sentinel** prevents repeated failed lookups. If all seven sources fail for a domain, a zero-byte `.miss` file is created. The next time the domain is encountered, `is_known_miss()` returns `True` instantly, and the pipeline skips it without making any network calls.

```python
if is_known_miss(cache_dir, domain):
    return None
```

> [!TIP]
> This simple sentinel-file approach requires no database, no complex state management, and survives across sessions. Run `brandbox --clear-cache` to delete all `.png` and `.miss` files and start fresh. The `.gitkeep` file in the cache directory is preserved.

Caching makes repeated runs nearly instant. After the first full run, most lookups hit the cache, and the tool spends its time only on the actual contact photo uploads.

## Contact Discovery

The contact management layer is built around a clean abstract interface, with two concrete implementations.

### Provider Architecture

The `Provider` abstract base class (`providers/base.py`) defines the contract:

```python
class Provider(ABC):
    def start_auth(self) -> dict[str, Any]: ...
    def finish_auth(self, flow: dict[str, Any]) -> str: ...
    def get_accounts(self) -> list[Account]: ...
    def get_token(self, account: Account) -> str: ...
    def get_contacts(self, token: str) -> list[Contact]: ...
    def get_recent_senders(self, token: str, limit: int) -> set[str]: ...
    def create_contact(self, token: str, display_name: str, email: str) -> str | None: ...
    def set_contact_photo(self, token: str, contact_id: str, png: bytes) -> bool: ...
```

The two implementations — `GoogleProvider` and `MicrosoftProvider` — each handle their own authentication flow (different OAuth modalities), pagination strategies, and API endpoints. The CLI never touches any provider-specific code directly.

Provider instances are created by `build_providers()`, which checks environment variables and only instantiates providers with sufficient configuration:

```python
def build_providers(ms_client_id: str, google_creds: Path, token_dir: Path) -> dict[str, Provider]:
```

- If `BRANDBOX_CLIENT_ID` is set → `MicrosoftProvider` is instantiated
- If the Google credentials file exists → `GoogleProvider` is instantiated
- Both can be active simultaneously

Unconfigured providers are silently omitted. A user who only uses Microsoft 365 never needs to touch Google Cloud Console, and vice versa.

### Google Provider

- **Authentication**: OAuth 2.0 desktop flow via `InstalledAppFlow`. A browser window opens for consent; a local callback server handles the redirect. Tokens are saved per-account as `google_{sanitized_email}.json`.
- **Contacts**: `GET people/me/connections` with `pageSize=1000` and `nextPageToken` pagination. Returns all personal contacts with names and email addresses.
- **Recent senders**: The **otherContacts** endpoint (`people/otherContacts`) — a Google-maintained list of people you've interacted with via Gmail but haven't explicitly added as contacts. This is more efficient than scanning individual Gmail messages.
- **Photo upload**: `POST {resourceName}:updateContactPhoto` with the PNG bytes base64-encoded in the JSON body.

> [!NOTE]
> API pagination uses a shared helper `_people_get_paged()` that handles `nextPageToken` iteration transparently. If a single page fails, only that page's data is lost — previously fetched pages are preserved.

### Microsoft Provider

- **Authentication**: MSAL device code flow. A URL and code are displayed in the terminal — no browser required on the same machine. Tokens are stored in a single `microsoft.json` token cache file using `msal.SerializableTokenCache`.
- **Contacts**: `GET /me/contacts` with `$top=999` and `@odata.nextLink` pagination. Returns up to 999 contacts per page.
- **Recent senders**: `GET /me/mailFolders/inbox/messages` sorted by `receivedDateTime desc`, with `$select=from`, capped at 500 messages. Email addresses are extracted from `from.emailAddress.address`.
- **Photo upload**: `PUT /me/contacts/{id}/photo/$value` with raw PNG bytes and `Content-Type: image/png`.

> [!IMPORTANT]
> **Design Decision — Google vs Microsoft auth**: The two providers reflect the constraints of their platforms. Google mandates a browser-based OAuth flow (it's a desktop app requirement in their OAuth policy). Microsoft supports device code flow, which works without a browser on the authenticating machine — ideal for headless setups (servers, CI environments, SSH sessions).

## The Inbox Scan (`--scan-inbox`)

The `--scan-inbox` flag tells BrandBox to create contacts for people who've sent you email but aren't yet in your contacts. Here's exactly what happens:

1. **Fetch existing contacts** from the provider → build a set of known email addresses (lowercased for case-insensitive dedup).

2. **Fetch recent senders** from the inbox → subtract existing contacts → the remainder is `new_senders`.

3. **Group by root domain** — each sender's email is run through `root_domain()`, and senders are grouped by their company domain. This means the logo is fetched **once per unique domain**, not once per sender. If 50 senders all work at `stripe.com`, the logo is fetched exactly once.

   ```python
   domain_senders: dict[str, list[str]] = {}
   for email in sorted(new_senders):
       domain = logos.root_domain(email)
       if not domain or logos.is_personal_domain(domain):
           continue
       domain_senders.setdefault(domain, []).append(email)
   ```

4. **Skip personal email domains** — `gmail.com`, `yahoo.com`, `icloud.com`, `protonmail.com`, and 14 other personal/free email domains are in `SKIP_DOMAINS`. No logo is needed for these, and no contact is created.

5. **For each domain with a logo**: create a contact → upload the photo → track in state.

6. **For domains without a logo**: the domain is skipped (counted as `no_logo`), and a `.miss` sentinel is written so it's never retried.

7. **Batch state save** — `state.save()` is called once at the end of the inbox scan loop, not after every contact. This is different from the main loop, which saves per-contact (since it runs on fewer, existing contacts).

8. **Re-fetch contacts** — after the inbox scan creates new contacts, the contact list is refreshed so the main processing loop includes them in its progress bar totals.

> [!TIP]
> The domain deduplication is the key optimization here. An inbox scan might discover 200 new senders across only 30 unique domains — that's 30 logo fetches instead of 200. With a cold cache, each fetch adds ~1 second, so this saves about 3 minutes of wall time.

## The Main Run Loop

When `--run` is invoked (with or without `--scan-inbox`), the main processing loop handles the existing contacts:

1. **Load state** from `state.json` — tracks which contacts have already been processed per account.

2. **For each account** → **for each contact**:
   - **Skip** if: no email address → personal/invalid domain → no logo in cache (`is_known_miss`) → already processed (contact ID in `account_state`) — unless `--overwrite` is set
   - **Fetch logo** from cache (or, if missing, trigger the full pipeline)
   - **Upload** via `provider.set_contact_photo(token, contact_id, logo.png)`
   - **Save state** — `account_state[contact_id] = domain` written to disk immediately

3. **Rich Progress bar** across all contacts:

   A Rich progress bar shows the current contact being processed, a progress bar with MofN counter, and elapsed time — for example: `Processing contacts ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 147/147 15s`. The display uses five components: a spinner, a text description (the contact's display name), a bar, a MofN counter, and elapsed time.

4. **Summary** at the end:

   A per-account summary shows the breakdown: ✓  118 set  ·  22 already processed  ·  4 no logo  ·  2 personal domain  ·  1 failed

   Followed by the aggregate across all accounts: ✓  2 accounts  ·  240 logos set  ·  1m 32s

A 250ms delay (`GRAPH_WRITE_DELAY`) is inserted between each photo upload to avoid hitting API rate limits.

## State Management

The state file (`state.json`) is a lightweight JSON dictionary that tracks which contacts have been processed, per account:

```json
{
  "user@example.com": {
    "people/c12345": "stripe.com",
    "people/c67890": "acmecorp.com"
  }
}
```

This structure serves two purposes:

- **Idempotency**: Running `--run` twice processes only new contacts the second time. Completed contacts don't get their photo overwritten.
- **Progress preservation**: If the run is interrupted (network failure, Ctrl+C), already-processed contacts are tracked and won't be re-processed on the next run.

The `--overwrite` flag re-processes even completed contacts by skipping the `if contact.id in account_state` check, all without clearing the state file.

The `--reset-state` flag deletes `state.json` entirely, forcing a full re-evaluation of every contact on the next run (logos remain cached, so re-runs are still fast).

## Error Handling Philosophy

BrandBox follows a **fail-soft, never-crash-the-run** philosophy:

- **Per-source exception catching**: Every logo source fetch is wrapped in its own try/except. A timeout from Brandfetch never prevents falling through to the next source.
- **`.miss` sentinel files**: Domains with no logo are tracked via zero-byte sentinel files. They're never retried, even across sessions.
- **API pagination failures**: Each page is fetched independently. If page 3 of 5 fails, pages 1, 2, 4, and 5 are preserved in the result.
- **Per-contact error counting**: The `counts` dictionary tracks six categories — `set`, `processed`, `no_logo`, `domain` (personal email), `no_email`, and `failed`. Each is displayed in the summary.
- **Graceful degradation**: If `cairosvg` is missing, SVG sources are skipped and the pipeline falls through to raster APIs without error.
- **Account-level isolation**: A failure in one account (e.g., expired token) doesn't affect other accounts. The error is caught at the account loop level, logged, and processing continues.

```python
try:
    token = provider.get_token(account)
    counts = _process_account(...)
except Exception as e:
    console.print(f"Error on {account.username}: {e}")
```

The summary line at the end clearly shows what succeeded and what didn't. A clean run displays the account count, logos set, and elapsed time:

✓  2 accounts  ·  240 logos set  ·  1m 32s

If there were failures, a failure count segment is appended:

✓  2 accounts  ·  240 logos set  ·  1m 32s  ·  3 failed

## Key Design Decisions

| Decision                         | Rationale                                                                                                                                                                                                                                |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **SVG-first ordering**           | SVGs are inherently transparent — avoids the white-background problem that raster APIs produce in dark-mode Outlook and Gmail.                                                                                                           |
| **2× SVG rasterization (400px)** | SVGs are vector graphics with infinite resolution. Rasterizing at 2× the target canvas size (400px vs 200px) gives retina-quality output after Lanczos downscaling, with zero extra cost.                                                |
| **Domain deduplication**         | Logo is fetched once per unique root domain, not once per sender email. For 50 senders at `stripe.com`, that's one API call instead of 50 — dramatically reducing latency and API usage during inbox scans.                              |
| **Inline cairosvg import**       | SVG support is optional. If `cairosvg` isn't installed, `_fetch_svg_logo` catches `ImportError` and falls through to raster sources gracefully. No hard dependency.                                                                      |
| **State batching**               | Inbox scan saves state once at the end (bulk creation, no risk of partial failure). The main loop saves per-contact (smaller volume, finer granularity for resumption). Different tradeoffs for different workloads.                     |
| **Auth: browser vs device code** | Google uses `InstalledAppFlow` (opens a browser tab) because their OAuth requires a redirect URI. Microsoft uses MSAL device code flow (displays a URL + code in the terminal) — better for CLI tools that may run on headless machines. |
| **`.miss` sentinel files**       | Zero-byte files on disk mark domains with no logo. No database, no query overhead. `is_known_miss()` is a filesystem check — cheaper than retrying failed lookups on every run.                                                          |
| **No repadding after crop**      | After auto-crop strips transparent borders, the image is scaled to fill the full canvas with no extra padding. Maximizes visible logo area in the 200×200 output.                                                                        |
