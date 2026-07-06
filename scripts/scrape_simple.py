"""
简单 JD 爬虫 - 提取页面文本
"""

import asyncio
import json
from playwright.async_api import async_playwright


async def scrape_liepin_text():
    """从猎聘网提取文本内容"""
    from playwright.async_api import async_playwright

    all_text = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )

        page = await context.new_page()

        queries = ["AI Agent 工程师", "智能体开发工程师", "大模型应用开发"]

        for query in queries:
            print(f"\n🔍 搜索: {query}")
            try:
                url = f"https://www.liepin.com/zhaopin/?key={query}"
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(3)

                # 提取页面所有文本
                body_text = await page.inner_text("body")
                all_text.append({"query": query, "text": body_text[:5000]})

                # 尝试获取职位链接
                links = await page.query_selector_all("a[href*='/job/']")
                print(f"   找到 {len(links)} 个职位链接")

                # 获取前3个职位详情
                for i, link in enumerate(links[:3]):
                    try:
                        href = await link.get_attribute("href")
                        if href and not href.startswith("http"):
                            href = f"https://www.liepin.com{href}"

                        await page.goto(href, wait_until="networkidle", timeout=30000)
                        await asyncio.sleep(2)

                        detail_text = await page.inner_text("body")
                        all_text.append({"query": query, "url": href, "text": detail_text[:8000]})

                        # 提取关键信息
                        print(f"   职位 {i+1} 详情已获取")
                    except Exception as e:
                        print(f"   获取详情失败: {e}")

            except Exception as e:
                print(f"   搜索失败: {e}")

        await browser.close()

    return all_text


async def main():
    print("=" * 60)
    print("JD 文本提取器")
    print("=" * 60)

    all_text = await scrape_liepin_text()

    # 保存原始文本
    output_file = "/Users/gaotingkai/mimo_project/docs/job_texts.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_text, f, ensure_ascii=False, indent=2)

    print(f"\n\n✅ 文本已保存到: {output_file}")
    print(f"   共获取 {len(all_text)} 个文本片段")

    # 输出预览
    for item in all_text[:5]:
        print(f"\n--- {item['query']} ---")
        print(item['text'][:500])


if __name__ == "__main__":
    asyncio.run(main())