"""Gemini Flash를 사용한 뉴스 글 요약"""

import json
import os

from google import genai

PROMPT_TEMPLATE = """\
당신은 AI/ML 기술 트렌드 분석가입니다.
아래는 파이토치 한국 사용자 모임의 최근 게시글 목록입니다.

각 글에 대해:
1. 3줄 이내로 핵심 내용을 요약해주세요
2. 해당 글의 핵심 키워드를 2~3개 추출해주세요

그리고 전체 글을 종합하여:
3. 오늘의 AI/ML 트렌드를 3~5문장으로 정리해주세요

한국어로 응답해주세요.
응답은 반드시 아래 JSON 형식으로:
{{
  "trend_summary": "전체 트렌드 종합...",
  "articles": [
    {{
      "title": "글 제목",
      "summary": "3줄 요약",
      "keywords": ["키워드1", "키워드2"]
    }}
  ]
}}

---
게시글 목록:
{articles_text}
"""


def summarize_articles(articles: list[dict]) -> dict:
    """Gemini를 사용하여 글 일괄 요약"""
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    articles_text = ""
    for i, article in enumerate(articles, 1):
        articles_text += f"\n### {i}. {article['title']}\n"
        articles_text += f"URL: {article['url']}\n"
        if article.get("tags"):
            tag_names = [
                t["name"] if isinstance(t, dict) else str(t)
                for t in article["tags"]
            ]
            articles_text += f"태그: {', '.join(tag_names)}\n"
        articles_text += f"본문:\n{article['content'][:3000]}\n"

    prompt = PROMPT_TEMPLATE.format(articles_text=articles_text)

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )

    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]

    return json.loads(text)
