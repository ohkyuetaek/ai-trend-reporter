# AI Trend Reporter

PyTorch KR 뉴스와 GeekNews 게시글을 매일 수집해 Groq Llama 모델로 요약하고, HTML 이메일 브리핑으로 발송하는 GitHub Actions 기반 자동화 프로젝트입니다.

## 주요 기능

- PyTorch KR Discourse 뉴스 수집
- GeekNews RSS 및 개별 글 본문 수집
- KST 기준 브리핑 범위 계산
  - 월요일: 금·토·일 3일치
  - 화~금: 전날 하루치
- Groq `llama-3.3-70b-versatile` 기반 요약
- 글이 많을 경우 배치 분할 요약
- Gmail SMTP HTML 이메일 발송
- GitHub Actions 평일 오전 7시 KST 자동 실행

## 프로젝트 구조

```text
.
├── main.py                         # 수집 → 요약 → 이메일 발송 오케스트레이션
├── scraper.py                      # PyTorch KR Discourse API 수집
├── scraper_geeknews.py             # GeekNews RSS/본문 수집
├── summarizer.py                   # Groq 요약 및 결과 정렬
├── emailer.py                      # HTML 생성 및 Gmail SMTP 발송
├── templates/briefing.html         # 이메일 HTML 템플릿
├── tests/                          # 단위 테스트
├── .github/workflows/daily-briefing.yml
├── requirements.txt
└── .env.example
```

## 로컬 실행

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env`에 필요한 값을 설정합니다.

```text
GROQ_API_KEY=your-groq-api-key
GMAIL_ADDRESS=your-gmail@gmail.com
GMAIL_APP_PASSWORD=your-16-char-app-password
RECIPIENT_EMAIL=recipient@example.com
```

실행:

```bash
python main.py
```

## 테스트

```bash
. .venv/bin/activate
python -m pytest -q
```

## GitHub Actions 설정

Repository Secrets에 아래 값을 등록해야 합니다.

- `GROQ_API_KEY`
- `GMAIL_ADDRESS`
- `GMAIL_APP_PASSWORD`
- `RECIPIENT_EMAIL`

Workflow는 `.github/workflows/daily-briefing.yml`에 정의되어 있으며, 평일 오전 7시 KST에 실행됩니다.

## 운영 메모

Public repository의 scheduled GitHub Actions는 장기간 push가 없으면 자동 비활성화될 수 있습니다. 정기적으로 README, 문서, 설정 등 의미 있는 변경사항을 커밋해 workflow 비활성화를 방지합니다.
