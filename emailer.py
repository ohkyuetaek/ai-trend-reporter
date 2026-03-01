"""Gmail SMTP를 통한 브리핑 이메일 발송"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


def _load_template() -> str:
    template_path = Path(__file__).parent / "templates" / "briefing.html"
    return template_path.read_text(encoding="utf-8")


def build_html(summary_data: dict, articles: list[dict], date_range: str) -> str:
    """요약 데이터를 HTML 이메일 본문으로 변환"""
    template = _load_template()

    articles_html = ""
    for orig, summ in zip(articles, summary_data.get("articles", [])):
        keywords = ", ".join(summ.get("keywords", []))
        articles_html += (
            '<div style="margin-bottom:20px;padding:15px;background:#f8f9fa;'
            'border-radius:8px;border-left:4px solid #4285f4;">'
            "<h3 style=\"margin:0 0 8px 0;\">"
            f'<a href="{orig["url"]}" style="color:#1a73e8;text-decoration:none;">'
            f"{summ['title']}</a></h3>"
            f'<p style="margin:0 0 8px 0;color:#333;line-height:1.6;">'
            f"{summ['summary']}</p>"
            f'<p style="margin:0;color:#666;font-size:13px;">'
            f"🏷️ {keywords}</p></div>"
        )

    html = template.replace("{{trend_summary}}", summary_data.get("trend_summary", ""))
    html = html.replace("{{articles}}", articles_html)
    html = html.replace("{{article_count}}", str(len(articles)))
    html = html.replace("{{date_range}}", date_range)

    return html


def send_email(subject: str, html_body: str):
    """Gmail SMTP로 이메일 발송"""
    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ["RECIPIENT_EMAIL"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(gmail_address, gmail_password)
        server.sendmail(gmail_address, recipient, msg.as_string())
