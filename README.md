# AI Trend Reporter

PyTorch KR 뉴스와 GeekNews 게시글을 매일 수집해 로컬 Ollama 모델로 요약하고, HTML 이메일 브리핑으로 발송하는 자동화 프로젝트입니다.

이 프로젝트의 기본 운영 목표는 API 사용량 과금 0원입니다. 따라서 기본 LLM provider는 로컬 Ollama이며, GitHub Actions/Groq API는 기본 운영 경로가 아닙니다.

## 주요 기능

- PyTorch KR Discourse 뉴스 수집
- GeekNews RSS 및 개별 글 본문 수집
- KST 기준 브리핑 범위 계산
  - 월요일: 금·토·일 3일치
  - 화~금: 전날 하루치
- 로컬 Ollama 기반 요약
  - 기본 모델: `qwen2.5:14b`
  - MacBook Air M3 16GB에서 실제 3개 샘플 글 요약 검증 완료
- 글이 많을 경우 배치 분할 요약
- Gmail SMTP HTML 이메일 발송

## 프로젝트 구조

```text
.
├── main.py                         # 수집 → 요약 → 이메일 발송 오케스트레이션
├── scraper.py                      # PyTorch KR Discourse API 수집
├── scraper_geeknews.py             # GeekNews RSS/본문 수집
├── summarizer.py                   # Ollama 요약, 선택적 provider, 결과 정렬
├── emailer.py                      # HTML 생성 및 Gmail SMTP 발송
├── templates/briefing.html         # 이메일 HTML 템플릿
├── tests/                          # 단위 테스트
├── .github/workflows/daily-briefing.yml  # legacy/manual workflow
├── requirements.txt
└── .env.example
```

## 로컬 Ollama 운영

1. Ollama 설치/업데이트

```bash
brew install ollama
# 이미 설치되어 있으면
brew upgrade ollama
```

2. Ollama 서버 실행

```bash
OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 ollama serve
```

이미 Ollama 앱이나 background service가 실행 중이면 별도 실행하지 않아도 됩니다.

3. 권장 모델 설치

```bash
ollama pull qwen2.5:14b
```

선정 근거:

- `qwen3.5:9b`: 설치 및 실행은 가능했지만 짧은 응답도 160초 이상 걸리고 thinking 출력을 길게 생성해 자동 브리핑에는 부적합했습니다.
- `qwen2.5:14b`: 짧은 한국어 응답 약 14초, 3개 샘플 글 JSON 요약 약 119초로 확인됐고, 한국어 요약 품질과 JSON 안정성이 브리핑 용도에 적합했습니다.
- 27B/35B급 모델은 MacBook Air M3 16GB에서 메모리/속도상 비현실적입니다.

4. Python 환경 준비

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

5. `.env` 설정

```text
LLM_PROVIDER=ollama
LLM_FALLBACK_PROVIDER=
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b
OLLAMA_NUM_CTX=8192
OLLAMA_TIMEOUT=550
GMAIL_ADDRESS=your-gmail@gmail.com
GMAIL_APP_PASSWORD=your-16-char-app-password
RECIPIENT_EMAIL=recipient@example.com
```

`LLM_FALLBACK_PROVIDER`는 비워두는 것이 기본입니다. Groq fallback을 설정하면 API 사용량 과금이 발생할 수 있습니다.

6. 실행

```bash
python main.py
```

## 모델 관리

현재 이 프로젝트의 권장 로컬 모델은 하나입니다.

```bash
ollama list
```

권장 상태:

```text
qwen2.5:14b
```

불필요한 모델은 디스크와 메모리 관리를 위해 제거할 수 있습니다.

```bash
ollama rm <model-name>
```

## GitHub Actions

GitHub Actions는 로컬 Ollama 서버에 접근할 수 없으므로 이 프로젝트의 기본 운영 경로가 아닙니다.

API 비용 0원 목표에서는 Mac 로컬 스케줄링, 예를 들어 launchd/cron, 으로 실행하는 방식을 사용합니다. GitHub Actions에서 Groq API로 실행하는 방식은 legacy/manual 용도이며, API 사용량 과금 가능성이 있으므로 기본 스케줄 운영에는 사용하지 않습니다.

## 테스트

```bash
. .venv/bin/activate
python -m pytest -q
```

## 운영 메모

- Mac이 켜져 있고 네트워크에 연결되어 있어야 메일 발송까지 완료됩니다.
- Ollama 서버가 실행 중이어야 합니다.
- 모델 응답이 JSON 파싱 또는 shape validation에 실패하면 현재 기본 구성에서는 API fallback 없이 오류 이메일을 보냅니다. 이는 추가 API 비용을 막기 위한 의도적 동작입니다.
