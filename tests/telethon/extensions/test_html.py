"""
Tests for `telethon.extensions.html`.
"""
from telethon.extensions import html
from telethon.tl.types import (
    MessageEntityBold,
    MessageEntityBlockquote,
    MessageEntityItalic,
    MessageEntityMentionName,
    MessageEntityPre,
    MessageEntityTextUrl,
    MessageEntityUrl,
)


def test_entity_edges():
    """
    Test that entities at the edges (start and end) don't crash.
    """
    text = 'Hello, world'
    entities = [MessageEntityBold(0, 5), MessageEntityBold(7, 5)]
    result = html.unparse(text, entities)
    assert result == '<strong>Hello</strong>, <strong>world</strong>'


def test_malformed_entities():
    """
    Test that malformed entity offsets from bad clients
    don't crash and produce the expected results.
    """
    text = '🏆Telegram Official Android Challenge is over🏆.'
    entities = [MessageEntityTextUrl(offset=2, length=43, url='https://example.com')]
    result = html.unparse(text, entities)
    assert result == '🏆<a href="https://example.com">Telegram Official Android Challenge is over</a>🏆.'


def test_trailing_malformed_entities():
    """
    Similar to `test_malformed_entities`, but for the edge
    case where the malformed entity offset is right at the end
    (note the lack of a trailing dot in the text string).
    """
    text = '🏆Telegram Official Android Challenge is over🏆'
    entities = [MessageEntityTextUrl(offset=2, length=43, url='https://example.com')]
    result = html.unparse(text, entities)
    assert result == '🏆<a href="https://example.com">Telegram Official Android Challenge is over</a>🏆'


def test_entities_together():
    """
    Test that an entity followed immediately by a different one behaves well.
    """
    original = '<strong>⚙️</strong><em>Settings</em>'
    stripped = '⚙️Settings'

    text, entities = html.parse(original)
    assert text == stripped
    assert entities == [MessageEntityBold(0, 2), MessageEntityItalic(2, 8)]

    text = html.unparse(text, entities)
    assert text == original


def test_nested_entities():
    """
    Test that an entity nested inside another one behaves well.
    """
    original = '<a href="https://example.com"><strong>Example</strong></a>'
    original_entities = [MessageEntityTextUrl(0, 7, url='https://example.com'), MessageEntityBold(0, 7)]
    stripped = 'Example'

    text, entities = html.parse(original)
    assert text == stripped
    assert entities == original_entities

    text = html.unparse(text, entities)
    assert text == original


def test_offset_at_emoji():
    """
    Tests that an entity starting at a emoji preserves the emoji.
    """
    text = 'Hi\n👉 See example'
    entities = [MessageEntityBold(0, 2), MessageEntityItalic(3, 2), MessageEntityBold(10, 7)]
    parsed = '<strong>Hi</strong>\n<em>👉</em> See <strong>example</strong>'

    assert html.parse(parsed) == (text, entities)
    assert html.unparse(text, entities) == parsed


def test_blockquote_expandable_none():
    """
    Test that blockquote with expandable=None doesn't crash.
    This can happen when the HTML parser passes None as attribute value.
    """
    text, entities = html.parse('<blockquote expandable>test</blockquote>')
    assert text == 'test'
    assert len(entities) == 1


def test_blockquote_expandable_sets_collapsed_true():
    text, entities = html.parse('<blockquote expandable>test</blockquote>')
    assert text == 'test'
    assert entities == [MessageEntityBlockquote(offset=0, length=4, collapsed=True)]


def test_blockquote_plain_sets_collapsed_none():
    text, entities = html.parse('<blockquote>test</blockquote>')
    assert text == 'test'
    assert entities == [MessageEntityBlockquote(offset=0, length=4, collapsed=None)]


def test_unparse_blockquote_collapsed_true_outputs_expandable():
    text = 'test'
    entities = [MessageEntityBlockquote(offset=0, length=4, collapsed=True)]
    assert html.unparse(text, entities) == '<blockquote expandable>test</blockquote>'


def test_unparse_blockquote_collapsed_false_outputs_plain():
    text = 'test'
    entities = [MessageEntityBlockquote(offset=0, length=4, collapsed=False)]
    assert html.unparse(text, entities) == '<blockquote>test</blockquote>'


def test_link_same_as_text_parses_as_url_entity():
    text, entities = html.parse('<a href="https://example.com">https://example.com</a>')
    assert text == "https://example.com"
    assert entities == [MessageEntityUrl(0, len(text))]


def test_tg_user_link_parses_as_mention_name():
    text, entities = html.parse('<a href="tg://user?id=12345">Alice</a>')
    assert text == "Alice"
    assert entities == [MessageEntityMentionName(offset=0, length=5, user_id=12345)]


def test_nested_same_tag_keeps_full_outer_range():
    text, entities = html.parse("<strong>a<strong>b</strong>c</strong>")
    assert text == "abc"
    assert entities == [MessageEntityBold(offset=0, length=3)]


def test_unparse_pre_entity_has_no_spurious_braces_or_indentation():
    text = "pip install -e . --upgrade"
    entities = [MessageEntityPre(offset=0, length=len(text), language="shell")]
    assert html.unparse(text, entities) == "<pre><code class='language-shell'>pip install -e . --upgrade</code></pre>"


def test_unparse_pre_entity_without_language_has_plain_code_tag():
    text = "pip install -e . --upgrade"
    entities = [MessageEntityPre(offset=0, length=len(text), language="")]
    assert html.unparse(text, entities) == "<pre><code>pip install -e . --upgrade</code></pre>"


def test_unparse_plain_text_keeps_quotes_but_escapes_markup_chars():
    text = 'say "yes" and \'no\' <b> & <i>'
    assert html.unparse(text, []) == 'say "yes" and \'no\' &lt;b&gt; &amp; &lt;i&gt;'


def test_unparse_formatted_text_keeps_quotes_but_escapes_markup_chars():
    text = 'say "yes" and \'no\' <b> & <i>'
    entities = [MessageEntityBold(offset=0, length=len(text))]
    assert html.unparse(text, entities) == '<strong>say "yes" and \'no\' &lt;b&gt; &amp; &lt;i&gt;</strong>'


def test_parse_unknown_tags_are_kept_as_plain_text():
    text, entities = html.parse("<unknown>hello</unknown>")
    assert text == "<unknown>hello</unknown>"
    assert entities == []


def test_parse_invalid_anchor_is_kept_as_plain_text():
    text, entities = html.parse("<a>hello</a>")
    assert text == "<a>hello</a>"
    assert entities == []


def test_parse_mismatched_unknown_closing_tag_is_kept_as_plain_text():
    source = "<unknown>hello</other>"
    text, entities = html.parse(source)
    assert text == source
    assert entities == []


def test_parse_non_ascii_tag_names_are_kept_as_plain_text():
    source = "<ьoaшщвыoaгвшыoaшгщыaшгщoaшгщфывoшaoывшщao>abc</aвлaшзщ>"
    text, entities = html.parse(source)
    assert text == source
    assert entities == []
