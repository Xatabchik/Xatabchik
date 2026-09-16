"""Поле поиска ключей: type=text, чтобы WebView не рисовал второй крестик."""
from __future__ import annotations

import re

from webapp_frontend_src import mini_app_html


def test_keys_search_input_is_text_with_custom_clear_button():
    html = mini_app_html()
    match = re.search(
        r'<input\b[^>]*\bid="keys-search-input"[^>]*>',
        html,
    )
    assert match, "в app.html должно быть поле #keys-search-input"
    tag = match.group(0)
    assert 'type="text"' in tag
    assert 'type="search"' not in tag
    assert 'id="keys-search-clear"' in html
