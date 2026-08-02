import pytest

from telethon.tl import types
from telethon.tl.custom.inlinebuilder import InlineBuilder


class MockClient:
    def build_reply_markup(self, buttons):
        return None

    async def _parse_message_text(self, text, parse_mode):
        return text, []


@pytest.mark.asyncio
async def test_article_can_send_html_rich_text():
    result = await InlineBuilder(MockClient()).article(
        "Rich article",
        rich_text="<h1>Title</h1><p><b>Body</b></p>",
        rich_rtl=True,
        rich_noautolink=True,
    )

    assert isinstance(result.send_message, types.InputBotInlineMessageRichMessage)
    assert isinstance(result.send_message.rich_message, types.InputRichMessage)
    assert isinstance(result.send_message.rich_message.blocks[0], types.PageBlockHeading1)
    assert isinstance(result.send_message.rich_message.blocks[1], types.PageBlockParagraph)
    assert result.send_message.rich_message.rtl is True
    assert result.send_message.rich_message.noautolink is True


@pytest.mark.asyncio
async def test_article_can_send_markdown_rich_text():
    result = await InlineBuilder(MockClient()).article(
        "Rich article",
        rich_text="# Title\n\n**Body**",
        rich_parse_mode="md",
    )

    assert isinstance(result.send_message.rich_message, types.InputRichMessageMarkdown)
    assert result.send_message.rich_message.markdown == "# Title\n\n**Body**"


@pytest.mark.asyncio
async def test_article_can_send_prebuilt_rich_message():
    rich_message = types.InputRichMessageHTML("<p>Body</p>")

    result = await InlineBuilder(MockClient()).article(
        "Rich article",
        rich_message=rich_message,
    )

    assert result.send_message.rich_message is rich_message


@pytest.mark.asyncio
async def test_article_rich_text_is_mutually_exclusive_with_text():
    with pytest.raises(ValueError, match="exactly one"):
        await InlineBuilder(MockClient()).article(
            "Rich article",
            text="plain",
            rich_text="<p>Body</p>",
        )


def test_rich_message_rejects_unknown_parse_mode():
    with pytest.raises(ValueError, match="rich_parse_mode"):
        InlineBuilder._rich_message(rich_text="body", rich_parse_mode="rst")


@pytest.mark.asyncio
async def test_rich_article_wraps_article_rich_message():
    result = await InlineBuilder(MockClient()).rich_article(
        "Rich article",
        "<h1>Title</h1>",
    )

    assert isinstance(result.send_message, types.InputBotInlineMessageRichMessage)
    assert isinstance(result.send_message.rich_message, types.InputRichMessage)
    assert isinstance(result.send_message.rich_message.blocks[0], types.PageBlockHeading1)


@pytest.mark.asyncio
async def test_article_rich_media_mapping_builds_rich_files():
    photo = types.InputPhoto(1, 2, b"ref")

    result = await InlineBuilder(MockClient()).rich_article(
        "Rich article",
        '<a href="tg://photo?id=hero">Photo</a>',
        rich_media={"hero": photo},
    )

    rich_message = result.send_message.rich_message
    assert isinstance(rich_message.files[0], types.InputRichFilePhoto)
    assert rich_message.files[0].id == "hero"
    assert rich_message.files[0].photo is photo


def test_rich_media_alias_rewrite():
    assert InlineBuilder._replace_media_ref_type(
        '<a href="tg://media?id=hero">Media</a>', "hero", "video"
    ) == '<a href="tg://video?id=hero">Media</a>'
