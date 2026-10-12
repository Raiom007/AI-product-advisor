# ADR 0005: Live Web Scraping Implementation

## Status
Proposed

## Context
The user requested "real scraping" where the output contains working, live links to actual e-commerce websites (like Amazon or BestBuy) rather than synthetic or mock APIs (like DummyJSON). 

However, all major e-commerce platforms (Amazon, BestBuy, B&H, eBay) and search engines (DuckDuckGo) currently deploy aggressive bot-protection (Cloudflare, PerimeterX, CAPTCHAs) that instantly block simple, fast HTTP requests (`httpx` or `requests`). 

To fulfill the requirement of fetching *real* products and reviews from these sites live, we must bypass bot protection.

## Decision Options

**Option A: Headless Browser (Playwright)**
- **How:** Install `playwright` (new dependency), launch a hidden Chromium browser, and physically render the page to bypass basic bot checks.
- **Pros:** Will successfully fetch real Amazon links, prices, and text reviews.
- **Cons:** Extremely slow (takes 10-30 seconds per search, violating "fast" MVP goals). Violates Rule 10 (no new dependencies without ADR). Requires downloading ~100MB of browser binaries.

**Option B: Third-Party Scraping API (Rainforest API / BrightData)**
- **How:** Use a dedicated scraping proxy service.
- **Pros:** Fast and 100% reliable.
- **Cons:** Violates Rule 10 ("Free tier only. No paid keys").

**Option C: Keep DummyJSON but inject real Amazon links**
- **How:** Continue using the fast, reliable DummyJSON mock API, but programmatically map the dummy products to real, working Amazon ASIN URLs.
- **Pros:** Lightning fast, no new dependencies, no bot blocks.
- **Cons:** The data (prices/reviews) comes from DummyJSON, only the link points to Amazon.

## Recommendation
Since Option B violates the SOW, we must choose between **Option A (Slow but Real)** or **Option C (Fast but Mocked Data with Real Links)**.
