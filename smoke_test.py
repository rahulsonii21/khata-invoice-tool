"""
Smoke test: walks through the app's actual core user flows on a mobile-sized
viewport, the way Rahul and his father really use it - not just checking that
pages return 200, but clicking real buttons and confirming real results appear.

Run this before every push that touches the frontend. It won't catch
everything, but it directly targets the gap that let the blank-screen bug
through: testing HTTP responses instead of actually using the app.

Usage: python3 smoke_test.py <base_url>
  e.g. python3 smoke_test.py http://localhost:4173
"""
import sys
import time
from playwright.sync_api import sync_playwright

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:4173"
MOBILE_VIEWPORT = {"width": 390, "height": 844}  # iPhone 12/13-ish, matches primary device

failures = []
console_errors = []


def check(condition, description):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {description}")
    if not condition:
        failures.append(description)


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=MOBILE_VIEWPORT, accept_downloads=True)
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: console_errors.append(str(exc)))
        failed_urls = []
        page.on("response", lambda resp: failed_urls.append(resp.url) if resp.status >= 400 else None)

        print("\n=== 1. Dashboard loads with real content ===")
        page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(1000)
        body = page.inner_text("body")
        check(len(body.strip()) > 0, "Page is not blank")
        check("Dashboard" in body, "Dashboard heading present")
        check("Total invoiced" in body, "Stat cards rendered")

        print("\n=== 2. Mobile bottom tab bar works ===")
        # On mobile viewport, nav should be the bottom tab bar, not the desktop top nav
        tab_bar_visible = page.locator("text=Parties").last.is_visible()
        check(tab_bar_visible, "Bottom tab bar 'Parties' button is visible")
        page.locator("text=Parties").last.click()
        page.wait_for_timeout(1000)
        body = page.inner_text("body")
        check("All customers" in body or "Party" in body, "Parties screen loaded after tap")

        print("\n=== 3. Upload screen and mode switching ===")
        page.locator("text=Upload").last.click()
        page.wait_for_timeout(800)
        body = page.inner_text("body")
        check("Upload photo" in body or "Drop invoice" in body, "Upload screen loaded")
        if page.locator("text=Enter manually").count() > 0:
            page.locator("text=Enter manually").first.click()
            page.wait_for_timeout(500)
            body = page.inner_text("body")
            check("Add invoice manually" in body, "Manual entry mode switch works")

        print("\n=== 4. Generate Bill screen ===")
        page.locator("text=Generate Bill").last.click()
        page.wait_for_timeout(800)
        body = page.inner_text("body")
        check("Generate Bill" in body, "Generate Bill screen loaded")
        check("Party" in body, "Party field present")

        print("\n=== 5. Settings screen ===")
        page.locator("text=Settings").last.click()
        page.wait_for_timeout(800)
        body = page.inner_text("body")
        check("Business Details" in body or "Settings" in body, "Settings screen loaded")

        print("\n=== 6. Backups screen ===")
        page.locator("text=Backups").last.click()
        page.wait_for_timeout(800)
        body = page.inner_text("body")
        check("Backup" in body, "Backups screen loaded")

        print("\n=== 6b. Reports screen ===")
        page.locator("text=Reports").last.click()
        page.wait_for_timeout(800)
        body = page.inner_text("body")
        check("Reports" in body, "Reports screen loaded")
        check("Summary PDF" in body, "Summary PDF option present")
        check("Combined Bills PDF" in body, "Combined Bills PDF option present")

        print("\n=== 6c. Download filename check (regression guard) ===")
        # This exact bug shipped silently once already: Content-Disposition
        # wasn't exposed via CORS, so every export downloaded as a generic
        # "export.pdf"/"export" instead of the real filename - invisible in
        # curl-based testing since curl doesn't enforce CORS, only caught by
        # actually clicking the button in a real browser context.
        try:
            with page.expect_download(timeout=8000) as download_info:
                page.locator("text=Summary PDF").click()
            filename = download_info.value.suggested_filename
            check(filename != "export" and filename != "export.pdf" and filename.startswith("sales_summary"),
                  f"Download has a real filename, not a generic fallback (got: {filename})")
        except Exception as e:
            check(False, f"Download did not trigger at all: {e}")

        print("\n=== 7. Console error check ===")
        # fonts.googleapis.com 403s are a known limitation of this specific
        # testing sandbox (no external network access) - not a real app bug.
        # Cross-check against actual failed URLs rather than trusting the
        # console text, since Chrome's message doesn't always include the URL.
        font_failures = [u for u in failed_urls if "fonts.googleapis.com" in u or "fonts.gstatic.com" in u]
        unexplained_errors = [
            e for e in console_errors
            if not (len(font_failures) > 0 and "403" in e)
        ]
        check(len(unexplained_errors) == 0, f"No unexpected console errors (found: {unexplained_errors})")
        if font_failures:
            print(f"  (ignored: {len(font_failures)} Google Fonts 403s - sandbox network limitation, not an app bug)")

        browser.close()

    print(f"\n{'='*50}")
    if failures:
        print(f"SMOKE TEST FAILED: {len(failures)} issue(s)")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("SMOKE TEST PASSED - all core flows work")
        sys.exit(0)


if __name__ == "__main__":
    run()
