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

    assert msg.html_text == "<b>Hello &lt;rich&gt;</b>"
    assert msg.raw_text == "Hello <rich>"
    assert msg.text == "Hello <rich>"
