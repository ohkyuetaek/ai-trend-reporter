"""GeekNews (news.hada.io) Atom RSS 피드를 통한 뉴스 크롤링"""

import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from scraper import _strip_html

KST = ZoneInfo("Asia/Seoul")
RSS_URL = "https://news.hada.io/rss/news"
HEADERS = {"User-Agent": "AI-Trend-Reporter/1.0"}
MAX_RETRIES = 3

# Atom 네임스페이스
ATOM_NS = "{http://www.w3.org/2005/Atom}"

_TOPIC_CONTENTS_RE = re.compile(
    r"<span id='topic_contents'>(.*?)</span>", re.DOTALL
)


def _fetch_rss() -> ET.Element:
    """RSS 피드를 가져와서 XML 루트 반환"""
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(RSS_URL, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            return ET.fromstring(resp.content)
        except (requests.RequestException, ET.ParseError):
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2**attempt)


def _fetch_topic_content(url: str, rss_content: str) -> str:
    """개별 GeekNews 토픽 페이지에서 전체 본문을 가져온다. 실패 시 RSS 내용으로 폴백."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            m = _TOPIC_CONTENTS_RE.search(resp.text)
            if m:
                return _strip_html(m.group(1))
            break
        except requests.RequestException:
            if attempt == MAX_RETRIES - 1:
                break
            time.sleep(2**attempt)
    return rss_content


def scrape_geeknews(start: datetime, end: datetime) -> list[dict]:
    """날짜 범위에 해당하는 GeekNews 글 수집"""
    root = _fetch_rss()

    articles = []
    for entry in root.findall(f"{ATOM_NS}entry"):
        published_text = entry.findtext(f"{ATOM_NS}published", "")
        if not published_text:
            continue

        published = datetime.fromisoformat(published_text).astimezone(KST)
        if not (start <= published < end):
            continue

        title = entry.findtext(f"{ATOM_NS}title", "").strip()
        link_el = entry.find(f"{ATOM_NS}link[@rel='alternate']")
        url = link_el.get("href", "") if link_el is not None else ""
        content_html = entry.findtext(f"{ATOM_NS}content", "")
        rss_content = _strip_html(content_html) if content_html else ""

        # 개별 페이지에서 전체 본문 가져오기 (RSS는 요약만 포함)
        content = _fetch_topic_content(url, rss_content) if url else rss_content

        articles.append(
            {
                "title": title,
                "url": url,
                "content": content,
                "created_at": published.isoformat(),
                "tags": [],
                "source": "geeknews",
            }
        )

    return articles
