"""Groq (Llama-3.3-70b)를 사용한 뉴스 글 요약"""

import json
import os
import re

from groq import Groq

PROMPT_TEMPLATE = """\
당신은 AI/ML 및 기술 트렌드 분석가입니다.
아래는 여러 기술 커뮤니티(PyTorch KR, GeekNews 등)의 최근 게시글 목록입니다.

## 지시사항

각 글에 대해 (입력 순서 그대로, 빠짐없이):
1. 글의 **핵심 주장, 결론, 또는 새로운 발견**을 중심으로 3줄 이내로 요약하세요.
   - 원문의 문장을 그대로 복사하지 마세요. 핵심만 재구성하세요.
   - "~에 대해 다룬다", "~를 소개한다" 같은 메타 설명 대신, 실제 내용을 요약하세요.
2. 핵심 키워드를 2~3개 추출하세요.

전체 글을 종합하여:
3. 오늘의 AI/ML 및 기술 트렌드를 3~5문장으로 정리하세요.
   - 공통 주제, 기술적 흐름, 주목할 변화를 분석하세요.

## 응답 형식

한국어로, 반드시 아래 JSON 형식으로 응답하세요.
articles 배열의 순서와 개수는 입력 게시글과 정확히 일치해야 합니다.

{{
  "trend_summary": "전체 트렌드 종합...",
  "articles": [
    {{
      "title": "원문 제목 그대로",
      "summary": "핵심 내용 요약 (원문 복붙 금지)",
      "keywords": ["키워드1", "키워드2"]
    }}
  ]
}}

---
게시글 목록 ({article_count}개):
{articles_text}
"""


def _smart_truncate(text: str, max_chars: int = 2000) -> str:
    """문장/문단 경계에서 자르고, 잘린 경우 표시"""
    if len(text) <= max_chars:
        return text

    cut = text[:max_chars]

    # 1차: 문단 경계(\n\n)에서 자르기
    para_break = cut.rfind("\n\n")
    if para_break > max_chars * 0.5:
        return cut[:para_break].rstrip() + "\n\n[이하 생략]"

    # 2차: 문장 끝(. ! ? 등)에서 자르기
    sentence_end = None
    for m in re.finditer(r"[.!?。]\s", cut):
        sentence_end = m.end()
    if sentence_end and sentence_end > max_chars * 0.5:
        return cut[:sentence_end].rstrip() + "\n\n[이하 생략]"

    # 3차: 하드컷
    return cut.rstrip() + "\n\n[이하 생략]"


def summarize_articles(articles: list[dict]) -> dict:
    """Groq을 사용하여 글 일괄 요약"""
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    source_labels = {
        "pytorch_kr": "PyTorch KR",
        "geeknews": "GeekNews",
    }

    articles_text = ""
    for i, article in enumerate(articles, 1):
        source = article.get("source", "pytorch_kr")
        articles_text += f"\n### 글 {i}/{len(articles)}. [{source_labels.get(source, source)}] {article['title']}\n"
        articles_text += f"URL: {article['url']}\n"
        if article.get("tags"):
            tag_names = [
                t["name"] if isinstance(t, dict) else str(t)
                for t in article["tags"]
            ]
            articles_text += f"태그: {', '.join(tag_names)}\n"
        articles_text += f"본문:\n{_smart_truncate(article['content'])}\n"

    prompt = PROMPT_TEMPLATE.format(
        articles_text=articles_text,
        article_count=len(articles),
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]

    return json.loads(text)
