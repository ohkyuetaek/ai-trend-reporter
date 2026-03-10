"""GeekNews (news.hada.io) Atom RSS 피드를 통한 뉴스 크롤링"""

import time
import xml.etree.ElementTree as ET
from datetime import datetime
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

import requests

KST = ZoneInfo("Asia/Seoul")
RSS_URL = "https://news.hada.io/rss/news"
HEADERS = {"User-Agent": "AI-Trend-Reporter/1.0"}
MAX_RETRIES = 3

# Atom 네임스페이스
ATOM_NS = "{http://www.w3.org/2005/Atom}"


class _HTMLTextExtractor(HTMLParser):
    """HTML에서 텍스트만 추출"""

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data):
        self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._parts).strip()


def _strip_html(html: str) -> str:
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    return extractor.get_text()


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
        content = _strip_html(content_html) if content_html else ""

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
