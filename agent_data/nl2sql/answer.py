"""Natural language answer generation for NL2SQL.

Provides configurable answer styles and quality scoring for
converting SQL query results into insightful Chinese answers.
"""
import re
from enum import Enum
from typing import Any, Dict, List, Optional


class AnswerStyle(str, Enum):
    """Answer generation styles."""
    BRIEF = "brief"          # 一句话，数字突出
    DETAILED = "detailed"    # 完整分析，含趋势/排名
    COMPARISON = "comparison"  # 对比型，突出差异
    SUMMARY = "summary"      # 摘要型，多行聚合


# Prompt templates for each style
STYLE_PROMPTS = {
    AnswerStyle.BRIEF: """你是一个数据分析助手。根据查询结果，用一句话回答用户问题。

## 规则
1. 直接给出答案，不超过 1 句话
2. 如果结果是数字，直接写出数字
3. 不要加"根据查询结果"等前缀
4. 用中文回答

## 用户问题
{question}

## 查询结果
{result_data}

请直接回答：""",

    AnswerStyle.DETAILED: """你是一个专业的数据分析助手。根据查询结果，详细回答用户问题。

## 规则
1. 用 2-3 句话完整回答
2. 突出关键数字和数据点
3. 如果有多行结果，指出趋势或排名
4. 如果结果为空，解释可能的原因
5. 用中文回答

## 用户问题
{question}

## SQL 查询
```sql
{sql}
```

## 查询结果
{result_data}

请详细回答：""",

    AnswerStyle.COMPARISON: """你是一个数据分析助手。根据查询结果，对比分析数据。

## 规则
1. 突出不同项之间的差异
2. 用"多/少 X%"或"相差 Y"的格式表达对比
3. 如果是排名，指出第一和最后的差距
4. 用中文回答

## 用户问题
{question}

## SQL 查询
```sql
{sql}
```

## 查询结果
{result_data}

请对比分析：""",

    AnswerStyle.SUMMARY: """你是一个数据分析助手。根据查询结果，提供数据摘要。

## 规则
1. 概括数据的整体情况
2. 指出最大值、最小值、平均值等统计量
3. 如果有多个维度，分别说明
4. 用中文回答

## 用户问题
{question}

## SQL 查询
```sql
{sql}
```

## 查询结果
{result_data}

请提供数据摘要：""",
}


def detect_answer_style(
    question: str,
    sql: str,
    data: List[Dict[str, Any]],
) -> AnswerStyle:
    """自动检测最适合的回答风格。

    Args:
        question: 用户原始问题
        sql: 生成的 SQL
        data: 查询结果

    Returns:
        推荐的回答风格
    """
    if not data:
        return AnswerStyle.BRIEF

    row_count = len(data)

    # 问题含对比词 → comparison
    comparison_words = ["对比", "区别", "差异", "比较", "vs"]
    if any(w in question for w in comparison_words):
        return AnswerStyle.COMPARISON
    # "哪个X高/低/多/少/好/坏" 模式
    if re.search(r"哪个\w*(高|低|多|少|好|坏)", question):
        return AnswerStyle.COMPARISON

    # 问题含摘要词 → summary
    summary_words = ["统计", "汇总", "总览", "概览", "整体", "全部"]
    if any(w in question for w in summary_words) or row_count > 10:
        return AnswerStyle.SUMMARY

    # 单行结果 → brief
    if row_count <= 1:
        return AnswerStyle.BRIEF

    # SQL 含 GROUP BY 或聚合函数 → detailed
    sql_upper = sql.upper()
    if "GROUP BY" in sql_upper or any(fn in sql_upper for fn in ["COUNT", "SUM", "AVG", "MAX", "MIN"]):
        return AnswerStyle.DETAILED

    # 默认 brief
    return AnswerStyle.BRIEF


def build_answer_messages(
    question: str,
    sql: str,
    result_data: List[Dict[str, Any]],
    style: Optional[AnswerStyle] = None,
) -> List[Dict[str, str]]:
    """构建回答生成的 prompt messages。

    Args:
        question: 用户原始问题
        sql: 生成的 SQL
        result_data: 查询结果
        style: 回答风格。None 则自动检测。

    Returns:
        LLM messages 列表
    """
    if style is None:
        style = detect_answer_style(question, sql, result_data)

    # 格式化结果为文本
    lines = []
    if result_data:
        cols = list(result_data[0].keys())
        lines.append(" | ".join(cols))
        lines.append("-" * 40)
        for row in result_data[:20]:
            lines.append(" | ".join(str(row.get(c, "")) for c in cols))
        if len(result_data) > 20:
            lines.append(f"... 共 {len(result_data)} 行，仅显示前 20 行")
    else:
        lines.append("(无结果)")

    result_str = "\n".join(lines)

    prompt = STYLE_PROMPTS[style].format(
        question=question,
        sql=sql,
        result_data=result_str,
    )

    return [
        {"role": "system", "content": "你是一个专业、简洁的中文数据分析助手。"},
        {"role": "user", "content": prompt},
    ]


def score_answer_quality(
    question: str,
    answer: str,
    data: List[Dict[str, Any]],
) -> float:
    """对回答质量进行简单评分 (0-1)。

    评分维度：
    - 数字是否被提及（如果结果含数字）
    - 长度是否合适（太短或太长扣分）
    - 是否包含"根据查询结果"等废话前缀（扣分）

    Args:
        question: 用户问题
        answer: 生成的回答
        data: 查询结果

    Returns:
        质量分数 0.0 - 1.0
    """
    score = 1.0

    # 检查数字是否被提及
    has_numbers = any(
        isinstance(v, (int, float))
        for row in data
        for v in row.values()
    )
    if has_numbers and not re.search(r"\d", answer):
        score -= 0.3

    # 长度检查
    length = len(answer)
    if length < 5:
        score -= 0.3
    elif length > 500:
        score -= 0.2

    # 废话前缀检查
    bad_prefixes = ["根据查询结果", "基于以上信息", "从查询结果可以看出"]
    if any(p in answer[:20] for p in bad_prefixes):
        score -= 0.1

    return max(0.0, min(1.0, score))
