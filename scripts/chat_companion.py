"""Drive the companion room in Chromium. Server must already be on 4747.

  .venv\\Scripts\\python.exe scripts\\chat_companion.py
  .venv\\Scripts\\python.exe scripts\\chat_companion.py --headed "miss you"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.e2e.companion_browser import (  # noqa: E402
    DEFAULT_KEY,
    DEFAULT_URL,
    save_shot,
    send_chat,
    server_up,
    unlock_to_room,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Playwright chat against /companion")
    parser.add_argument("message", nargs="?", default="hey. just got home.")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--key", default=DEFAULT_KEY)
    parser.add_argument("--device", default="a7ad1d6e-5ef0-4b68-8691-ed8bd67dccdb")
    args = parser.parse_args()
    if not server_up(args.url):
        print("Server is not up. Start-Companion.bat first.", file=sys.stderr)
        return 2
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        context = browser.new_context(viewport={"width": 420, "height": 780})
        if args.device:
            context.add_init_script(
                f"localStorage.setItem('edurag_companion_device', {args.device!r});"
            )
        page = context.new_page()
        unlock_to_room(page, url=args.url, key=args.key)
        print("ROOM ok")
        reply = send_chat(page, args.message)
        shot = save_shot(page, "last-chat.png")
        print("--- Maya ---")
        print(reply)
        print("---")
        print("screenshot:", shot)
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
