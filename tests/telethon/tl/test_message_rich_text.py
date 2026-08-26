from telethon.tl import types
from telethon.tl.custom.message import Message


def test_message_text_properties_fallback_to_rich_message():
    msg = Message(
        id=1,
        peer_id=types.PeerUser(123),
        message="",
        rich_message=types.RichMessage(
            blocks=[types.PageBlockParagraph(types.TextBold(types.TextPlain("Hello <rich>")))],
            photos=[],
            documents=[],
        ),
    )

    assert msg.html_text == "<p><b>Hello &lt;rich&gt;</b></p>"
    assert msg.raw_text == "Hello <rich>"
    assert msg.text == "Hello <rich>"


def test_message_rich_plain_text_does_not_leak_rich_html_tags():
    msg = Message(
        id=1,
        peer_id=types.PeerUser(123),
        message="",
        rich_message=types.RichMessage(
            blocks=[
                types.PageBlockMath('x^2'),
                types.PageBlockList([types.PageListItemText(types.TextPlain('item'))]),
                types.PageBlockButtonRow([
                    types.PageButton(types.TextPlain('Button'), types.InlineButtonTypeDisabled())
                ]),
            ], photos=[], documents=[],
        ),
    )

    assert msg.raw_text == 'x^2\nitem\nButton'
    assert msg.text == 'x^2\nitem\nButton'


def test_message_rich_plain_text_includes_captions_and_containers():
    caption = types.PageCaption(types.TextPlain('Caption'), types.TextPlain('Credit'))
    msg = Message(
        id=1,
        peer_id=types.PeerUser(123),
        message="",
        rich_message=types.RichMessage(
            blocks=[
                types.PageBlockPhoto(1, caption),
                types.PageBlockCover(types.PageBlockParagraph(types.TextPlain('Cover'))),
                types.PageBlockCollage([types.PageBlockParagraph(types.TextPlain('Collage'))], caption),
                types.PageBlockSlideshow([types.PageBlockParagraph(types.TextPlain('Slide'))], caption),
            ], photos=[], documents=[],
        ),
    )

    assert msg.raw_text == 'Caption\nCredit\nCover\nCaption\nCredit\nCollage\nCaption\nCredit\nSlide'
