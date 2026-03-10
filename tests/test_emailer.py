from emailer import build_html


def test_index_based_matching():
    """LLM이 제목을 변경해도 순서 기반으로 매칭"""
    summary_data = {
        "trend_summary": "트렌드 요약",
        "articles": [
            {"title": "약간 다른 제목 A", "summary": "요약 A", "keywords": ["k1"]},
            {"title": "약간 다른 제목 B", "summary": "요약 B", "keywords": ["k2"]},
        ],
    }
    all_articles = [
        {"title": "원본 제목 A", "url": "https://a.com", "content": "내용A", "source": "pytorch_kr"},
        {"title": "원본 제목 B", "url": "https://b.com", "content": "내용B", "source": "pytorch_kr"},
    ]
    articles_by_source = {"pytorch_kr": all_articles}

    html = build_html(summary_data, all_articles, articles_by_source, "2026-03-11")

    assert "요약 A" in html
    assert "요약 B" in html
    assert "원본 제목 A" in html  # 원본 제목 사용


def test_fallback_when_summary_missing():
    """요약 결과가 부족할 때 폴백"""
    summary_data = {
        "trend_summary": "트렌드",
        "articles": [
            {"title": "제목 A", "summary": "요약 A", "keywords": ["k1"]},
        ],
    }
    all_articles = [
        {"title": "제목 A", "url": "https://a.com", "content": "내용A", "source": "pytorch_kr"},
        {"title": "제목 B", "url": "https://b.com", "content": "내용B가 꽤 긴 텍스트", "source": "pytorch_kr"},
    ]
    articles_by_source = {"pytorch_kr": all_articles}

    html = build_html(summary_data, all_articles, articles_by_source, "2026-03-11")

    assert "요약 A" in html
    assert "제목 B" in html  # 폴백이지만 제목은 표시


def test_multi_source_matching():
    """다중 소스에서도 인덱스 순서대로 매칭"""
    summary_data = {
        "trend_summary": "트렌드",
        "articles": [
            {"title": "PT글", "summary": "PT요약", "keywords": ["k1"]},
            {"title": "GN글", "summary": "GN요약", "keywords": ["k2"]},
        ],
    }
    all_articles = [
        {"title": "PT원본", "url": "https://a.com", "content": "PT내용", "source": "pytorch_kr"},
        {"title": "GN원본", "url": "https://b.com", "content": "GN내용", "source": "geeknews"},
    ]
    articles_by_source = {
        "pytorch_kr": [all_articles[0]],
        "geeknews": [all_articles[1]],
    }

    html = build_html(summary_data, all_articles, articles_by_source, "2026-03-11")

    assert "PT요약" in html
    assert "GN요약" in html
