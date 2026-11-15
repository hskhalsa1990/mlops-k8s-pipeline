from check_docs import broken_links


def test_markdown_links_resolve():
    assert broken_links() == []
