"""PyTorch KR 뉴스 일일 브리핑 — 엔트리포인트"""

import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

from emailer import build_html, send_email
from scraper import get_date_range, scrape_articles
from summarizer import summarize_articles

KST = ZoneInfo("Asia/Seoul")


def main():
    now = datetime.now(KST)
    date_str = now.strftime("%Y-%m-%d")

    print(f"[{date_str}] 브리핑 생성 시작")

    # 1. 글 수집
    try:
        articles = scrape_articles()
        print(f"  수집된 글: {len(articles)}개")
    except Exception as e:
        error_msg = f"글 수집 중 오류: {e}"
        print(f"  ❌ {error_msg}", file=sys.stderr)
        send_email(
            f"[AI 브리핑] {date_str} 오류 발생",
            f"<p>{error_msg}</p>",
        )
        sys.exit(1)

    # 2. 신규 글 없는 경우
    if not articles:
        print("  새로운 글 없음")
        send_email(
            f"[AI 브리핑] {date_str} PyTorch KR 뉴스 요약",
            "<p>오늘은 새로운 글이 없습니다.</p>",
        )
        return

    # 3. Gemini 요약
    try:
        summary = summarize_articles(articles)
        print("  요약 완료")
    except Exception as e:
        error_msg = f"요약 중 오류: {e}"
        print(f"  ❌ {error_msg}", file=sys.stderr)
        send_email(
            f"[AI 브리핑] {date_str} 오류 발생",
            f"<p>{error_msg}</p>",
        )
        sys.exit(1)

    # 4. HTML 빌드 & 이메일 발송
    start, end = get_date_range()
    date_range = f"{start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')}"

    html = build_html(summary, articles, date_range)
    send_email(f"[AI 브리핑] {date_str} PyTorch KR 뉴스 요약", html)

    print(f"  ✅ 브리핑 발송 완료 ({len(articles)}개 글)")


if __name__ == "__main__":
    main()
