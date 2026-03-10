from scraper import _strip_html


def test_paragraphs_separated_by_newlines():
    html = "<p>첫 번째 문단입니다.</p><p>두 번째 문단입니다.</p>"
    result = _strip_html(html)
    assert "첫 번째 문단입니다.\n\n두 번째 문단입니다." == result


def test_list_items_preserved():
    html = "<ul><li>항목 1</li><li>항목 2</li></ul>"
    result = _strip_html(html)
    assert "- 항목 1\n- 항목 2" == result


def test_headings_preserved():
    html = "<h2>제목</h2><p>본문</p>"
    result = _strip_html(html)
    assert "## 제목\n\n본문" == result


def test_links_text_only():
    html = '<p>자세한 내용은 <a href="https://example.com">여기</a>를 참고하세요.</p>'
    result = _strip_html(html)
    assert "자세한 내용은 여기를 참고하세요." == result


def test_nested_tags():
    html = "<p><strong>중요:</strong> 이것은 <em>강조</em>입니다.</p>"
    result = _strip_html(html)
    assert "중요: 이것은 강조입니다." == result


def test_br_tags():
    html = "<p>줄 1<br>줄 2<br/>줄 3</p>"
    result = _strip_html(html)
    assert "줄 1\n줄 2\n줄 3" in result


def test_multiple_whitespace_collapsed():
    html = "<p>  여러   공백이    있는   텍스트  </p>"
    result = _strip_html(html)
    assert "여러 공백이 있는 텍스트" == result


def test_script_and_style_stripped():
    html = "<p>본문</p><script>alert('x')</script><style>.a{}</style><p>끝</p>"
    result = _strip_html(html)
    assert "alert" not in result
    assert "본문" in result
    assert "끝" in result
