"""summarizer._reorder_summaries 단위 테스트"""

from summarizer import _reorder_summaries, _normalize_title


class TestNormalizeTitle:
    def test_basic(self):
        assert _normalize_title("Hello World!") == "helloworld"

    def test_korean(self):
        assert _normalize_title("PyTorch 2.0 출시") == "pytorch20출시"

    def test_spaces_and_punctuation(self):
        assert _normalize_title("  A - B : C  ") == "abc"


class TestReorderSummaries:
    def _make_articles(self, titles):
        return [
            {"title": t, "url": f"https://example.com/{i}", "content": f"본문 {i}"}
            for i, t in enumerate(titles)
        ]

    def test_correct_order_with_article_id(self):
        """article_id가 정확하면 그대로 매칭"""
        originals = self._make_articles(["글A", "글B", "글C"])
        llm_output = [
            {"article_id": 1, "title": "글A", "summary": "요약A", "keywords": ["a"]},
            {"article_id": 2, "title": "글B", "summary": "요약B", "keywords": ["b"]},
            {"article_id": 3, "title": "글C", "summary": "요약C", "keywords": ["c"]},
        ]
        result = _reorder_summaries(originals, llm_output)
        assert [r["summary"] for r in result] == ["요약A", "요약B", "요약C"]

    def test_reorder_shuffled_article_id(self):
        """LLM이 순서를 섞어도 article_id로 올바르게 매칭"""
        originals = self._make_articles(["글A", "글B", "글C"])
        llm_output = [
            {"article_id": 3, "title": "글C", "summary": "요약C", "keywords": ["c"]},
            {"article_id": 1, "title": "글A", "summary": "요약A", "keywords": ["a"]},
            {"article_id": 2, "title": "글B", "summary": "요약B", "keywords": ["b"]},
        ]
        result = _reorder_summaries(originals, llm_output)
        assert [r["summary"] for r in result] == ["요약A", "요약B", "요약C"]

    def test_fallback_to_title_matching(self):
        """article_id가 없으면 제목으로 매칭"""
        originals = self._make_articles(["글A", "글B", "글C"])
        llm_output = [
            {"title": "글C", "summary": "요약C", "keywords": ["c"]},
            {"title": "글A", "summary": "요약A", "keywords": ["a"]},
            {"title": "글B", "summary": "요약B", "keywords": ["b"]},
        ]
        result = _reorder_summaries(originals, llm_output)
        assert [r["summary"] for r in result] == ["요약A", "요약B", "요약C"]

    def test_missing_summary_fallback(self):
        """LLM이 일부 글을 빠뜨리면 원본 content로 폴백"""
        originals = self._make_articles(["글A", "글B", "글C"])
        llm_output = [
            {"article_id": 1, "title": "글A", "summary": "요약A", "keywords": ["a"]},
            {"article_id": 3, "title": "글C", "summary": "요약C", "keywords": ["c"]},
        ]
        result = _reorder_summaries(originals, llm_output)
        assert result[0]["summary"] == "요약A"
        assert result[1]["summary"] == "본문 1"  # 폴백
        assert result[2]["summary"] == "요약C"

    def test_title_with_minor_differences(self):
        """LLM이 제목에 공백/특수문자를 약간 바꿔도 매칭"""
        originals = self._make_articles(["PyTorch 2.0: 새로운 시작"])
        llm_output = [
            {"title": "PyTorch 2.0 : 새로운 시작", "summary": "요약", "keywords": []},
        ]
        result = _reorder_summaries(originals, llm_output)
        assert result[0]["summary"] == "요약"

    def test_wrong_article_id_corrected_by_title(self):
        """article_id가 잘못되었지만 제목으로 복구"""
        originals = self._make_articles(["글A", "글B"])
        # article_id가 모두 잘못됨
        llm_output = [
            {"article_id": 99, "title": "글B", "summary": "요약B", "keywords": []},
            {"article_id": 100, "title": "글A", "summary": "요약A", "keywords": []},
        ]
        result = _reorder_summaries(originals, llm_output)
        assert result[0]["summary"] == "요약A"
        assert result[1]["summary"] == "요약B"

    def test_empty_llm_response(self):
        """LLM이 빈 배열을 반환하면 모두 폴백"""
        originals = self._make_articles(["글A", "글B"])
        result = _reorder_summaries(originals, [])
        assert len(result) == 2
        assert result[0]["title"] == "글A"
        assert result[1]["title"] == "글B"


class TestProviderFallback:
    def _article(self):
        return {
            "title": "테스트 글",
            "url": "https://example.com/a",
            "content": "PyTorch가 새 기능을 발표했다.",
            "source": "pytorch_kr",
        }

    def test_ollama_success_does_not_call_groq(self, monkeypatch):
        """Ollama가 유효한 JSON을 반환하면 Groq fallback을 호출하지 않는다."""
        import summarizer

        calls = []
        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        monkeypatch.setenv("LLM_FALLBACK_PROVIDER", "groq")

        def fake_ollama(prompt):
            calls.append("ollama")
            return {
                "trend_summary": "로컬 요약 성공",
                "articles": [
                    {
                        "article_id": 1,
                        "title": "테스트 글",
                        "summary": "새 기능 발표 요약",
                        "keywords": ["PyTorch"],
                    }
                ],
            }

        def fake_groq(client, prompt):
            calls.append("groq")
            raise AssertionError("Groq should not be called")

        monkeypatch.setattr(summarizer, "_call_ollama", fake_ollama)
        monkeypatch.setattr(summarizer, "_call_groq", fake_groq)

        result = summarizer.summarize_articles([self._article()])

        assert result["trend_summary"] == "로컬 요약 성공"
        assert result["articles"][0]["summary"] == "새 기능 발표 요약"
        assert calls == ["ollama"]

    def test_ollama_failure_falls_back_to_groq(self, monkeypatch):
        """Ollama 호출이 실패하면 Groq provider로 재시도한다."""
        import summarizer

        calls = []
        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        monkeypatch.setenv("LLM_FALLBACK_PROVIDER", "groq")
        monkeypatch.setenv("GROQ_API_KEY", "dummy")

        def fake_ollama(prompt):
            calls.append("ollama")
            raise RuntimeError("local model unavailable")

        def fake_groq(client, prompt):
            calls.append("groq")
            return {
                "trend_summary": "Groq fallback 성공",
                "articles": [
                    {
                        "article_id": 1,
                        "title": "테스트 글",
                        "summary": "fallback 요약",
                        "keywords": ["fallback"],
                    }
                ],
            }

        monkeypatch.setattr(summarizer, "_call_ollama", fake_ollama)
        monkeypatch.setattr(summarizer, "_call_groq", fake_groq)

        result = summarizer.summarize_articles([self._article()])

        assert result["trend_summary"] == "Groq fallback 성공"
        assert result["articles"][0]["summary"] == "fallback 요약"
        assert calls == ["ollama", "groq"]

    def test_invalid_ollama_shape_falls_back_to_groq(self, monkeypatch):
        """Ollama가 JSON은 반환했지만 필수 shape가 없으면 fallback한다."""
        import summarizer

        calls = []
        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        monkeypatch.setenv("LLM_FALLBACK_PROVIDER", "groq")
        monkeypatch.setenv("GROQ_API_KEY", "dummy")

        def fake_ollama(prompt):
            calls.append("ollama")
            return {"message": "not expected shape"}

        def fake_groq(client, prompt):
            calls.append("groq")
            return {
                "trend_summary": "shape fallback 성공",
                "articles": [
                    {
                        "article_id": 1,
                        "title": "테스트 글",
                        "summary": "shape fallback 요약",
                        "keywords": ["shape"],
                    }
                ],
            }

        monkeypatch.setattr(summarizer, "_call_ollama", fake_ollama)
        monkeypatch.setattr(summarizer, "_call_groq", fake_groq)

        result = summarizer.summarize_articles([self._article()])

        assert result["trend_summary"] == "shape fallback 성공"
        assert result["articles"][0]["summary"] == "shape fallback 요약"
        assert calls == ["ollama", "groq"]

    def test_empty_ollama_articles_falls_back_to_groq(self, monkeypatch):
        """Ollama가 articles를 누락하면 원문 폴백 대신 Groq fallback을 사용한다."""
        import summarizer

        calls = []
        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        monkeypatch.setenv("LLM_FALLBACK_PROVIDER", "groq")
        monkeypatch.setenv("GROQ_API_KEY", "dummy")

        def fake_ollama(prompt):
            calls.append("ollama")
            return {"trend_summary": "불완전", "articles": []}

        def fake_groq(client, prompt):
            calls.append("groq")
            return {
                "trend_summary": "empty articles fallback 성공",
                "articles": [
                    {
                        "article_id": 1,
                        "title": "테스트 글",
                        "summary": "empty articles fallback 요약",
                        "keywords": ["empty"],
                    }
                ],
            }

        monkeypatch.setattr(summarizer, "_call_ollama", fake_ollama)
        monkeypatch.setattr(summarizer, "_call_groq", fake_groq)

        result = summarizer.summarize_articles([self._article()])

        assert result["trend_summary"] == "empty articles fallback 성공"
        assert result["articles"][0]["summary"] == "empty articles fallback 요약"
        assert calls == ["ollama", "groq"]
