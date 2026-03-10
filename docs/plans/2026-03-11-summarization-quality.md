# 요약 품질 개선 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** LLM 모델 변경 없이 텍스트 전처리, 프롬프트, 매칭 로직을 개선하여 요약 품질을 높인다.

**Architecture:** HTML→텍스트 변환기 개선, 스마트 잘림, 프롬프트 강화, 인덱스 기반 매칭으로 4개 파일 수정. 추가 LLM 호출 없음, 비용 $0 유지.

**Tech Stack:** Python 3.12, Groq API (llama-3.3-70b), pytest

---

### Task 1: HTML 텍스트 추출기 개선 (scraper.py, scraper_geeknews.py)

**Files:**
- Modify: `scraper.py:17-34` (`_HTMLTextExtractor`, `_strip_html`)
- Modify: `scraper_geeknews.py:20-37` (동일 클래스 중복)
- Create: `tests/test_html_extractor.py`

**Step 1: Write the failing test**

```python
# tests/test_html_extractor.py
from scraper import _strip_html


def test_paragraphs_separated_by_newlines():
    html = "<p>첫 번째 문단입니다.</p><p>두 번째 문단입니다.</p>"
    result = _strip_html(html)
    assert "첫 번째 문단입니다.\n두 번째 문단입니다." == result


def test_list_items_preserved():
    html = "<ul><li>항목 1</li><li>항목 2</li></ul>"
    result = _strip_html(html)
    assert "- 항목 1\n- 항목 2" == result


def test_headings_preserved():
    html = "<h2>제목</h2><p>본문</p>"
    result = _strip_html(html)
    assert "## 제목\n본문" == result


def test_links_text_only():
    html = '<p>자세한 내용은 <a href="https://example.com">여기</a>를 참고하세요.</p>'
    result = _strip_html(html)
    assert "자세한 내용은 여기를 참고하세요." == result


def test_nested_tags():
    html = "<p><strong>중요:</strong> 이것은 <em>강조</em>입니다.</p>"
    result = _strip_html(html)
    assert "중요: 이것은 강조입니다." == result


def test_br_tags():
    html = "<p>줄 1<br>줄 2<br/>줄 3</p>"
    result = _strip_html(html)
    assert "줄 1\n줄 2\n줄 3" in result


def test_multiple_whitespace_collapsed():
    html = "<p>  여러   공백이    있는   텍스트  </p>"
    result = _strip_html(html)
    assert "여러 공백이 있는 텍스트" == result
```

**Step 2: Run test to verify it fails**

Run: `cd /path/to/project && python -m pytest tests/test_html_extractor.py -v`
Expected: FAIL (현재 `_strip_html`은 구조를 무시하고 공백으로 이어붙임)

**Step 3: Write implementation**

`scraper.py`의 `_HTMLTextExtractor`를 구조 보존형으로 교체:

```python
import re
from html.parser import HTMLParser

_BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "tr", "table"}
_LIST_ITEM_TAG = "li"
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_HEADING_PREFIX = {"h1": "# ", "h2": "## ", "h3": "### ", "h4": "#### ", "h5": "##### ", "h6": "###### "}
_BR_TAG = "br"
_SKIP_TAGS = {"script", "style", "nav", "footer", "header"}


class _HTMLTextExtractor(HTMLParser):
    """HTML에서 구조를 보존하며 텍스트 추출"""

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0
        self._tag_stack: list[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        self._tag_stack.append(tag)
        if tag in _BLOCK_TAGS:
            self._parts.append("\n")
            if tag in _HEADING_TAGS:
                self._parts.append(_HEADING_PREFIX[tag])
        elif tag == _LIST_ITEM_TAG:
            self._parts.append("\n- ")
        elif tag == _BR_TAG:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()
        if tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_startendtag(self, tag, attrs):
        if tag.lower() == _BR_TAG and not self._skip_depth:
            self._parts.append("\n")

    def handle_data(self, data):
        if not self._skip_depth:
            self._parts.append(data)

    def get_text(self) -> str:
        text = "".join(self._parts)
        text = re.sub(r"[ \t]+", " ", text)           # 수평 공백 정리
        text = re.sub(r" *\n *", "\n", text)           # 줄바꿈 주변 공백 정리
        text = re.sub(r"\n{3,}", "\n\n", text)         # 연속 빈줄 최대 1개
        return text.strip()


def _strip_html(html: str) -> str:
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    return extractor.get_text()
```

`scraper_geeknews.py`의 중복 클래스를 제거하고 `scraper.py`에서 import:

```python
from scraper import _strip_html
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_html_extractor.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add scraper.py scraper_geeknews.py tests/test_html_extractor.py
git commit -m "refactor(scraper): HTML 텍스트 추출기 구조 보존형으로 개선"
```

---

### Task 2: 스마트 본문 잘림 (summarizer.py)

**Files:**
- Modify: `summarizer.py:58` (잘림 로직)
- Create: `tests/test_truncation.py`

**Step 1: Write the failing test**

```python
# tests/test_truncation.py
from summarizer import _smart_truncate


def test_short_text_unchanged():
    text = "짧은 텍스트입니다."
    assert _smart_truncate(text, 100) == text


def test_truncate_at_sentence_boundary():
    text = "첫 번째 문장입니다. 두 번째 문장입니다. 세 번째 문장입니다."
    result = _smart_truncate(text, 30)
    assert result.endswith("입니다.")
    assert "[이하 생략]" not in result or len(result) <= 30 + len("\n\n[이하 생략]")


def test_truncate_adds_marker():
    text = "가" * 100 + ". " + "나" * 100
    result = _smart_truncate(text, 120)
    assert result.endswith("[이하 생략]")


def test_truncate_at_paragraph_boundary():
    text = "첫 번째 문단입니다.\n\n두 번째 문단입니다.\n\n세 번째 아주 긴 문단입니다."
    result = _smart_truncate(text, 35)
    assert "세 번째" not in result
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_truncation.py -v`
Expected: FAIL (`_smart_truncate` 함수 없음)

**Step 3: Write implementation**

`summarizer.py`에 `_smart_truncate` 함수 추가 및 적용:

```python
def _smart_truncate(text: str, max_chars: int = 3000) -> str:
    """문장/문단 경계에서 자르고, 잘린 경우 표시"""
    if len(text) <= max_chars:
        return text

    # 1차: 문단 경계(\n\n)에서 자르기
    cut = text[:max_chars]
    para_break = cut.rfind("\n\n")
    if para_break > max_chars * 0.5:
        return cut[:para_break].rstrip() + "\n\n[이하 생략]"

    # 2차: 문장 끝(. ! ? 다. 요. 습니다.)에서 자르기
    import re
    sentence_end = None
    for m in re.finditer(r"[.!?。]\s", cut):
        sentence_end = m.end()
    if sentence_end and sentence_end > max_chars * 0.5:
        return cut[:sentence_end].rstrip() + "\n\n[이하 생략]"

    # 3차: 하드컷
    return cut.rstrip() + "\n\n[이하 생략]"
```

`summarizer.py:58`의 `article['content'][:3000]` → `_smart_truncate(article['content'])` 으로 변경.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_truncation.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add summarizer.py tests/test_truncation.py
git commit -m "feat(summarizer): 문장/문단 경계 기반 스마트 잘림 적용"
```

---

### Task 3: 프롬프트 강화 + temperature 설정 (summarizer.py)

**Files:**
- Modify: `summarizer.py:8-35` (프롬프트 템플릿)
- Modify: `summarizer.py:62-65` (API 호출 파라미터)

**Step 1: 프롬프트 개선**

```python
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

```json
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
```

---
게시글 목록 ({article_count}개):
{articles_text}
"""
```

**Step 2: API 호출에 temperature 추가 및 글 번호 포함**

```python
# articles_text 생성 시 번호 명시
articles_text += f"\n### 글 {i}/{len(articles)}. [{source_labels.get(source, source)}] {article['title']}\n"

# API 호출
response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.3,
    response_format={"type": "json_object"},
)
```

**Step 3: 수동 테스트**

프롬프트 변경은 LLM 응답 품질 문제이므로 단위 테스트 대신 수동 확인.
`response_format={"type": "json_object"}`로 JSON 파싱 실패 방지.

**Step 4: Commit**

```bash
git add summarizer.py
git commit -m "feat(summarizer): 프롬프트 강화 및 temperature 0.3 설정"
```

---

### Task 4: 인덱스 기반 요약 매칭 (emailer.py)

**Files:**
- Modify: `emailer.py:44-81` (`build_html`)
- Create: `tests/test_emailer.py`

**Step 1: Write the failing test**

```python
# tests/test_emailer.py
from emailer import build_html


def test_index_based_matching():
    """LLM이 제목을 변경해도 순서 기반으로 매칭"""
    summary_data = {
        "trend_summary": "트렌드 요약",
        "articles": [
            {"title": "약간 다른 제목 A", "summary": "요약 A", "keywords": ["k1"]},
            {"title": "약간 다른 제목 B", "summary": "요약 B", "keywords": ["k2"]},
        ],
    }
    all_articles = [
        {"title": "원본 제목 A", "url": "https://a.com", "content": "내용A", "source": "pytorch_kr"},
        {"title": "원본 제목 B", "url": "https://b.com", "content": "내용B", "source": "pytorch_kr"},
    ]
    articles_by_source = {"pytorch_kr": all_articles}

    html = build_html(summary_data, all_articles, articles_by_source, "2026-03-11")

    assert "요약 A" in html
    assert "요약 B" in html
    assert "원본 제목 A" in html  # 원본 제목 사용
    assert "내용A" not in html    # 폴백(content[:200]) 사용하지 않음


def test_fallback_when_summary_missing():
    """요약 결과가 부족할 때 폴백"""
    summary_data = {
        "trend_summary": "트렌드",
        "articles": [
            {"title": "제목 A", "summary": "요약 A", "keywords": ["k1"]},
        ],
    }
    all_articles = [
        {"title": "제목 A", "url": "https://a.com", "content": "내용A", "source": "pytorch_kr"},
        {"title": "제목 B", "url": "https://b.com", "content": "내용B가 꽤 긴 텍스트", "source": "pytorch_kr"},
    ]
    articles_by_source = {"pytorch_kr": all_articles}

    html = build_html(summary_data, all_articles, articles_by_source, "2026-03-11")

    assert "요약 A" in html
    assert "제목 B" in html  # 폴백이지만 제목은 표시
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_emailer.py -v`
Expected: FAIL (현재 제목 문자열 매칭 기반)

**Step 3: Write implementation**

`emailer.py`의 `build_html`을 인덱스 기반으로 변경:

```python
def build_html(
    summary_data: dict,
    all_articles: list[dict],
    articles_by_source: dict[str, list[dict]],
    date_range: str,
) -> str:
    """요약 데이터를 HTML 이메일 본문으로 변환 (인덱스 기반 매칭)"""
    template = _load_template()

    # 인덱스 기반 매칭: all_articles 순서 = summary articles 순서
    summaries = summary_data.get("articles", [])
    summary_by_index = {}
    idx = 0
    for source, articles in articles_by_source.items():
        for article in articles:
            key = id(article)
            if idx < len(summaries):
                summary_by_index[key] = summaries[idx]
            idx += 1

    sections_html = ""
    for source, articles in articles_by_source.items():
        config = SOURCE_CONFIG.get(source, SOURCE_CONFIG["pytorch_kr"])
        sections_html += (
            f'<div style="margin-bottom:30px;">'
            f'<h2 style="color:#333;font-size:18px;margin:0 0 12px 0;">'
            f'{config["icon"]} {config["label"]} ({len(articles)}개)</h2>'
        )

        for orig in articles:
            summ = summary_by_index.get(id(orig), {
                "title": orig["title"],
                "summary": orig.get("content", "")[:200],
                "keywords": [],
            })
            # 제목은 항상 원본 사용
            summ_with_orig_title = {**summ, "title": orig["title"]}
            sections_html += _build_article_card(orig, summ_with_orig_title, config["color"])

        sections_html += "</div>"

    html = template.replace("{{trend_summary}}", summary_data.get("trend_summary", ""))
    html = html.replace("{{articles_sections}}", sections_html)
    html = html.replace("{{article_count}}", str(len(all_articles)))
    html = html.replace("{{date_range}}", date_range)

    return html
```

핵심: `summarizer.py`에서 글을 넣는 순서와 `build_html`에서 글을 순회하는 순서가 동일하므로, 인덱스로 매칭. `id(article)` 대신 실제로는 `articles_by_source` 순회 순서 = `all_articles` 구성 순서이므로 단순 카운터 사용.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_emailer.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add emailer.py tests/test_emailer.py
git commit -m "fix(emailer): 제목 문자열 매칭 → 인덱스 기반 매칭으로 변경"
```

---

### Task 5: 전체 통합 테스트

**Step 1: 전체 테스트 실행**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

**Step 2: 수동 검증 (선택)**

```bash
python main.py  # .env에 키 설정 필요
```

**Step 3: 최종 커밋**

```bash
git add -A
git commit -m "test: 요약 품질 개선 통합 테스트 추가"
```
