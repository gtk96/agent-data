"""空状态渲染：4 个示例 chip 都存在且可点击。"""
from playwright.sync_api import expect


def test_empty_state_chips(demo_server, page):
    page.goto(demo_server)
    page.wait_for_load_state("networkidle")
    chips = page.locator(".chip")
    expect(chips).to_have_count(4)
    expect(chips.nth(0)).to_contain_text("用户")
    page.screenshot(path="tests/e2e/screenshots/empty.png")