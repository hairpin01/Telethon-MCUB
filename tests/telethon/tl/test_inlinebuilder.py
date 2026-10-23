import pytest

from telethon.tl import types
from telethon.tl.custom import inlinebuilder as inlinebuilder_module
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


class _UrlUploadFakeClient(MockClient):
    """Pretends to upload: returns canned UploadMedia result."""

    def __init__(self, uploaded):
        self.uploaded = uploaded
        self.seen_name = None

    async def _file_to_media(self, file, **kwargs):
        self.seen_name = getattr(file, "name", None)
        assert file.read() == b"fake-bytes"
        return None, object(), True

    async def __call__(self, request):
        return self.uploaded


@pytest.mark.asyncio
async def test_upload_url_as_rich_file_downloads_and_attaches_photo(monkeypatch):
    monkeypatch.setattr(
        inlinebuilder_module, "_download_rich_media_url", lambda url: b"fake-bytes"
    )
    photo = types.Photo(
        id=7, access_hash=8, file_reference=b"fr", date=None, sizes=[], dc_id=2
    )
    client = _UrlUploadFakeClient(types.MessageMediaPhoto(photo=photo))
    builder = InlineBuilder(client)

    rich_file, resolved = await builder._upload_url_as_rich_file(
        "hero", "https://example.com/pic.jpg", "photo"
    )

    assert isinstance(rich_file, types.InputRichFilePhoto)
    assert rich_file.id == "hero"
    assert (rich_file.photo.id, rich_file.photo.access_hash) == (7, 8)
    assert resolved == "photo"
    assert client.seen_name == "pic.jpg"


@pytest.mark.asyncio
async def test_upload_url_as_rich_file_resolves_video_mime(monkeypatch):
    monkeypatch.setattr(
        inlinebuilder_module, "_download_rich_media_url", lambda url: b"fake-bytes"
    )
    document = types.Document(
        id=9,
        access_hash=10,
        file_reference=b"fr2",
        date=None,
        mime_type="video/mp4",
        size=123,
        dc_id=2,
        attributes=[],
    )
    client = _UrlUploadFakeClient(types.MessageMediaDocument(document=document))
    builder = InlineBuilder(client)

    rich_file, resolved = await builder._upload_url_as_rich_file(
        "clip", "https://example.com/v?a=b", "video"
    )

    assert isinstance(rich_file, types.InputRichFileDocument)
    assert rich_file.id == "clip"
    assert resolved == "video"
    # extensionless URL falls back to a synthetic file name
    assert client.seen_name == "rich-media-clip"


@pytest.mark.asyncio
async def test_upload_url_as_rich_file_rejects_empty_upload(monkeypatch):
    monkeypatch.setattr(
        inlinebuilder_module, "_download_rich_media_url", lambda url: b"fake-bytes"
    )
    builder = InlineBuilder(_UrlUploadFakeClient(types.MessageMediaEmpty()))

    with pytest.raises(ValueError, match="no usable"):
        await builder._upload_url_as_rich_file(
            "hero", "https://example.com/pic.jpg", "photo"
        )


def test_download_rich_media_url_rejects_oversize(monkeypatch):
    import urllib.request

    class _Resp:
        headers = {
            "Content-Length": str(
                inlinebuilder_module._RICH_MEDIA_MAX_DOWNLOAD_BYTES + 1
            )
        }

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, n=-1):
            raise AssertionError("body must not be read")

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: _Resp())

    with pytest.raises(ValueError, match="too large"):
        inlinebuilder_module._download_rich_media_url("https://example.com/big.bin")


def test_rich_media_url_filename():
    assert (
        inlinebuilder_module._rich_media_url_filename(
            "https://example.com/a/pic.jpg?x=1", "id1"
        )
        == "pic.jpg"
    )
    assert (
        inlinebuilder_module._rich_media_url_filename("https://example.com/v", "clip")
        == "rich-media-clip"
    )
