"""错误：mock /api/v1/query 抛 500，UI 显示运行失败。"""

import re

from playwright.sync_api import expect


def test_500_shows_failure(demo_server, page):
    page.route("**/api/v1/query", lambda route: route.fulfill(status=500, body="boom"))
    page.goto(demo_server)
    page.wait_for_load_state("networkidle")
    page.fill("#chat-input", "test 500")
    page.press("#chat-input", "Enter")
    article = page.locator(".turn-assistant").first
    article.wait_for(state="visible", timeout=15_000)
    expect(article).to_contain_text(re.compile(r"运行失败"))
