"""
Tests for `telethon.extensions.html`.
"""
from types import SimpleNamespace

from telethon.extensions import html
from telethon.tl import types as tl_types
from telethon.tl.types import (
    MessageEntityBold,
    MessageEntityBlockquote,
    MessageEntityItalic,
    MessageEntityMentionName,
    MessageEntityPre,
    MessageEntitySpoiler,
    MessageEntityStrike,
    MessageEntityTextUrl,
    MessageEntityUnderline,
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


def test_parse_bot_api_alias_tags():
    source = (
        "<ins>u</ins>"
        "<strike>s</strike>"
        "<spoiler>x</spoiler>"
        '<span class="tg-spoiler">y</span>'
    )
    text, entities = html.parse(source)

    assert text == "usxy"
    assert entities == [
        MessageEntityUnderline(offset=0, length=1),
        MessageEntityStrike(offset=1, length=1),
        MessageEntitySpoiler(offset=2, length=1),
        MessageEntitySpoiler(offset=3, length=1),
    ]


def test_parse_generic_span_is_kept_as_plain_text():
    source = '<span class="note">hello</span>'
    text, entities = html.parse(source)

    assert text == source
    assert entities == []


def test_parse_line_break_and_block_tags():
    text, entities = html.parse("a<br>b<p>c</p><div>d</div>")

    assert text == "a\nb\nc\nd"
    assert entities == []


def test_parse_heading_tags_as_bold_blocks():
    text, entities = html.parse("<h1>Title</h1><h2>Sub</h2>")

    assert text == "Title\nSub"
    assert entities == [
        MessageEntityBold(offset=0, length=5),
        MessageEntityBold(offset=6, length=3),
    ]


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


def test_rich_message_to_html_renders_live_layer_227_sample():
    rich_message = tl_types.RichMessage(
        blocks=[
            tl_types.PageBlockParagraph(
                text=tl_types.TextConcat(
                    texts=[
                        tl_types.TextPlain('👤 '),
                        tl_types.TextBold(tl_types.TextPlain('/home/esconine:')),
                        tl_types.TextPlain(
                            ' Вы размышляете | ✅ | (+10 IQ) Решенный пример:'
                        ),
                    ]
                )
            ),
            tl_types.PageBlockMath('8 \\times 5 = 40'),
        ],
        photos=[],
        documents=[],
    )

    assert html.rich_message_to_html(rich_message) == (
        '👤 <b>/home/esconine:</b> Вы размышляете | ✅ | (+10 IQ) Решенный пример:\n'
        '<pre><code class="math">8 \\times 5 = 40</code></pre>'
    )


def test_rich_message_text_nodes_escape_text_and_attributes():
    rich_message = tl_types.RichMessage(
        blocks=[
            tl_types.PageBlockParagraph(
                tl_types.TextConcat(
                    texts=[
                        tl_types.TextPlain('<plain & "quoted">'),
                        tl_types.TextUrl(
                            tl_types.TextPlain(' link <x>'),
                            'https://example.com/?a=1&b=<2>',
                            0,
                        ),
                        tl_types.TextEmail(tl_types.TextPlain(' mail'), 'a&b@example.com'),
                        tl_types.TextPhone(tl_types.TextPlain(' phone'), '+1&2'),
                        tl_types.TextMentionName(tl_types.TextPlain(' Alice'), 42),
                        tl_types.TextImage(99, 16, 16),
                    ]
                )
            )
        ],
        photos=[],
        documents=[],
    )

    assert html.rich_message_to_html(rich_message) == (
        '&lt;plain &amp; &quot;quoted&quot;&gt;'
        '<a href="https://example.com/?a=1&amp;b=&lt;2&gt;"> link &lt;x&gt;</a>'
        '<a href="mailto:a&amp;b@example.com"> mail</a>'
        '<a href="tel:+1&amp;2"> phone</a>'
        '<a href="tg://user?id=42"> Alice</a>'
        '[img:99]'
    )


def test_rich_message_blocks_and_lists_render_to_html():
    rich_message = tl_types.RichMessage(
        blocks=[
            tl_types.PageBlockPreformatted(tl_types.TextPlain('x < y'), 'python'),
            tl_types.PageBlockHeader(tl_types.TextPlain('Title <&>')),
            tl_types.PageBlockBlockquote(
                tl_types.TextPlain('quote <b>'),
                tl_types.TextPlain('ignored'),
            ),
            tl_types.PageBlockList(
                items=[
                    tl_types.PageListItemText(tl_types.TextPlain('one')),
                    tl_types.PageListItemText(tl_types.TextBold(tl_types.TextPlain('two'))),
                ]
            ),
            tl_types.PageBlockDivider(),
        ],
        photos=[],
        documents=[],
    )

    assert html.rich_message_to_html(rich_message) == (
        '<pre><code class="language-python">x &lt; y</code></pre>\n'
        '<b>Title &lt;&amp;&gt;</b>\n'
        '<blockquote>quote &lt;b&gt;</blockquote>\n'
        '• one\n'
        '• <b>two</b>\n\n'
        '---'
    )


def test_message_to_html_prefers_rich_message_and_falls_back_to_unparse():
    rich_message = tl_types.RichMessage(
        blocks=[tl_types.PageBlockParagraph(tl_types.TextPlain('rich'))],
        photos=[],
        documents=[],
    )

    assert html.message_to_html(
        SimpleNamespace(rich_message=rich_message, message='<plain>', entities=[])
    ) == 'rich'
    assert html.message_to_html(
        SimpleNamespace(rich_message=None, message='<plain>', entities=[])
    ) == '&lt;plain&gt;'


def test_rich_message_unknown_future_types_are_ignored():
    class PageBlockFuture:
        pass

    class TextFuture:
        pass

    assert html._render_text_node(TextFuture()) == ''
    assert html.rich_message_to_html(SimpleNamespace(blocks=[PageBlockFuture()])) == ''


def test_rich_message_renders_extra_inline_text_tags():
    rich_message = tl_types.RichMessage(
        blocks=[
            tl_types.PageBlockParagraph(
                tl_types.TextConcat(
                    texts=[
                        tl_types.TextAutoUrl(tl_types.TextPlain('https://example.com/?a=<b>')),
                        tl_types.TextPlain(' '),
                        tl_types.TextAutoEmail(tl_types.TextPlain('me&you@example.com')),
                        tl_types.TextPlain(' '),
                        tl_types.TextAutoPhone(tl_types.TextPlain('+1&2')),
                        tl_types.TextPlain(' '),
                        tl_types.TextMath('x < y'),
                        tl_types.TextPlain(' '),
                        tl_types.TextCustomEmoji(123, '🔥'),
                        tl_types.TextPlain(' '),
                        tl_types.TextHashtag(tl_types.TextPlain('#tag')),
                        tl_types.TextPlain(' '),
                        tl_types.TextBotCommand(tl_types.TextPlain('/start')),
                    ]
                )
            )
        ],
        photos=[],
        documents=[],
    )

    assert html.rich_message_to_html(rich_message) == (
        '<a href="https://example.com/?a=&lt;b&gt;">'
        'https://example.com/?a=&lt;b&gt;</a> '
        '<a href="mailto:me&amp;you@example.com">me&amp;you@example.com</a> '
        '<a href="tel:+1&amp;2">+1&amp;2</a> '
        '<code class="math">x &lt; y</code> '
        '<tg-emoji emoji-id="123">🔥</tg-emoji> '
        '#tag /start'
    )


def test_rich_message_renders_extra_page_blocks():
    rich_message = tl_types.RichMessage(
        blocks=[
            tl_types.PageBlockSubtitle(tl_types.TextPlain('Sub')),
            tl_types.PageBlockHeading1(tl_types.TextPlain('Heading')),
            tl_types.PageBlockFooter(tl_types.TextPlain('Foot')),
            tl_types.PageBlockKicker(tl_types.TextPlain('Kick')),
            tl_types.PageBlockAuthorDate(tl_types.TextPlain('Author'), None),
            tl_types.PageBlockPullquote(tl_types.TextPlain('Pull'), tl_types.TextEmpty()),
            tl_types.PageBlockBlockquoteBlocks(
                blocks=[tl_types.PageBlockParagraph(tl_types.TextPlain('Nested'))],
                caption=tl_types.TextEmpty(),
            ),
            tl_types.PageBlockDetails(
                blocks=[tl_types.PageBlockParagraph(tl_types.TextPlain('Detail'))],
                title=tl_types.TextPlain('More'),
                open=True,
            ),
            tl_types.PageBlockCover(tl_types.PageBlockParagraph(tl_types.TextPlain('Cover'))),
            tl_types.PageBlockCollage(
                items=[tl_types.PageBlockParagraph(tl_types.TextPlain('Collage'))],
                caption=tl_types.TextEmpty(),
            ),
        ],
        photos=[],
        documents=[],
    )

    assert html.rich_message_to_html(rich_message) == (
        '<b>Sub</b>\n'
        '<b>Heading</b>\n'
        '<i>Foot</i>\n'
        '<i>Kick</i>\n'
        '<i>Author</i>\n'
        '<blockquote>Pull</blockquote>\n'
        '<blockquote>Nested</blockquote>\n'
        '<b>More</b>\n'
        'Detail\n'
        'Cover\n'
        'Collage'
    )


def test_rich_message_renders_deep_block_formatting():
    caption = tl_types.PageCaption(
        text=tl_types.TextPlain('Caption <x>'),
        credit=tl_types.TextPlain('Credit & co'),
    )
    rich_message = tl_types.RichMessage(
        blocks=[
            tl_types.PageBlockTable(
                title=tl_types.TextPlain('Stats'),
                rows=[
                    tl_types.PageTableRow(
                        cells=[
                            tl_types.PageTableCell(
                                header=True,
                                text=tl_types.TextPlain('Name'),
                            ),
                            tl_types.PageTableCell(
                                header=True,
                                text=tl_types.TextPlain('Value'),
                            ),
                        ]
                    ),
                    tl_types.PageTableRow(
                        cells=[
                            tl_types.PageTableCell(text=tl_types.TextPlain('IQ')),
                            tl_types.PageTableCell(text=tl_types.TextPlain('+10')),
                        ]
                    ),
                ],
            ),
            tl_types.PageBlockRelatedArticles(
                title=tl_types.TextPlain('More'),
                articles=[
                    tl_types.PageRelatedArticle(
                        url='https://example.com/?a=<b>',
                        webpage_id=1,
                        title='Article <1>',
                        description='Desc & more',
                    )
                ],
            ),
            tl_types.PageBlockEmbed(
                caption=caption,
                url='https://video.example/?q=<x>',
            ),
            tl_types.PageBlockPhoto(photo_id=1, caption=caption),
            tl_types.PageBlockMap(
                geo=object(),
                zoom=1,
                w=10,
                h=10,
                caption=tl_types.PageCaption(tl_types.TextPlain('Map'), tl_types.TextEmpty()),
            ),
        ],
        photos=[],
        documents=[],
    )

    assert html.rich_message_to_html(rich_message) == (
        '<b>Stats</b>\n'
        '<b>Name</b> | <b>Value</b>\n'
        'IQ | +10\n'
        '<b>More</b>\n'
        '• <a href="https://example.com/?a=&lt;b&gt;">Article &lt;1&gt;</a>'
        ' — Desc &amp; more\n'
        '<a href="https://video.example/?q=&lt;x&gt;">[embed]</a>\n'
        'Caption &lt;x&gt;\n'
        '<i>Credit &amp; co</i>\n'
        '[media]\n'
        'Caption &lt;x&gt;\n'
        '<i>Credit &amp; co</i>\n'
        '[map]\n'
        'Map'
    )
