"""
Boss直聘 AI Agent 工程师 JD 爬虫
使用 Playwright 无头浏览器
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def scrape_boss_jd():
    """爬取 Boss 直聘 AI Agent 相关岗位 JD"""
    from playwright.async_api import async_playwright

    results = []

    async with async_playwright() as p:
        # 启动无头浏览器
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )

        page = await context.new_page()

        # 搜索关键词列表
        queries = [
            "AI Agent 工程师",
            "AI Agent 开发",
            "智能体开发工程师",
            "大模型应用开发",
            "LLM工程师",
        ]

        for query in queries:
            print(f"\n🔍 搜索: {query}")
            try:
                # 访问 Boss 直聘搜索页
                url = f"https://www.zhipin.com/web/geek/job?query={query}&city=100010000"
                await page.goto(url, wait_until="networkidle", timeout=30000)

                # 等待页面加载
                await asyncio.sleep(3)

                # 获取职位列表
                job_cards = await page.query_selector_all(".job-card-wrapper")

                print(f"   找到 {len(job_cards)} 个职位")

                # 获取前 5 个职位的详情
                for i, card in enumerate(job_cards[:5]):
                    try:
                        # 获取职位标题
                        title_el = await card.query_selector(".job-name")
                        title = await title_el.inner_text() if title_el else "未知"

                        # 获取公司名称
                        company_el = await card.query_selector(".company-name")
                        company = await company_el.inner_text() if company_el else "未知"

                        # 获取薪资
                        salary_el = await card.query_selector(".salary")
                        salary = await salary_el.inner_text() if salary_el else "未知"

                        # 获取城市
                        area_el = await card.query_selector(".job-area")
                        area = await area_el.inner_text() if area_el else "未知"

                        # 获取职位详情页链接
                        link_el = await card.query_selector("a.job-card-left")
                        link = await link_el.get_attribute("href") if link_el else ""
                        if link and not link.startswith("http"):
                            link = f"https://www.zhipin.com{link}"

                        # 记录职位
                        job_info = {
                            "query": query,
                            "title": title,
                            "company": company,
                            "salary": salary,
                            "area": area,
                            "link": link,
                        }
                        results.append(job_info)
                        print(f"   [{i+1}] {title} - {company} ({salary})")

                    except Exception as e:
                        print(f"   获取职位详情失败: {e}")

                # 翻页 - 获取更多结果
                for page_num in range(2, 4):  # 获取前3页
                    try:
                        next_url = f"{url}&page={page_num}"
                        await page.goto(next_url, wait_until="networkidle", timeout=30000)
                        await asyncio.sleep(2)

                        job_cards = await page.query_selector_all(".job-card-wrapper")
                        for card in job_cards[:3]:
                            try:
                                title_el = await card.query_selector(".job-name")
                                title = await title_el.inner_text() if title_el else "未知"

                                company_el = await card.query_selector(".company-name")
                                company = await company_el.inner_text() if company_el else "未知"

                                salary_el = await card.query_selector(".salary")
                                salary = await salary_el.inner_text() if salary_el else "未知"

                                area_el = await card.query_selector(".job-area")
                                area = await area_el.inner_text() if area_el else "未知"

                                link_el = await card.query_selector("a.job-card-left")
                                link = await link_el.get_attribute("href") if link_el else ""
                                if link and not link.startswith("http"):
                                    link = f"https://www.zhipin.com{link}"

                                job_info = {
                                    "query": query,
                                    "title": title,
                                    "company": company,
                                    "salary": salary,
                                    "area": area,
                                    "link": link,
                                }
                                results.append(job_info)
                            except:
                                pass
                    except:
                        break

            except Exception as e:
                print(f"   搜索失败: {e}")

        # 获取职位详情
        print("\n\n📋 获取职位详情...")
        detailed_results = []

        for job in results[:15]:  # 获取前15个职位的详情
            if not job.get("link"):
                continue

            print(f"   详情: {job['title']}...")
            try:
                await page.goto(job["link"], wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2)

                # 获取职位描述
                desc_el = await page.query_selector(".job-detail-section .job-sec-text")
                description = await desc_el.inner_text() if desc_el else ""

                # 获取任职要求
                require_el = await page.query_selector(".job-sec-text:last-child")
                requirements = await require_el.inner_text() if require_el else ""

                job["description"] = description
                job["requirements"] = requirements
                detailed_results.append(job)

            except Exception as e:
                print(f"   获取详情失败: {e}")

        await browser.close()

    return results, detailed_results


async def main():
    """主函数"""
    print("=" * 60)
    print("Boss 直聘 AI Agent 工程师 JD 爬虫")
    print("=" * 60)

    results, detailed_results = await scrape_boss_jd()

    # 保存结果
    output_file = "/Users/gaotingkai/mimo_project/docs/boss_jd_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            {"summary": results, "details": detailed_results},
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"\n\n✅ 结果已保存到: {output_file}")
    print(f"   总共获取 {len(results)} 个职位")
    print(f"   其中 {len(detailed_results)} 个有详细描述")

    # 输出摘要
    print("\n\n📊 职位摘要:")
    for job in detailed_results[:10]:
        print(f"\n【{job['title']}】- {job['company']}")
        print(f"   薪资: {job['salary']} | 地区: {job['area']}")
        if job.get("description"):
            print(f"   描述: {job['description'][:200]}...")


if __name__ == "__main__":
    asyncio.run(main())