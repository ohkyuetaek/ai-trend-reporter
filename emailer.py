"""Gmail SMTP를 통한 브리핑 이메일 발송"""

import base64
import os
import smtplib
import subprocess
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


def _load_template() -> str:
    template_path = Path(__file__).parent / "templates" / "briefing.html"
    return template_path.read_text(encoding="utf-8")


SOURCE_CONFIG = {
    "pytorch_kr": {
        "label": "PyTorch KR",
        "color": "#ee4c2c",
        "icon": "🔥",
    },
    "geeknews": {
        "label": "GeekNews",
        "color": "#6b48ff",
        "icon": "💡",
    },
}


def _build_article_card(orig: dict, summ: dict, border_color: str) -> str:
    keywords = ", ".join(summ.get("keywords", []))
    return (
        f'<div style="margin-bottom:20px;padding:15px;background:#f8f9fa;'
        f'border-radius:8px;border-left:4px solid {border_color};">'
        f'<h3 style="margin:0 0 8px 0;">'
        f'<a href="{orig["url"]}" style="color:#1a73e8;text-decoration:none;">'
        f"{summ['title']}</a></h3>"
        f'<p style="margin:0 0 8px 0;color:#333;line-height:1.6;">'
        f"{summ['summary']}</p>"
        f'<p style="margin:0;color:#666;font-size:13px;">'
        f"🏷️ {keywords}</p></div>"
    )


def build_html(
    summary_data: dict,
    all_articles: list[dict],
    articles_by_source: dict[str, list[dict]],
    date_range: str,
) -> str:
    """요약 데이터를 HTML 이메일 본문으로 변환 (인덱스 기반 매칭)"""
    template = _load_template()

    # all_articles의 인덱스 순서로 요약 매칭 (dict 순회 순서에 의존하지 않음)
    summaries = summary_data.get("articles", [])
    summary_by_id = {}
    for i, article in enumerate(all_articles):
        if i < len(summaries):
            summary_by_id[id(article)] = summaries[i]

    sections_html = ""
    for source, articles in articles_by_source.items():
        config = SOURCE_CONFIG.get(source, SOURCE_CONFIG["pytorch_kr"])

        sections_html += (
            f'<div style="margin-bottom:30px;">'
            f'<h2 style="color:#333;font-size:18px;margin:0 0 12px 0;">'
            f'{config["icon"]} {config["label"]} ({len(articles)}개)</h2>'
        )

        for orig in articles:
            matched = summary_by_id.get(id(orig))
            if matched:
                summ = {**matched, "title": orig["title"]}
            else:
                summ = {
                    "title": orig["title"],
                    "summary": orig.get("content", "")[:200],
                    "keywords": [],
                }
            sections_html += _build_article_card(orig, summ, config["color"])

        sections_html += "</div>"

    html = template.replace("{{trend_summary}}", summary_data.get("trend_summary", ""))
    html = html.replace("{{articles_sections}}", sections_html)
    html = html.replace("{{article_count}}", str(len(all_articles)))
    html = html.replace("{{date_range}}", date_range)

    return html


def _send_email_smtp(subject: str, html_body: str):
    """Gmail SMTP로 이메일 발송"""
    gmail_address = os.environ["GMAIL_ADDRESS"].strip().replace("\xa0", "")
    gmail_password = os.environ["GMAIL_APP_PASSWORD"].strip().replace("\xa0", "").replace(" ", "")
    recipient = os.environ["RECIPIENT_EMAIL"].strip().replace("\xa0", "")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(gmail_address, gmail_password)
        server.sendmail(gmail_address, recipient, msg.as_string())


def _send_email_github_actions(subject: str, html_body: str):
    """GitHub Actions에 저장된 Gmail secrets를 사용해 이메일만 발송한다.

    로컬 Mac의 Gmail 앱 비밀번호가 오래되었더라도, 기존 Groq 기반 workflow에서
    검증된 GitHub repository secrets를 재사용한다. 요약은 로컬 Ollama가 수행하므로
    Groq API 비용은 발생하지 않는다.
    """
    repo = os.getenv("GITHUB_EMAIL_REPO", "ohkyuetaek/ai-trend-reporter")
    workflow = os.getenv("GITHUB_EMAIL_WORKFLOW", "send-email.yml")
    html_b64 = base64.b64encode(html_body.encode("utf-8")).decode("ascii")

    result = subprocess.run(
        [
            "gh",
            "workflow",
            "run",
            workflow,
            "--repo",
            repo,
            "--field",
            f"subject={subject}",
            "--field",
            f"html_b64={html_b64}",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"GitHub Actions 이메일 발송 workflow dispatch 실패: {detail}")


def send_email(subject: str, html_body: str):
    """이메일 발송.

    기본은 직접 Gmail SMTP이며, EMAIL_FALLBACK_PROVIDER=github_actions이면
    SMTP 인증 실패 시 GitHub Actions secrets 기반 발송으로 재시도한다.
    EMAIL_PROVIDER=github_actions이면 처음부터 GitHub Actions 경로를 사용한다.
    """
    provider = os.getenv("EMAIL_PROVIDER", "smtp").strip().lower()
    fallback = os.getenv("EMAIL_FALLBACK_PROVIDER", "").strip().lower()

    if provider == "github_actions":
        _send_email_github_actions(subject, html_body)
        return
    if provider != "smtp":
        raise ValueError(f"지원하지 않는 EMAIL_PROVIDER: {provider}")

    try:
        _send_email_smtp(subject, html_body)
    except smtplib.SMTPAuthenticationError:
        if fallback == "github_actions":
            print("  ⚠️ 로컬 SMTP 인증 실패, GitHub Actions secrets로 이메일 발송 재시도")
            _send_email_github_actions(subject, html_body)
            return
        raise
