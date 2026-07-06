"""
多平台招聘网站 JD 爬虫
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def scrape_liepin():
    """爬取猎聘网 JD"""
    from playwright.async_api import async_playwright

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )

        page = await context.new_page()

        queries = ["AI Agent", "智能体开发", "大模型应用"]

        for query in queries:
            print(f"\n🔍 猎聘搜索: {query}")
            try:
                url = f"https://www.liepin.com/zhaopin/?key={query}"
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(3)

                # 获取职位卡片
                job_cards = await page.query_selector_all(".job-card-pc-container")
                if not job_cards:
                    job_cards = await page.query_selector_all("[class*='job-card']")

                print(f"   找到 {len(job_cards)} 个职位")

                for i, card in enumerate(job_cards[:5]):
                    try:
                        title_el = await card.query_selector("[class*='job-title'] a, .job-title-box a")
                        title = await title_el.inner_text() if title_el else "未知"

                        company_el = await card.query_selector("[class*='company-name'], .company-name")
                        company = await company_el.inner_text() if company_el else "未知"

                        salary_el = await card.query_selector("[class*='job-salary'], .job-salary")
                        salary = await salary_el.inner_text() if salary_el else "未知"

                        area_el = await card.query_selector("[class*='job-dq'], .job-dq")
                        area = await area_el.inner_text() if area_el else "未知"

                        link_el = await card.query_selector("a[href*='/job/']")
                        link = await link_el.get_attribute("href") if link_el else ""
                        if link and not link.startswith("http"):
                            link = f"https://www.liepin.com{link}"

                        results.append({
                            "platform": "猎聘",
                            "query": query,
                            "title": title.strip(),
                            "company": company.strip(),
                            "salary": salary.strip(),
                            "area": area.strip(),
                            "link": link,
                        })
                        print(f"   [{i+1}] {title.strip()} - {company.strip()} ({salary.strip()})")
                    except Exception as e:
                        pass

            except Exception as e:
                print(f"   搜索失败: {e}")

        # 获取详情
        print("\n\n📋 获取猎聘职位详情...")
        detailed = []
        for job in results[:10]:
            if not job.get("link"):
                continue
            print(f"   详情: {job['title'][:30]}...")
            try:
                await page.goto(job["link"], wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2)

                desc_el = await page.query_selector("[class*='job-intro'] [class*='content'], .job-intro-container")
                desc = await desc_el.inner_text() if desc_el else ""

                job["description"] = desc
                detailed.append(job)
            except:
                pass

        await browser.close()

    return results, detailed


async def scrape_zhipin_api():
    """尝试通过 API 获取 Boss 直聘数据"""
    from playwright.async_api import async_playwright

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )

        page = await context.new_page()

        # 先访问主页获取 cookie
        print("\n🔍 访问 Boss 直聘主页...")
        await page.goto("https://www.zhipin.com/", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        queries = ["AI Agent", "智能体", "大模型"]

        for query in queries:
            print(f"\n🔍 Boss 搜索: {query}")
            try:
                url = f"https://www.zhipin.com/web/geek/job?query={query}&city=100010000"
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(5)

                # 尝试获取页面内容
                content = await page.content()

                # 检查是否有验证页面
                if "验证" in content or "captcha" in content.lower():
                    print("   遇到验证码，跳过")
                    continue

                # 尝试多种选择器
                selectors = [
                    ".job-card-wrapper",
                    "[class*='job-card']",
                    ".search-job-result li",
                    ".job-list-box li",
                ]

                for selector in selectors:
                    job_cards = await page.query_selector_all(selector)
                    if job_cards:
                        print(f"   使用选择器 {selector} 找到 {len(job_cards)} 个职位")
                        break

                if not job_cards:
                    # 尝试获取页面文本
                    text = await page.inner_text("body")
                    print(f"   页面文本前200字: {text[:200]}")

            except Exception as e:
                print(f"   搜索失败: {e}")

        await browser.close()

    return results


async def main():
    print("=" * 60)
    print("招聘网站 AI Agent 工程师 JD 爬虫")
    print("=" * 60)

    # 先尝试猎聘
    liepin_results, liepin_detailed = await scrape_liepin()

    # 尝试 Boss 直聘
    boss_results = await scrape_zhipin_api()

    # 合并结果
    all_results = liepin_results + boss_results

    # 保存结果
    output_file = "/Users/gaotingkai/mimo_project/docs/job_jd_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            {"liepin": liepin_results, "liepin_detailed": liepin_detailed, "boss": boss_results},
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"\n\n✅ 结果已保存到: {output_file}")
    print(f"   猎聘: {len(liepin_results)} 个职位")
    print(f"   Boss: {len(boss_results)} 个职位")

    # 输出摘要
    if liepin_detailed:
        print("\n\n📊 猎聘职位详情:")
        for job in liepin_detailed[:10]:
            print(f"\n【{job['title']}】- {job['company']}")
            print(f"   薪资: {job['salary']} | 地区: {job['area']}")
            if job.get("description"):
                desc = job["description"][:300]
                print(f"   描述: {desc}...")


if __name__ == "__main__":
    asyncio.run(main())