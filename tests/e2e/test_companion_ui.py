from __future__ import annotations

import os

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from tests.e2e.companion_browser import (  # noqa: E402
    save_shot,
    send_chat,
    server_up,
    unlock_to_room,
)


pytestmark = pytest.mark.e2e


@pytest.fixture
def page():
    from playwright.sync_api import sync_playwright

    if not server_up():
        pytest.skip("Companion server is not running on 4747")
    headed = os.environ.get("COMPANION_HEADED", "").strip() in {"1", "true", "yes"}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        context = browser.new_context(viewport={"width": 420, "height": 780})
        device = os.environ.get("COMPANION_DEVICE", "a7ad1d6e-5ef0-4b68-8691-ed8bd67dccdb")
        if device:
            context.add_init_script(
                f"localStorage.setItem('edurag_companion_device', {device!r});"
            )
        pg = context.new_page()
        yield pg
        browser.close()


def test_unlock_opens_the_room(page):
    unlock_to_room(page)
    assert page.locator("#room").is_visible()
    assert page.locator("#lock").is_hidden()
    save_shot(page, "room.png")


@pytest.mark.skipif(
    os.environ.get("COMPANION_E2E", "").strip() not in {"1", "true", "yes"},
    reason="Set COMPANION_E2E=1 to send a live chat (needs Ollama)",
)
def test_one_chat_turn(page):
    unlock_to_room(page)
    reply = send_chat(page, "hey. just got home.")
    save_shot(page, "chat.png")
    assert len(reply) >= 4
    low = reply.lower()
    assert "[you unbutton" not in low
    assert "how can i help you" not in low
