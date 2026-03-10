from summarizer import _smart_truncate


def test_short_text_unchanged():
    text = "짧은 텍스트입니다."
    assert _smart_truncate(text, 100) == text


def test_truncate_at_paragraph_boundary():
    text = "첫 번째 문단입니다.\n\n두 번째 문단입니다.\n\n세 번째 아주 긴 문단입니다."
    result = _smart_truncate(text, 35)
    assert "세 번째" not in result
    assert result.endswith("[이하 생략]")


def test_truncate_at_sentence_boundary():
    text = "첫 번째 문장입니다. 두 번째 문장입니다. 세 번째 문장입니다. 네 번째 문장입니다."
    result = _smart_truncate(text, 45)
    assert result.endswith("[이하 생략]")
    # 문장 경계에서 잘려야 함
    assert "입니다." in result.replace("\n\n[이하 생략]", "")


def test_truncate_hard_cut_when_no_boundary():
    text = "가" * 200
    result = _smart_truncate(text, 100)
    assert result.endswith("[이하 생략]")
    assert len(result) <= 100 + len("\n\n[이하 생략]")


def test_no_marker_when_not_truncated():
    text = "짧은 글입니다."
    result = _smart_truncate(text, 3000)
    assert "[이하 생략]" not in result
