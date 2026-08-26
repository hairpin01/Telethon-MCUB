"""
Tests for `telethon.extensions.html`.
"""
from types import SimpleNamespace

from telethon.extensions import html, richparser
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


def test_richparser_math_block_keeps_source():
    message = richparser.html_to_input_rich_message(
        "<tg-math-block>E=mc^2</tg-math-block>"
    )

    assert isinstance(message, tl_types.InputRichMessage)
    assert isinstance(message.blocks[0], tl_types.PageBlockMath)
    assert message.blocks[0].source == "E=mc^2"


def test_richparser_inline_math_keeps_source():
    message = richparser.html_to_input_rich_message(
        "<p>Inline <tg-math>x^2</tg-math></p>"
    )

    paragraph = message.blocks[0]
    assert isinstance(paragraph, tl_types.PageBlockParagraph)
    assert isinstance(paragraph.text, tl_types.TextConcat)
    assert isinstance(paragraph.text.texts[1], tl_types.TextMath)
    assert paragraph.text.texts[1].source == "x^2"


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

    assert richparser.rich_message_to_html(rich_message) == (
        '<p>👤 <b>/home/esconine:</b> Вы размышляете | ✅ | (+10 IQ) Решенный пример:</p>'
        '<tg-math-block>8 \\times 5 = 40</tg-math-block>'
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

    assert richparser.rich_message_to_html(rich_message) == (
        '<p>&lt;plain &amp; &quot;quoted&quot;&gt;'
        '<a href="https://example.com/?a=1&amp;b=&lt;2&gt;"> link &lt;x&gt;</a>'
        '<a href="mailto:a&amp;b@example.com"> mail</a>'
        '<a href="tel:+1&amp;2"> phone</a>'
        '<a href="tg://user?id=42"> Alice</a>'
        '[img:99]</p>'
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

    assert richparser.rich_message_to_html(rich_message) == (
        '<pre><code class="language-python">x &lt; y</code></pre>'
        '<b>Title &lt;&amp;&gt;</b>\n'
        '<blockquote>quote &lt;b&gt;<cite>ignored</cite></blockquote>'
        '<ul><li>one</li><li><b>two</b></li></ul>'
        '<hr>'
    )


def test_message_to_html_prefers_rich_message_and_falls_back_to_unparse():
    rich_message = tl_types.RichMessage(
        blocks=[tl_types.PageBlockParagraph(tl_types.TextPlain('rich'))],
        photos=[],
        documents=[],
    )

    assert richparser.message_to_html(
        SimpleNamespace(rich_message=rich_message, message='<plain>', entities=[])
    ) == '<p>rich</p>'
    assert richparser.message_to_html(
        SimpleNamespace(rich_message=None, message='<plain>', entities=[])
    ) == '&lt;plain&gt;'


def test_rich_message_unknown_future_types_are_ignored():
    class PageBlockFuture:
        pass

    class TextFuture:
        pass

    assert richparser._render_text_node(TextFuture()) == ''
    assert richparser.rich_message_to_html(SimpleNamespace(blocks=[PageBlockFuture()])) == ''


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

    assert richparser.rich_message_to_html(rich_message) == (
        '<p>'
        '<a href="https://example.com/?a=&lt;b&gt;">'
        'https://example.com/?a=&lt;b&gt;</a> '
        '<a href="mailto:me&amp;you@example.com">me&amp;you@example.com</a> '
        '<a href="tel:+1&amp;2">+1&amp;2</a> '
        '<tg-math>x &lt; y</tg-math> '
        '<tg-emoji emoji-id="123">🔥</tg-emoji> '
        '#tag /start</p>'
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

    rendered = richparser.rich_message_to_html(rich_message)
    assert '<h1>Heading</h1>' in rendered
    assert '<footer>Foot</footer>' in rendered
    assert '<aside>Pull</aside>' in rendered
    assert '<details open><summary>More</summary><p>Detail</p></details>' in rendered


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

    rendered = richparser.rich_message_to_html(rich_message)
    assert '<table><caption>Stats</caption><tr><th>Name</th><th>Value</th></tr>' in rendered
    assert '<tr><td>IQ</td><td>+10</td></tr></table>' in rendered
    assert 'Article &lt;1&gt;' in rendered


def test_rich_message_renders_media_links_and_new_block_flags():
    # Received RichMessage blocks carry Telegram's page-block media ids. When
    # sending InputRichMessageHTML, the id in tg://photo?id=... must instead
    # match the string id from InputRichFilePhoto/InputRichFileDocument.
    rich_message = tl_types.RichMessage(
        blocks=[
            tl_types.PageBlockPhoto(
                photo_id=10,
                caption=tl_types.PageCaption(tl_types.TextPlain('Photo'), tl_types.TextEmpty()),
                spoiler=True,
            ),
            tl_types.PageBlockVideo(
                video_id=11,
                caption=tl_types.PageCaption(tl_types.TextPlain('Video'), tl_types.TextEmpty()),
            ),
            tl_types.PageBlockAudio(
                audio_id=12,
                caption=tl_types.PageCaption(tl_types.TextPlain('Audio'), tl_types.TextEmpty()),
            ),
            tl_types.InputPageBlockMap(
                geo=object(),
                zoom=1,
                w=10,
                h=10,
                caption=tl_types.PageCaption(tl_types.TextPlain('Input map'), tl_types.TextEmpty()),
            ),
            tl_types.PageBlockUnsupported(),
        ],
        photos=[],
        documents=[],
    )

    assert richparser.rich_message_to_html(rich_message) == (
        '<tg-spoiler><a href="tg://photo?id=10">[photo]</a></tg-spoiler>\n'
        'Photo\n'
        '<a href="tg://video?id=11">[video]</a>\n'
        'Video\n'
        '<a href="tg://audio?id=12">[audio]</a>\n'
        'Audio\n'
        '[map]\n'
        'Input map\n'
        '[unsupported]'
    )


def test_rich_message_renders_checkbox_list_items():
    rich_message = tl_types.RichMessage(
        blocks=[
            tl_types.PageBlockList(
                items=[
                    tl_types.PageListItemText(
                        tl_types.TextPlain('done'), checkbox=True, checked=True
                    ),
                    tl_types.PageListItemBlocks(
                        [tl_types.PageBlockParagraph(tl_types.TextPlain('todo'))],
                        checkbox=True,
                        checked=False,
                    ),
                ]
            ),
            tl_types.PageBlockOrderedList(
                items=[
                    tl_types.PageListOrderedItemText(
                        tl_types.TextPlain('ordered'), checkbox=True, checked=True, num='A'
                    )
                ]
            ),
        ],
        photos=[],
        documents=[],
    )

    assert richparser.rich_message_to_html(rich_message) == (
        '<ul><li><input type="checkbox" checked>done</li><li><input type="checkbox"><p>todo</p></li></ul>'
        '<ol><li data-num="A"><input type="checkbox" checked>ordered</li></ol>'
    )


def test_richparser_preserves_inline_code_and_semantic_inline_tags():
    message = richparser.html_to_input_rich_message(
        '<p><b>bold <code>&lt;x&gt;</code></b> <mark>mark</mark> '
        '<tg-spoiler>spoiler</tg-spoiler> <tg-math>x^2</tg-math></p>'
        '<tg-math-block>E=mc^2</tg-math-block>'
    )
    paragraph = message.blocks[0].text

    assert isinstance(paragraph, tl_types.TextConcat)
    assert isinstance(paragraph.texts[0].text.texts[1], tl_types.TextFixed)
    assert paragraph.texts[0].text.texts[1].text.text == '<x>'
    assert isinstance(paragraph.texts[2], tl_types.TextMarked)
    assert isinstance(paragraph.texts[4], tl_types.TextSpoiler)
    assert richparser.rich_message_to_html(message) == (
        '<p><b>bold <code>&lt;x&gt;</code></b> <mark>mark</mark> '
        '<tg-spoiler>spoiler</tg-spoiler> <tg-math>x^2</tg-math></p>'
        '<tg-math-block>E=mc^2</tg-math-block>'
    )


def test_richparser_renders_semantic_table_list_and_blocks():
    message = tl_types.RichMessage(
        blocks=[
            tl_types.PageBlockHeading2(tl_types.TextPlain('Heading')),
            tl_types.PageBlockTable(
                tl_types.TextPlain('Stats'),
                [tl_types.PageTableRow([
                    tl_types.PageTableCell(
                            text=tl_types.TextPlain('Value'), align_right=True,
                            valign_bottom=True, colspan=2
                    )
                ])],
                bordered=True, striped=True, compact=True,
            ),
            tl_types.PageBlockList([tl_types.PageListItemText(tl_types.TextPlain('item'))]),
        ], photos=[], documents=[]
    )

    assert richparser.rich_message_to_html(message) == (
        '<h2>Heading</h2><table bordered striped compact><caption>Stats</caption>'
        '<tr><td align="right" valign="bottom" colspan="2">Value</td></tr></table>'
        '<ul><li>item</li></ul>'
    )


def test_richparser_button_rows_round_trip_rich_labels_and_styles():
    source = (
        '<tg-button-row align="center">'
        '<tg-button type="callback_data" data="ping" requires-password="true" style="primary">'
        '<b>Ping</b> <tg-emoji emoji-id="42">X</tg-emoji></tg-button>'
        '<tg-button type="url" url="https://example.com" style="danger">Danger</tg-button>'
        '<tg-button type="web_app" url="https://app.example" style="success">App</tg-button>'
        '<tg-button type="copy_text" text="copy" style="link">Copy</tg-button>'
        '<tg-button type="disabled">Disabled</tg-button>'
        '</tg-button-row>'
    )
    row = richparser.html_to_input_rich_message(source).blocks[0]

    assert isinstance(row, tl_types.PageBlockButtonRow)
    assert row.align_center is True
    assert richparser.html_to_input_rich_message(
        '<tg-button-row align="left"><tg-button type="disabled">Left</tg-button></tg-button-row>'
    ).blocks[0].align_left is True
    assert row.buttons[0].type.data == b'ping'
    assert row.buttons[0].type.requires_password is True
    assert isinstance(row.buttons[0].text.texts[0], tl_types.TextBold)
    assert isinstance(row.buttons[0].text.texts[1], tl_types.TextPlain)
    assert isinstance(row.buttons[0].text.texts[2], tl_types.TextCustomEmoji)
    assert [button.style.to_dict() for button in row.buttons[:4]] == [
        {'_': 'RichButtonStyle', 'bg_primary': True, 'bg_danger': None, 'bg_success': None, 'link': None},
        {'_': 'RichButtonStyle', 'bg_primary': None, 'bg_danger': True, 'bg_success': None, 'link': None},
        {'_': 'RichButtonStyle', 'bg_primary': None, 'bg_danger': None, 'bg_success': True, 'link': None},
        {'_': 'RichButtonStyle', 'bg_primary': None, 'bg_danger': None, 'bg_success': None, 'link': True},
    ]
    assert richparser.rich_message_to_html(tl_types.RichMessage([row], [], [])) == source


def test_richparser_button_callback_bytes_and_login_switch_round_trip():
    row = tl_types.PageBlockButtonRow([
        tl_types.PageButton(tl_types.TextPlain('Bytes'), tl_types.InlineButtonTypeCallback(b'\xff\x00')),
        tl_types.PageButton(tl_types.TextPlain('Login'), tl_types.InlineButtonTypeUrlAuth('https://login', 3, 'Forward')),
        tl_types.PageButton(tl_types.TextPlain('Switch'), tl_types.InlineButtonTypeSwitchInline('query', True)),
    ], align_right=True)
    rendered = richparser.rich_message_to_html(tl_types.RichMessage([row], [], []))
    parsed = richparser.html_to_input_rich_message(rendered).blocks[0]

    assert rendered == (
        '<tg-button-row align="right"><tg-button type="callback_data" data-base64="/wA=">Bytes</tg-button>'
        '<tg-button type="login_url" url="https://login" button-id="3" forward-text="Forward">Login</tg-button>'
        '<tg-button type="switch_inline_query_current_chat" query="query">Switch</tg-button></tg-button-row>'
    )
    assert parsed.buttons[0].type.data == b'\xff\x00'
    assert isinstance(parsed.buttons[1].type, tl_types.InlineButtonTypeUrlAuth)
    assert parsed.buttons[2].type.same_peer is True
    malformed = richparser.html_to_input_rich_message(
        '<tg-button-row><tg-button type="callback_data" data="fallback" '
        'data-base64="not base64!">Fallback</tg-button></tg-button-row>'
    )
    assert malformed.blocks[0].buttons[0].type.data == b'fallback'


def test_richparser_preserves_nested_scalar_and_list_content():
    message = richparser.html_to_input_rich_message(
        '<blockquote><p>quote <code>a<i>b</i>c</code></p></blockquote>'
        '<details><summary><b>S</b></summary><p>body</p></details>'
        '<ul><li>outer<ul><li>inner</li></ul></li><li>tail</li></ul>'
        '<table compact><caption>A &amp; B "Q"</caption><tr><td align="right" '
        'valign="bottom" colspan="2" rowspan="3"><p>cell</p></td></tr></table>'
    )
    quote, details, outer_list, table = message.blocks

    assert quote.text.texts[1].text.text == 'abc'
    assert details.title.text == 'S'
    assert isinstance(outer_list.items[0], tl_types.PageListItemBlocks)
    assert isinstance(outer_list.items[0].blocks[0], tl_types.PageBlockParagraph)
    assert outer_list.items[0].blocks[0].text.text == 'outer'
    assert isinstance(outer_list.items[0].blocks[1], tl_types.PageBlockList)
    assert table.title.text == 'A & B "Q"'
    assert table.compact is True
    cell = table.rows[0].cells[0]
    assert cell.align_right and cell.valign_bottom and cell.colspan == 2 and cell.rowspan == 3
    rendered = richparser.rich_message_to_html(message)
    assert '<ul><li><p>outer</p><ul><li>inner</li></ul></li><li>tail</li></ul>' in rendered
    reparsed = richparser.html_to_input_rich_message(rendered)
    nested = reparsed.blocks[2].items[0]
    assert nested.blocks[0].text.text == 'outer'
    assert isinstance(nested.blocks[1], tl_types.PageBlockList)


def test_richparser_scalar_wrappers_alignment_and_received_text_depth():
    assert richparser._inline_plain([
        richparser.TextEmoji('1', 'emoji'), richparser.TextDateTime(1, text='time')
    ]) == 'emojitime'
    assert richparser.BlockButtonRow([], '" onfocus="bad').to_html() == '<tg-button-row></tg-button-row>'
    node = tl_types.TextPlain('end')
    for _ in range(500):
        node = tl_types.TextBold(node)
    rendered = richparser._render_text_node(node)
    assert 'end' not in rendered
    assert rendered.count('<b>') == 100


def test_richparser_preserves_inline_runs_around_nested_blocks():
    message = richparser.html_to_input_rich_message(
        '<details open><summary>Head</summary>before<p>inside</p>after</details>'
        '<ul><li>before<p>block</p>after</li></ul>'
    )
    details, block_list = message.blocks

    assert [block.text.text for block in details.blocks] == ['before', 'inside', 'after']
    item = block_list.items[0]
    assert [block.text.text for block in item.blocks] == ['before', 'block', 'after']
    rendered = richparser.rich_message_to_html(message)
    assert '<details open><summary>Head</summary><p>before</p><p>inside</p><p>after</p></details>' in rendered
    assert '<ul><li><p>before</p><p>block</p><p>after</p></li></ul>' in rendered
    reparsed = richparser.html_to_input_rich_message(rendered)
    assert [block.text.text for block in reparsed.blocks[0].blocks] == ['before', 'inside', 'after']
    assert [block.text.text for block in reparsed.blocks[1].items[0].blocks] == ['before', 'block', 'after']


def test_richparser_button_safety_callback_limits_and_chosen_chat():
    message = richparser.html_to_input_rich_message(
        '<tg-button-row><tg-button type="switch_inline_query_chosen_chat" query="q" '
        'allow-user-chats allow-bot-chats allow-group-chats allow-channel-chats '
        'onfocus="bad">Choose</tg-button></tg-button-row>'
    )
    button = message.blocks[0].buttons[0]
    assert {peer.__class__.__name__ for peer in button.type.peer_types} == {
        'InlineQueryPeerTypePM', 'InlineQueryPeerTypeBotPM',
        'InlineQueryPeerTypeChat', 'InlineQueryPeerTypeBroadcast',
    }
    rendered = richparser.rich_message_to_html(tl_types.RichMessage([message.blocks[0]], [], []))
    assert 'onfocus' not in rendered
    assert 'allow-user-chats' in rendered
    control = tl_types.PageButton(tl_types.TextPlain('C'), tl_types.InlineButtonTypeCallback(b'\x00'))
    assert 'data-base64="AA=="' in richparser.rich_message_to_html(
        tl_types.RichMessage([tl_types.PageBlockButtonRow([control])], [], [])
    )
    try:
        richparser.html_to_input_rich_message(
            '<tg-button-row><tg-button type="callback_data" data="{}">x</tg-button></tg-button-row>'.format('x' * 65)
        )
    except ValueError as error:
        assert '1 to 64 bytes' in str(error)
    else:
        assert False, 'oversized callback data must be rejected'


def test_richparser_safe_links_and_invalid_integer_attributes():
    rich_message = tl_types.RichMessage([
        tl_types.PageBlockParagraph(tl_types.TextUrl(tl_types.TextPlain('unsafe'), 'javascript:alert(1)', 0))
    ], [], [])
    assert richparser.rich_message_to_html(rich_message) == '<p>unsafe</p>'
    message = richparser.html_to_input_rich_message(
        '<table><tr><td colspan="999999999999">x</td></tr></table>'
        '<tg-emoji emoji-id="999999999999999999999">emoji</tg-emoji>'
    )
    assert message.blocks[0].rows[0].cells[0].colspan is None
    unsafe = richparser.html_to_input_rich_message(
        '<p><a href="javascript:alert(1)">js</a><a href="data:text/plain,x">data</a>'
        '<a href="vbscript:x">vb</a><a href="https://example.com">safe</a></p>'
    ).blocks[0].text
    assert ''.join(node.text for node in unsafe.texts[:-1]) == 'jsdatavb'
    assert isinstance(unsafe.texts[-1], tl_types.TextUrl)
    ordered = richparser.html_to_input_rich_message(
        '<ol start="999999999999"><li>item</li></ol>'
    ).blocks[0]
    assert ordered.start is None


def test_rich_message_to_text_preserves_block_list_item_order():
    rich_message = tl_types.RichMessage([
        tl_types.PageBlockList([
            tl_types.PageListItemBlocks([tl_types.PageBlockParagraph(tl_types.TextPlain('first'))]),
            tl_types.PageListItemText(tl_types.TextPlain('second')),
        ])
    ], [], [])

    assert richparser.rich_message_to_text(rich_message) == 'first\nsecond'


def test_richparser_rejects_and_disables_unsafe_button_urls():
    for button_type in ('url', 'web_app', 'login_url'):
        try:
            richparser.html_to_input_rich_message(
                '<tg-button-row><tg-button type="{}" url="javascript:alert(1)">Label</tg-button></tg-button-row>'.format(button_type)
            )
        except ValueError as error:
            assert 'safe scheme' in str(error)
        else:
            assert False, '{} must reject unsafe URLs'.format(button_type)

    unsafe_buttons = [
        tl_types.PageButton(tl_types.TextPlain('URL'), tl_types.InlineButtonTypeUrl('data:text/plain,x')),
        tl_types.PageButton(tl_types.TextPlain('App'), tl_types.InlineButtonTypeWebView('vbscript:x')),
        tl_types.PageButton(tl_types.TextPlain('Login'), tl_types.InlineButtonTypeUrlAuth('javascript:x', 1)),
    ]
    rendered = richparser.rich_message_to_html(
        tl_types.RichMessage([tl_types.PageBlockButtonRow(unsafe_buttons)], [], [])
    )
    assert rendered == (
        '<tg-button-row><tg-button type="disabled">URL</tg-button>'
        '<tg-button type="disabled">App</tg-button><tg-button type="disabled">Login</tg-button></tg-button-row>'
    )


def test_richparser_button_row_and_block_limits():
    buttons = ''.join('<tg-button type="disabled">x</tg-button>' for _ in range(8))
    assert len(richparser.html_to_input_rich_message('<tg-button-row>{}</tg-button-row>'.format(buttons)).blocks[0].buttons) == 8
    for amount in (0, 9):
        source = ''.join('<tg-button type="disabled">x</tg-button>' for _ in range(amount))
        try:
            richparser.html_to_input_rich_message('<tg-button-row>{}</tg-button-row>'.format(source))
        except ValueError as error:
            assert '1 to 8' in str(error)
        else:
            assert False, 'invalid button-row size must fail'
    hundred = ''.join('<p>x</p>' for _ in range(100))
    assert len(richparser.html_to_input_rich_message(hundred).blocks) == 100
    try:
        richparser.html_to_input_rich_message(hundred + '<p>x</p>')
    except ValueError as error:
        assert '100 blocks' in str(error)
    else:
        assert False, 'more than 100 blocks must fail'


def test_richparser_validates_nested_block_and_button_limits():
    eight = ''.join('<tg-button type="disabled">x</tg-button>' for _ in range(8))
    assert len(richparser.html_to_input_rich_message(
        '<details><summary>x</summary><tg-button-row>{}</tg-button-row></details>'.format(eight)
    ).blocks[0].blocks[0].buttons) == 8
    nine = ''.join('<tg-button type="disabled">x</tg-button>' for _ in range(9))
    for source in (
        '<details><summary>x</summary><tg-button-row>{}</tg-button-row></details>'.format(nine),
        '<ul><li><tg-button-row>{}</tg-button-row></li></ul>'.format(nine),
    ):
        try:
            richparser.html_to_input_rich_message(source)
        except ValueError as error:
            assert '1 to 8' in str(error)
        else:
            assert False, 'nested button-row size must fail'

    ninety_nine = ''.join('<p>x</p>' for _ in range(99))
    assert len(richparser.html_to_input_rich_message(
        '<details><summary>x</summary>{}</details>'.format(ninety_nine)
    ).blocks[0].blocks) == 99
    for source in (
        '<details><summary>x</summary>{}</details>'.format(''.join('<p>x</p>' for _ in range(100))),
        '<ul><li>{}</li></ul>'.format(''.join('<p>x</p>' for _ in range(100))),
    ):
        try:
            richparser.html_to_input_rich_message(source)
        except ValueError as error:
            assert '100 blocks' in str(error)
        else:
            assert False, 'nested block count must fail'
    prebuilt = tl_types.RichMessage([
        tl_types.PageBlockDetails(
            blocks=[tl_types.PageBlockParagraph(tl_types.TextPlain('x')) for _ in range(100)],
            title=tl_types.TextPlain('x'),
        )
    ], [], [])
    try:
        richparser.rich_message_to_html(prebuilt)
    except ValueError as error:
        assert '100 blocks' in str(error)
    else:
        assert False, 'prebuilt nested blocks must fail'
