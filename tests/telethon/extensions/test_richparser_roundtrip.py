"""Inline rich buttons ("pills") and RichMessage -> HTML -> parse -> HTML stability."""
import pytest

from telethon.extensions import richparser
from telethon.tl import types as tl

P = tl.TextPlain


def button(text, button_type, style=None):
    return tl.TextButton(text, button_type, style=style)


def message(*blocks):
    return tl.RichMessage(list(blocks), [], [])


def copy_button(value):
    emoji = tl.TextCustomEmoji(6021445064096486884, '💾')
    return button(emoji, tl.InlineButtonTypeCopy(value))


def test_inline_button_in_paragraph_becomes_text_button():
    parsed = richparser.html_to_input_rich_message(
        '<p>Mod <tg-button type="disabled">v1.3.0</tg-button> '
        '<tg-button type="disabled" style="success">external</tg-button></p>'
    )
    texts = parsed.blocks[0].text.texts
    assert isinstance(texts[1], tl.TextButton)
    assert isinstance(texts[1].type, tl.InlineButtonTypeDisabled)
    assert texts[1].style is None
    assert texts[3].style.bg_success is True
    bytes(parsed)  # must serialize


def test_inline_button_keeps_nested_formatting_and_click_types():
    parsed = richparser.html_to_input_rich_message(
        '<p><tg-button type="copy_text" text=".cmd"><b>copy</b></tg-button>'
        '<tg-button type="callback_data" data="a:1" style="danger">go</tg-button></p>'
    )
    copy, callback = parsed.blocks[0].text.texts
    assert isinstance(copy.text, tl.TextBold)
    assert copy.type.copy_text == '.cmd'
    assert callback.type.data == b'a:1' and callback.style.bg_danger is True


def test_badge_and_pill_aliases_are_disabled_inline_buttons():
    html = '<p><tg-badge style="danger">new</tg-badge> <tg-pill>x</tg-pill></p>'
    blocks = richparser.parse_rich_html(html)
    assert richparser.render_rich_html(blocks) == (
        '<p><tg-button type="disabled" style="danger">new</tg-button> '
        '<tg-button type="disabled">x</tg-button></p>'
    )


def test_nested_buttons_keep_text_but_not_the_inner_button():
    html = richparser.render_rich_html(richparser.parse_rich_html(
        '<p><tg-button type="url" url="https://a.b">'
        '<tg-button type="disabled">in</tg-button> out</tg-button></p>'
    ))
    assert html == '<p><tg-button type="url" url="https://a.b">in out</tg-button></p>'


def test_button_attributes_are_canonical():
    html = richparser.render_rich_html(richparser.parse_rich_html(
        '<tg-button-row><tg-button style="PRIMARY" copy-text="x" type="copy_text">c</tg-button>'
        '<tg-button type="callback_data" data-base64="YTox" requires-password>p</tg-button>'
        '<tg-button type="login_url" fwd-text="F" url="https://l" button-id="2">l</tg-button>'
        '</tg-button-row>'
    ))
    assert html == (
        '<tg-button-row>'
        '<tg-button type="copy_text" text="x" style="primary">c</tg-button>'
        '<tg-button type="callback_data" data="a:1" requires-password="true">p</tg-button>'
        '<tg-button type="login_url" url="https://l" button-id="2" forward-text="F">l</tg-button>'
        '</tg-button-row>'
    )


def test_pretty_printed_html_does_not_leak_layout_whitespace():
    html = richparser.render_rich_html(richparser.parse_rich_html(
        '<details open>\n  <summary>S</summary>\n  <ul>\n    <li>a</li>\n  </ul>\n'
        '  <table>\n<tr><td>1</td></tr>\n</table>\n</details>'
    ))
    assert html == (
        '<details open><summary>S</summary><ul><li>a</li></ul>'
        '<table><tr><td>1</td></tr></table></details>'
    )


def test_collapsed_blockquote_maps_to_expandable():
    html = richparser.rich_message_to_html(
        message(tl.PageBlockBlockquote(P('q'), tl.TextEmpty(), collapsed=True))
    )
    assert html == '<blockquote expandable="true">q</blockquote>'
    parsed = richparser.html_to_input_rich_message(html)
    assert parsed.blocks[0].collapsed is True

CASES = {
    'pasted_sample': message(
        tl.PageBlockPhoto(5878826560914132586, tl.PageCaption(tl.TextEmpty(), tl.TextEmpty()), spoiler=False),
        tl.PageBlockParagraph(tl.TextConcat([
            tl.TextCustomEmoji(6024065724291488135, '🧩'), P(' '),
            tl.TextBold(P('ComfyImageGen')), P(' '),
            button(P('v1.3.0'), tl.InlineButtonTypeDisabled()), P(' '),
            button(P('external'), tl.InlineButtonTypeDisabled(), tl.RichButtonStyle(bg_success=True)),
        ])),
        tl.PageBlockBlockquote(P('Image generation'), tl.TextEmpty(), collapsed=False),
        tl.PageBlockDetails([tl.PageBlockParagraph(tl.TextConcat([
            tl.TextFixed(P('.chelp')), P(' - help '), copy_button('.chelp'), P('\n'),
            tl.TextFixed(P('.comfy')), P(' '), tl.TextItalic(P('[prompt]')), P(' '), copy_button('.comfy'),
        ]))], P('Commands'), open=True),
    ),
    'button_kinds': message(tl.PageBlockParagraph(tl.TextConcat([
        button(P('a'), tl.InlineButtonTypeUrl('https://x.y/?a=1&b=2'), tl.RichButtonStyle(bg_primary=True)),
        button(tl.TextBold(P('b')), tl.InlineButtonTypeCallback(b'cb:1'), tl.RichButtonStyle(bg_danger=True)),
        button(P('c'), tl.InlineButtonTypeSwitchInline('q', same_peer=True), tl.RichButtonStyle(link=True)),
        button(P('d'), tl.InlineButtonTypeUserProfile(123)),
        button(P('e'), tl.InlineButtonTypeWebView('https://w.app')),
        button(P('<&>'), tl.InlineButtonTypeCopy('a"b<c>')),
        button(P('bytes'), tl.InlineButtonTypeCallback(b'\xff\x00', requires_password=True)),
        button(P('login'), tl.InlineButtonTypeUrlAuth(url='https://l.in', button_id=3, fwd_text='Fwd')),
        button(P('chosen'), tl.InlineButtonTypeSwitchInline(
            'q', peer_types=[tl.InlineQueryPeerTypePM(), tl.InlineQueryPeerTypeBroadcast()])),
        button(P('unsafe'), tl.InlineButtonTypeUrl('javascript:alert(1)')),
    ]))),
    'button_row': message(tl.PageBlockButtonRow(
        [tl.PageButton(P('Row'), tl.InlineButtonTypeCallback(b'row'), tl.RichButtonStyle(bg_danger=True))],
        align_right=True)),
    'media_and_captions': message(
        tl.PageBlockPhoto(1, tl.PageCaption(P('Cap'), P('credit')), spoiler=True),
        tl.PageBlockUnsupported()),
    'code': message(
        tl.PageBlockPreformatted(tl.TextBold(P('plain <x>')), ''),
        tl.PageBlockPreformatted(P('a<b'), 'python'),
        tl.PageBlockParagraph(tl.TextFixed(tl.TextBold(P('a'))))),
    'quotes_and_titles': message(
        tl.PageBlockBlockquoteBlocks(
            [tl.PageBlockParagraph(P('a')), tl.PageBlockParagraph(tl.TextBold(P('b')))], P('src')),
        tl.PageBlockDetails([tl.PageBlockParagraph(P('body'))], tl.TextBold(P('S'))),
        tl.PageBlockTable(tl.TextBold(P('Title')), [tl.PageTableRow([
            tl.PageTableCell(header=True, text=P('h'), align_center=True),
            tl.PageTableCell(text=tl.TextBold(P('c')), colspan=2, align_right=True)])], bordered=True)),
    'lists_dividers': message(
        tl.PageBlockOrderedList([tl.PageListOrderedItemText(P('one'), num='1')]),
        tl.PageBlockDivider(), tl.PageBlockAnchor('top'), tl.PageBlockHeading2(P('H')),
        tl.PageBlockFooter(P('f'))),
    'emoji_and_diff': message(tl.PageBlockParagraph(tl.TextConcat([
        tl.TextCustomEmoji(5, ''), tl.TextDiff(P('new'), P('old'))]))),
}


@pytest.mark.parametrize('name', sorted(CASES))
def test_rich_message_html_is_a_parser_fixpoint(name):
    html = richparser.rich_message_to_html(CASES[name])

    assert richparser.render_rich_html(richparser.parse_rich_html(html)) == html

    rebuilt = tl.RichMessage(richparser.html_to_tl_blocks(html), [], [])
    again = richparser.rich_message_to_html(rebuilt)
    assert again == html
    assert richparser.rich_message_to_html(
        tl.RichMessage(richparser.html_to_tl_blocks(again), [], [])
    ) == html


def test_rich_message_to_html_keeps_inline_buttons():
    html = richparser.rich_message_to_html(CASES['pasted_sample'])
    assert '<tg-button type="disabled">v1.3.0</tg-button>' in html
    assert '<tg-button type="disabled" style="success">external</tg-button>' in html
    assert '<tg-button type="copy_text" text=".chelp">' in html
