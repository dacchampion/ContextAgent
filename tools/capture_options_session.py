from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
BACKEND_DIR = THIS_FILE.parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from services.options_data import validate_options_session  # noqa: E402


async def _capture_session(output_path: str, dashboard_url: str | None = None) -> int:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "Playwright is not installed. Add the dependency and run 'playwright install chromium'.",
                },
                indent=2,
            )
        )
        raise SystemExit(2) from exc

    target_url = dashboard_url or settings.OPTIONS_DASHBOARD_URL
    if not target_url:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "Missing dashboard URL. Set OPTIONS_DASHBOARD_URL or pass --url.",
                },
                indent=2,
            )
        )
        return 2
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=False,
            args=["--start-maximized"],
        )
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            screen={"width": 1440, "height": 900},
            is_mobile=False,
            has_touch=False,
            device_scale_factor=1,
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/133.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        await page.goto(target_url, wait_until="networkidle")

        print()
        print("Manual options data session capture")
        print(f"Browser opened at: {target_url}")
        print("1. Complete login manually in the opened browser window.")
        print("2. Navigate to the dashboard and make sure you can see protected content.")
        print("3. Return here and press Enter to save the authenticated session.")
        input()

        await context.storage_state(path=str(output))
        cookies = await context.cookies()
        session_check = await validate_options_session(str(output))
        print(
            json.dumps(
                {
                    "ok": bool(session_check.get("ok")),
                    "storage_state_path": str(output),
                    "current_url": page.url,
                    "cookie_count": len(cookies),
                    "session": session_check,
                },
                indent=2,
            )
        )

        await browser.close()
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Open a headed browser, let the user log into the external options dashboard manually, and save Playwright storage_state."
    )
    parser.add_argument(
        "--output",
        default="tmp/options-storage-state.json",
        help="Path where the Playwright storage_state JSON will be written.",
    )
    parser.add_argument(
        "--url",
        help="Optional URL to open instead of the default dashboard URL.",
    )
    args = parser.parse_args()
    return asyncio.run(_capture_session(output_path=args.output, dashboard_url=args.url))


if __name__ == "__main__":
    raise SystemExit(main())
