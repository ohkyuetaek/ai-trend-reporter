# PyTorch KR 뉴스 일일 브리핑 자동화

## 프로젝트 개요

파이토치 한국 사용자 모임 게시판(https://discuss.pytorch.kr/c/news/14)의 신규 글을 매일 자동 수집하여, AI 요약 브리핑을 이메일로 발송하는 GitHub Actions 기반 자동화 프로젝트.

## 기술 스택

- **언어:** Python 3.12
- **데이터 수집:** Discourse API (https://discuss.pytorch.kr/c/news/14.json)
- **LLM 요약:** Google Gemini Flash (무료 티어) — `google-genai` 패키지 사용
- **이메일 발송:** Gmail SMTP (smtplib, 표준라이브러리)
- **스케줄링:** GitHub Actions (daily cron)
- **비용:** $0 (모두 무료 티어)

## 수집 대상

- **소스 URL:** `https://discuss.pytorch.kr/c/news/14.json`
- Discourse API이므로 `.json` suffix를 붙이면 JSON 응답을 받을 수 있음
- 개별 글 본문: `https://discuss.pytorch.kr/t/{slug}/{topic_id}.json` 또는 `https://discuss.pytorch.kr/t/{topic_id}.json`

## 브리핑 범위 로직

- **화~금:** 전날(어제) 하루치 신규 글만
- **월요일:** 금/토/일 3일간 신규 글 포함
- **토/일:** 실행하지 않음 (cron에서 평일만)
- 글 생성일(`created_at`) 기준으로 필터링

## 브리핑 포맷 (이메일 본문)

이메일은 **HTML 형식**으로 발송. 구조:

```
제목: [AI 브리핑] 2026-03-02 PyTorch KR 뉴스 요약

본문:
1. 🔍 오늘의 트렌드 (전체 종합 요약)
   - 수집된 글 전체를 분석하여 3~5문장의 트렌드 종합 요약

2. 📋 개별 글 요약
   - 글 제목 (원문 링크)
     - 3줄 이내 핵심 요약
     - 태그/키워드

   (글 수만큼 반복)

3. 📊 통계
   - 총 N개 글 수집 (YYYY-MM-DD ~ YYYY-MM-DD)

4. 하단에 "이 브리핑은 AI(Gemini)가 자동 생성했습니다." 고지
```

## Gemini 프롬프트 설계

글 본문들을 모아 Gemini에 한 번에 보내서 요약. 프롬프트:

```
당신은 AI/ML 기술 트렌드 분석가입니다.
아래는 파이토치 한국 사용자 모임의 최근 게시글 목록입니다.

각 글에 대해:
1. 3줄 이내로 핵심 내용을 요약해주세요
2. 해당 글의 핵심 키워드를 2~3개 추출해주세요

그리고 전체 글을 종합하여:
3. 오늘의 AI/ML 트렌드를 3~5문장으로 정리해주세요

한국어로 응답해주세요.
응답은 반드시 아래 JSON 형식으로:
{
  "trend_summary": "전체 트렌드 종합...",
  "articles": [
    {
      "title": "글 제목",
      "summary": "3줄 요약",
      "keywords": ["키워드1", "키워드2"]
    }
  ]
}
```

## 이메일 설정

- **발신:** GitHub Secrets에 저장된 Gmail 계정 (`GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`)
- **수신:** `kyuetaek.oh@samsung.com`
- **SMTP:** smtp.gmail.com:587 (TLS)

## GitHub Actions Workflow

파일: `.github/workflows/daily-briefing.yml`

```yaml
name: Daily AI Briefing
on:
  schedule:
    # 오전 7시 KST = UTC 22:00 (전날)
    - cron: '0 22 * * 0-4'  # 일~목 22:00 UTC = 월~금 07:00 KST
  workflow_dispatch:  # 수동 실행 가능

jobs:
  briefing:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: python main.py
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          GMAIL_ADDRESS: ${{ secrets.GMAIL_ADDRESS }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
          RECIPIENT_EMAIL: ${{ secrets.RECIPIENT_EMAIL }}
```

## GitHub Secrets 필요 목록

| Secret 이름 | 값 |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio에서 발급한 API 키 |
| `GMAIL_ADDRESS` | 발신용 Gmail 주소 |
| `GMAIL_APP_PASSWORD` | Gmail 앱 비밀번호 (16자리) |
| `RECIPIENT_EMAIL` | `kyuetaek.oh@samsung.com` |

## 프로젝트 구조

```
pytorch-kr-briefing/
├── CLAUDE.md
├── README.md
├── requirements.txt          # google-genai, requests
├── main.py                   # 엔트리포인트 (오케스트레이션)
├── scraper.py                # Discourse API 크롤링
├── summarizer.py             # Gemini API 요약
├── emailer.py                # Gmail SMTP 발송
├── templates/
│   └── briefing.html         # 이메일 HTML 템플릿
└── .github/
    └── workflows/
        └── daily-briefing.yml
```

## 구현 시 주의사항

1. **Discourse API 요청 시 User-Agent 헤더 필수** — 없으면 403 가능
2. **Gemini 무료 티어 제한:** 분당 15회, 일 1,500회 — 글 본문을 하나씩 보내지 말고, 한 번에 배치로 보낼 것
3. **글 본문 크롤링:** 목록 API에는 본문이 없음. 각 topic의 first post를 별도 요청해야 함. `cooked` 필드에 HTML 본문이 있으니 텍스트만 추출
4. **월요일 판별:** Python에서 `datetime.now(KST).weekday() == 0`이면 월요일
5. **신규 글 없을 경우:** "오늘은 새로운 글이 없습니다"라는 간단한 이메일만 발송
6. **에러 핸들링:** API 실패 시 재시도 로직(최대 3회), 최종 실패 시에도 에러 내용을 이메일로 알림
7. **HTML 이메일:** 이메일 클라이언트 호환을 위해 인라인 CSS 사용, 복잡한 레이아웃 지양
8. **타임존:** 모든 시간 비교는 KST(Asia/Seoul) 기준

## 실행 방법 (로컬 테스트)

```bash
export GEMINI_API_KEY="your-key"
export GMAIL_ADDRESS="your-gmail"
export GMAIL_APP_PASSWORD="your-app-password"
export RECIPIENT_EMAIL="kyuetaek.oh@samsung.com"
python main.py
```