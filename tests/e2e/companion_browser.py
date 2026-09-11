"""Shared Playwright helpers for the companion room. Needs the server on 4747."""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_URL = os.environ.get("COMPANION_URL", "http://127.0.0.1:4747/companion")
DEFAULT_KEY = os.environ.get("COMPANION_KEY", "home-4747")
DEFAULT_DEVICE = os.environ.get(
    "COMPANION_DEVICE",
    "a7ad1d6e-5ef0-4b68-8691-ed8bd67dccdb",
)
ARTIFACTS = Path(__file__).resolve().parent / "artifacts"


def server_up(url: str = DEFAULT_URL, timeout: float = 2.0) -> bool:
    import urllib.error
    import urllib.request

    health = url.split("/companion")[0].rstrip("/") + "/v1/health"
    try:
        urllib.request.urlopen(health, timeout=timeout)
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def new_page(playwright, *, headed: bool = False, device_id: str = DEFAULT_DEVICE):
    browser = playwright.chromium.launch(headless=not headed)
    context = browser.new_context(viewport={"width": 420, "height": 780})
    if device_id:
        context.add_init_script(
            f"localStorage.setItem('edurag_companion_device', {device_id!r});"
        )
    page = context.new_page()
    return browser, context, page


def unlock_to_room(page, *, url: str = DEFAULT_URL, key: str = DEFAULT_KEY) -> str:
    """Lock → (setup if needed) → room. Returns 'room' or 'setup'."""
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    lock = page.locator("#lock")
    if lock.is_visible():
        page.locator('#unlockForm input[name="key"]').fill(key)
        box = page.locator('#unlockForm input[name="adult_confirm"]')
        if not box.is_checked():
            box.check()
        page.locator('#unlockForm button[type="submit"]').click()
        page.wait_for_timeout(800)
    setup = page.locator("#setup")
    if setup.is_visible():
        name = page.locator('#youForm input[name="user_name"]')
        if not (name.input_value() or "").strip():
            name.fill("Noah")
        page.locator('#youForm button[type="submit"]').click()
    page.locator("#room").wait_for(state="visible", timeout=15_000)
    return "room"


def send_chat(page, text: str, *, timeout_ms: int = 120_000) -> str:
    before = page.locator(".msg.assistant").count()
    box = page.locator("#input")
    box.fill(text)
    box.dispatch_event("input")
    send = page.locator("#send")
    send.wait_for(state="visible", timeout=5_000)
    page.wait_for_function("() => !document.getElementById('send').disabled", timeout=5_000)
    send.click()
    page.wait_for_function(
        """(before) => {
          const typing = document.getElementById('typing');
          const nodes = document.querySelectorAll('.msg.assistant');
          if (nodes.length <= before) return false;
          const last = nodes[nodes.length - 1];
          const done = typing && typing.classList.contains('hidden');
          return Boolean(done && last && last.textContent.trim().length > 2);
        }""",
        arg=before,
        timeout=timeout_ms,
    )
    return (page.locator(".msg.assistant").last.inner_text() or "").strip()


def save_shot(page, name: str) -> Path:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS / name
    page.screenshot(path=str(path), full_page=True)
    return path
