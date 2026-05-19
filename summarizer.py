"""Groq (Llama-3.3-70b)를 사용한 뉴스 글 요약"""

import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request
from typing import Optional

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


BATCH_SIZE = 15  # 배치당 최대 글 수 (출력 토큰 초과 방지)

TREND_PROMPT_TEMPLATE = """\
당신은 AI/ML 및 기술 트렌드 분석가입니다.
아래는 여러 기술 커뮤니티 게시글의 개별 요약입니다.

전체를 종합하여 오늘의 AI/ML 및 기술 트렌드를 3~5문장으로 정리하세요.
- 공통 주제, 기술적 흐름, 주목할 변화를 분석하세요.

한국어로, 반드시 아래 JSON 형식으로 응답하세요.

{{"trend_summary": "전체 트렌드 종합..."}}

---
요약 목록 ({count}개):
{summaries_text}
"""


def _build_articles_text(articles: list[dict], start_id: int = 1) -> str:
    """글 목록을 프롬프트용 텍스트로 변환"""
    source_labels = {
        "pytorch_kr": "PyTorch KR",
        "geeknews": "GeekNews",
    }
    text = ""
    for i, article in enumerate(articles, start_id):
        source = article.get("source", "pytorch_kr")
        text += f"\n### 글 {i} (article_id={i}). [{source_labels.get(source, source)}] {article['title']}\n"
        text += f"URL: {article['url']}\n"
        if article.get("tags"):
            tag_names = [
                t["name"] if isinstance(t, dict) else str(t)
                for t in article["tags"]
            ]
            text += f"태그: {', '.join(tag_names)}\n"
        text += f"본문:\n{_smart_truncate(article['content'])}\n"
    return text


def _call_groq(client: Groq, prompt: str) -> dict:
    """Groq API 호출 후 JSON 파싱"""
    response = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=8192,
        response_format={"type": "json_object"},
    )

    text = response.choices[0].message.content.strip()
    return _parse_json_text(text)


def _parse_json_text(text: str) -> dict:
    """LLM 응답 텍스트에서 JSON 객체를 파싱"""
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]

    return json.loads(text, strict=False)


def _call_ollama(prompt: str) -> dict:
    """로컬 Ollama API 호출 후 JSON 파싱"""
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
    timeout = int(os.getenv("OLLAMA_TIMEOUT", "300"))
    num_ctx = int(os.getenv("OLLAMA_NUM_CTX", "8192"))

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_ctx": num_ctx,
        },
    }
    request = urllib.request.Request(
        f"{base_url}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise RuntimeError(f"Ollama API 호출 실패: {e}") from e

    content = data.get("message", {}).get("content", "")
    if not content:
        raise ValueError("Ollama 응답에 message.content가 없습니다")
    return _parse_json_text(content.strip())


def _provider_order() -> list[str]:
    """환경변수 기준 provider 실행 순서 반환"""
    primary = os.getenv("LLM_PROVIDER", "groq").strip().lower()
    fallback = os.getenv("LLM_FALLBACK_PROVIDER", "").strip().lower()
    providers = [primary]
    if fallback and fallback not in providers:
        providers.append(fallback)
    return providers


def _call_provider(provider: str, prompt: str) -> dict:
    """단일 provider 호출"""
    if provider == "ollama":
        return _call_ollama(prompt)
    if provider == "groq":
        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        return _call_groq(client, prompt)
    raise ValueError(f"지원하지 않는 LLM_PROVIDER: {provider}")


def _validate_articles_result(result: dict, expected_count: Optional[int] = None) -> None:
    """개별 글 요약 응답 shape 검증"""
    if not isinstance(result, dict):
        raise ValueError("LLM 응답이 JSON 객체가 아닙니다")
    articles = result.get("articles")
    if not isinstance(articles, list):
        raise ValueError("LLM 응답에 articles 배열이 없습니다")
    if expected_count is not None and len(articles) != expected_count:
        raise ValueError(
            f"LLM 응답 articles 개수가 맞지 않습니다: "
            f"expected={expected_count}, actual={len(articles)}"
        )
    for i, article in enumerate(articles, 1):
        if not isinstance(article, dict):
            raise ValueError(f"articles[{i}]가 JSON 객체가 아닙니다")
        if not article.get("title"):
            raise ValueError(f"articles[{i}]에 title이 없습니다")
        if not article.get("summary"):
            raise ValueError(f"articles[{i}]에 summary가 없습니다")
        if not isinstance(article.get("keywords"), list):
            raise ValueError(f"articles[{i}]에 keywords 배열이 없습니다")
    if "trend_summary" not in result:
        raise ValueError("LLM 응답에 trend_summary가 없습니다")


def _validate_trend_result(result: dict) -> None:
    """통합 트렌드 응답 shape 검증"""
    if not isinstance(result, dict):
        raise ValueError("LLM 응답이 JSON 객체가 아닙니다")
    if not result.get("trend_summary"):
        raise ValueError("LLM 응답에 trend_summary가 없습니다")


def _call_llm(prompt: str, validator) -> dict:
    """provider 순서대로 호출하고 실패 시 fallback"""
    providers = _provider_order()
    errors = []
    for idx, provider in enumerate(providers):
        try:
            result = _call_provider(provider, prompt)
            validator(result)
            if len(providers) > 1:
                print(f"  LLM provider: {provider}")
            return result
        except Exception as e:
            errors.append(f"{provider}: {e}")
            if idx < len(providers) - 1:
                print(f"  ⚠️ {provider} 실패, fallback 시도: {e}")
                continue
            raise RuntimeError("; ".join(errors)) from e


def summarize_articles(articles: list[dict]) -> dict:
    """설정된 LLM provider를 사용하여 글 일괄 요약. 글이 많으면 배치 분할."""

    # 배치 분할
    batches = [
        articles[i : i + BATCH_SIZE]
        for i in range(0, len(articles), BATCH_SIZE)
    ]

    all_summaries: list[dict] = []

    for batch_idx, batch in enumerate(batches):
        if batch_idx > 0:
            time.sleep(5)  # Groq 무료 티어 rate limit 대비
        start_id = batch_idx * BATCH_SIZE + 1
        articles_text = _build_articles_text(batch, start_id)

        prompt = PROMPT_TEMPLATE.format(
            articles_text=articles_text,
            article_count=len(batch),
        )

        result = _call_llm(
            prompt,
            lambda value, expected_count=len(batch): _validate_articles_result(
                value,
                expected_count=expected_count,
            ),
        )
        batch_summaries = _reorder_summaries(batch, result.get("articles", []))
        all_summaries.extend(batch_summaries)

    # 배치가 1개면 트렌드 요약을 그대로 사용, 여러 배치면 통합 트렌드 생성
    if len(batches) == 1:
        trend_summary = result.get("trend_summary", "")
    else:
        summaries_text = ""
        for i, s in enumerate(all_summaries, 1):
            summaries_text += f"{i}. {s.get('title', '')}: {s.get('summary', '')}\n"

        trend_prompt = TREND_PROMPT_TEMPLATE.format(
            count=len(all_summaries),
            summaries_text=summaries_text,
        )
        trend_result = _call_llm(trend_prompt, _validate_trend_result)
        trend_summary = trend_result.get("trend_summary", "")

    return {
        "trend_summary": trend_summary,
        "articles": all_summaries,
    }
