"""Discourse API를 통한 PyTorch KR 뉴스 크롤링"""

import time
from datetime import datetime, timedelta
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

import requests

KST = ZoneInfo("Asia/Seoul")
BASE_URL = "https://discuss.pytorch.kr"
CATEGORY_URL = f"{BASE_URL}/c/news/14.json"
HEADERS = {"User-Agent": "PyTorchKR-Briefing-Bot/1.0"}
MAX_RETRIES = 3


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


def _request_with_retry(url: str) -> dict:
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2**attempt)


def get_date_range() -> tuple[datetime, datetime]:
    """수집 대상 날짜 범위 반환 (start inclusive, end exclusive)"""
    now = datetime.now(KST)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if now.weekday() == 0:  # 월요일 → 금·토·일 포함
        start = today - timedelta(days=3)
    else:  # 화~금 → 전날만
        start = today - timedelta(days=1)

    return start, today


def _fetch_topics() -> list[dict]:
    data = _request_with_retry(CATEGORY_URL)
    return data.get("topic_list", {}).get("topics", [])


def _fetch_topic_content(topic_id: int) -> str:
    url = f"{BASE_URL}/t/{topic_id}.json"
    data = _request_with_retry(url)
    posts = data.get("post_stream", {}).get("posts", [])
    if posts:
        return _strip_html(posts[0].get("cooked", ""))
    return ""


def scrape_articles() -> list[dict]:
    """날짜 범위에 해당하는 뉴스 글 수집"""
    start, end = get_date_range()
    topics = _fetch_topics()

    articles = []
    for topic in topics:
        created_at = (
            datetime.fromisoformat(topic["created_at"].replace("Z", "+00:00"))
            .astimezone(KST)
        )
        if start <= created_at < end:
            content = _fetch_topic_content(topic["id"])
            articles.append(
                {
                    "title": topic["title"],
                    "url": f"{BASE_URL}/t/{topic.get('slug', '')}/{topic['id']}",
                    "content": content,
                    "created_at": created_at.isoformat(),
                    "tags": topic.get("tags", []),
                    "source": "pytorch_kr",
                }
            )

    return articles
