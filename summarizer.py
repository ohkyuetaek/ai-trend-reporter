"""Groq (Llama-3.3-70b)를 사용한 뉴스 글 요약"""

import json
import os
import re
import unicodedata

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
각 글의 article_id는 입력에서 부여된 번호를 그대로 사용하세요.

{{
  "trend_summary": "전체 트렌드 종합...",
  "articles": [
    {{
      "article_id": 1,
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


def _normalize_title(title: str) -> str:
    """비교용 제목 정규화: 공백·특수문자 제거, 소문자화"""
    title = unicodedata.normalize("NFC", title)
    title = re.sub(r"[^\w]", "", title).lower()
    return title


def _reorder_summaries(
    original_articles: list[dict],
    llm_summaries: list[dict],
) -> list[dict]:
    """LLM 응답의 요약을 원본 글 순서에 맞게 재정렬.

    1차: article_id 기반 매칭
    2차: 제목 유사도 기반 매칭 (폴백)
    """
    # article_id 기반 매핑 (1-indexed)
    by_id: dict[int, dict] = {}
    for s in llm_summaries:
        aid = s.get("article_id")
        if isinstance(aid, int) and aid not in by_id:
            by_id[aid] = s

    # 제목 기반 매핑 (폴백용)
    by_title: dict[str, dict] = {}
    for s in llm_summaries:
        norm = _normalize_title(s.get("title", ""))
        if norm and norm not in by_title:
            by_title[norm] = s

    reordered: list[dict] = []
    used_ids: set[int] = set()

    for i, orig in enumerate(original_articles):
        expected_id = i + 1  # 1-indexed
        matched = None

        # 1차: article_id 매칭
        if expected_id in by_id:
            matched = by_id[expected_id]
            used_ids.add(expected_id)

        # 2차: 제목 매칭
        if matched is None:
            orig_norm = _normalize_title(orig["title"])
            if orig_norm in by_title:
                matched = by_title.pop(orig_norm)

        # 매칭 실패 시 원본 정보로 폴백
        if matched is None:
            matched = {
                "title": orig["title"],
                "summary": orig.get("content", "")[:200],
                "keywords": [],
            }

        reordered.append(matched)

    return reordered


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
        articles_text += f"\n### 글 {i}/{len(articles)} (article_id={i}). [{source_labels.get(source, source)}] {article['title']}\n"
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

    result = json.loads(text, strict=False)

    # LLM 응답 순서가 입력과 다를 수 있으므로, article_id → 제목 유사도 순으로 매칭
    result["articles"] = _reorder_summaries(articles, result.get("articles", []))

    return result
