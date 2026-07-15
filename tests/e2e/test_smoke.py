"""冒烟：open page → 输入问题 → 看到助手气泡。"""

import re

from playwright.sync_api import expect


def test_smoke_submit(demo_server, page):
    page.goto(demo_server)
    page.wait_for_load_state("networkidle")

    # 输入问题
    page.fill("#chat-input", "有多少用户？")
    page.press("#chat-input", "Enter")

    # 等 ≤30s 助手气泡出现
    article = page.locator(".turn-assistant").first
    article.wait_for(state="visible", timeout=30_000)
    text = article.inner_text()
    assert text.strip()  # 非空
    # statusdot 不报错
    dot = page.locator("#header-status-dot")
    expect(dot).to_be_visible()

    page.screenshot(path="tests/e2e/screenshots/smoke.png", full_page=True)
