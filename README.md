# AI Trend Reporter

PyTorch KR 뉴스와 GeekNews 게시글을 매일 수집해 LLM으로 요약하고, HTML 이메일 브리핑으로 발송하는 자동화 프로젝트입니다. 기본은 Groq API이며, 로컬 Mac에서는 Ollama를 먼저 사용하고 실패 시 Groq로 fallback하는 비용 절감 구성을 지원합니다.

## 주요 기능

- PyTorch KR Discourse 뉴스 수집
- GeekNews RSS 및 개별 글 본문 수집
- KST 기준 브리핑 범위 계산
  - 월요일: 금·토·일 3일치
  - 화~금: 전날 하루치
- LLM provider 선택
  - Groq `llama-3.3-70b-versatile` 기본 지원
  - 로컬 Ollama first + Groq fallback 지원
- 글이 많을 경우 배치 분할 요약
- Gmail SMTP HTML 이메일 발송
- GitHub Actions 평일 오전 7시 KST 자동 실행

## 프로젝트 구조

```text
.
├── main.py                         # 수집 → 요약 → 이메일 발송 오케스트레이션
├── scraper.py                      # PyTorch KR Discourse API 수집
├── scraper_geeknews.py             # GeekNews RSS/본문 수집
├── summarizer.py                   # LLM provider 요약, fallback, 결과 정렬
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

`.env`에 필요한 값을 설정합니다. 기존 GitHub Actions 방식은 Groq API를 사용하고, 로컬 Mac 운영은 Ollama first + Groq fallback 구성을 권장합니다.

```text
LLM_PROVIDER=ollama
LLM_FALLBACK_PROVIDER=groq
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b-instruct
OLLAMA_NUM_CTX=8192
OLLAMA_TIMEOUT=300
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.3-70b-versatile
GMAIL_ADDRESS=your-gmail@gmail.com
GMAIL_APP_PASSWORD=your-16-char-app-password
RECIPIENT_EMAIL=recipient@example.com
```

실행:

```bash
python main.py
```

## Ollama first + Groq fallback 운영

API 비용을 줄이고 싶을 때는 로컬 Mac에서 Ollama를 1차 provider로 사용합니다. Ollama 호출, JSON 파싱, 필수 응답 구조 검증 중 하나라도 실패하면 Groq로 자동 fallback합니다.

1. Ollama 실행 및 모델 설치

```bash
ollama pull qwen2.5:7b-instruct
ollama serve
```

2. `.env` 설정

```text
LLM_PROVIDER=ollama
LLM_FALLBACK_PROVIDER=groq
OLLAMA_MODEL=qwen2.5:7b-instruct
GROQ_API_KEY=your-groq-api-key
```

3. 실행

```bash
python main.py
```

주의사항:

- Ollama first 구성은 로컬 Ollama 서버가 떠 있는 Mac에서 실행해야 합니다.
- GitHub Actions 러너에는 로컬 Ollama 서버가 없으므로 GitHub Actions에서는 Groq provider 사용이 현실적입니다.
- 현재 MacBook Air M3 16GB 기준으로는 7B급 모델부터 검증하는 것을 권장합니다. Groq의 70B 모델과 동일한 품질을 기대하기보다는 비용 절감용 1차 요약기로 사용하고, 실패 시 Groq fallback으로 안정성을 확보합니다.
- 일반 뉴스 요약에는 `qwen2.5-coder:7b`보다 `qwen2.5:7b-instruct`를 우선 권장합니다.

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
