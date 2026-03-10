"""AI 트렌드 일일 브리핑 — 엔트리포인트"""

import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

from emailer import build_html, send_email
from scraper import get_date_range, scrape_articles
from scraper_geeknews import scrape_geeknews
from summarizer import summarize_articles

KST = ZoneInfo("Asia/Seoul")

def main():
    now = datetime.now(KST)
    date_str = now.strftime("%Y-%m-%d")
    start, end = get_date_range()

    print(f"[{date_str}] 브리핑 생성 시작")

    # 1. 글 수집 (다중 소스)
    all_articles = []
    errors = []

    for name, scrape_fn in [
        ("PyTorch KR", lambda: scrape_articles()),
        ("GeekNews", lambda: scrape_geeknews(start, end)),
    ]:
        try:
            articles = scrape_fn()
            print(f"  {name}: {len(articles)}개 수집")
            all_articles.extend(articles)
        except Exception as e:
            error_msg = f"{name} 수집 오류: {e}"
            print(f"  ❌ {error_msg}", file=sys.stderr)
            errors.append(error_msg)

    # 모든 소스 실패 시
    if not all_articles and errors:
        send_email(
            f"[AI 브리핑] {date_str} 오류 발생",
            f"<p>{'<br>'.join(errors)}</p>",
        )
        sys.exit(1)

    # 2. 신규 글 없는 경우
    if not all_articles:
        print("  새로운 글 없음")
        send_email(
            f"[AI 브리핑] {date_str} AI 트렌드 요약",
            "<p>오늘은 새로운 글이 없습니다.</p>",
        )
        return

    # 3. Groq 요약
    try:
        summary = summarize_articles(all_articles)
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
    date_range = f"{start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')}"

    # 소스별 글 분류
    articles_by_source = {}
    for article in all_articles:
        source = article.get("source", "pytorch_kr")
        articles_by_source.setdefault(source, []).append(article)

    html = build_html(summary, all_articles, articles_by_source, date_range)

    # 부분 실패 경고 포함
    subject = f"[AI 브리핑] {date_str} AI 트렌드 요약"
    if errors:
        subject += " (일부 소스 오류)"

    send_email(subject, html)

    print(f"  ✅ 브리핑 발송 완료 ({len(all_articles)}개 글)")


if __name__ == "__main__":
    main()
