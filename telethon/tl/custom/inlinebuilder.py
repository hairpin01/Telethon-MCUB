import hashlib
import re

from .. import functions, types
from ... import utils
from ...extensions import richparser

_TYPE_TO_MIMES = {
    "gif": ["image/gif"],  # 'video/mp4' too, but that's used for video
    "article": ["text/html"],
    "audio": ["audio/mpeg"],
    "contact": [],
    "file": ["application/pdf", "application/zip"],  # actually any
    "geo": [],
    "photo": ["image/jpeg"],
    "sticker": ["image/webp", "application/x-tgsticker"],
    "venue": [],
    "video": ["video/mp4"],  # tdlib includes text/html for some reason
    "voice": ["audio/ogg"],
}

_RICH_MEDIA_REF_RE = re.compile(r'tg://(photo|document|video|audio|media)\?id=([^"\'<>\s&]+)')


class InlineBuilder:
    """
    Helper class to allow defining `InlineQuery
    <telethon.events.inlinequery.InlineQuery>` ``results``.

    Common arguments to all methods are
    explained here to avoid repetition:

        text (`str`, optional):
            If present, the user will send a text
            message with this text upon being clicked.

        link_preview (`bool`, optional):
            Whether to show a link preview in the sent
            text message or not.

        geo (:tl:`InputGeoPoint`, :tl:`GeoPoint`, :tl:`InputMediaVenue`, :tl:`MessageMediaVenue`, optional):
            If present, it may either be a geo point or a venue.

        period (int, optional):
            The period in seconds to be used for geo points.

        contact (:tl:`InputMediaContact`, :tl:`MessageMediaContact`, optional):
            If present, it must be the contact information to send.

        game (`bool`, optional):
            May be `True` to indicate that the game will be sent.

        buttons (`list`, `custom.Button <telethon.tl.custom.button.Button>`, :tl:`KeyboardButton`, optional):
            Same as ``buttons`` for `client.send_message()
            <telethon.client.messages.MessageMethods.send_message>`.

        parse_mode (`str`, optional):
            Same as ``parse_mode`` for `client.send_message()
            <telethon.client.messageparse.MessageParseMethods.parse_mode>`.

        id (`str`, optional):
            The string ID to use for this result. If not present, it
            will be the SHA256 hexadecimal digest of converting the
            created :tl:`InputBotInlineResult` with empty ID to ``bytes()``,
            so that the ID will be deterministic for the same input.

            .. note::

                If two inputs are exactly the same, their IDs will be the same
                too. If you send two articles with the same ID, it will raise
                ``ResultIdDuplicateError``. Consider giving them an explicit
                ID if you need to send two results that are the same.

    """

    def __init__(self, client):
        self._client = client

    # noinspection PyIncorrectDocstring
    async def article(
        self,
        title,
        description=None,
        *,
        url=None,
        thumb=None,
        content=None,
        id=None,
        text=None,
        parse_mode=(),
        rich_text=None,
        rich_parse_mode="html",
        rich_message=None,
        rich_rtl=None,
        rich_noautolink=None,
        rich_files=None,
        rich_media=None,
        link_preview=True,
        geo=None,
        period=60,
        contact=None,
        game=False,
        buttons=None,
    ):
        """
        Creates new inline result of article type.

        Args:
            title (`str`):
                The title to be shown for this result.

            description (`str`, optional):
                Further explanation of what this result means.

            url (`str`, optional):
                The URL to be shown for this result.

            thumb (:tl:`InputWebDocument`, optional):
                The thumbnail to be shown for this result.
                For now it has to be a :tl:`InputWebDocument` if present.

            content (:tl:`InputWebDocument`, optional):
                The content to be shown for this result.
                For now it has to be a :tl:`InputWebDocument` if present.

            rich_text (`str`, optional):
                HTML or Markdown source for a rich article message. Use this
                when the selected inline result should send an expanded rich
                message instead of a normal formatted text message.

            rich_parse_mode (`str`, optional):
                The format used by ``rich_text``. May be ``'html'`` (default),
                ``'markdown'`` or ``'md'``.

            rich_message (:tl:`InputRichMessage`, optional):
                Already-built rich message to send. Useful when you need full
                control over rich blocks and attached rich files.

            rich_rtl (`bool`, optional):
                Whether Telegram should render the rich message right-to-left.

            rich_noautolink (`bool`, optional):
                Whether Telegram should avoid automatic link detection in the
                rich message.

            rich_files (`list`, optional):
                Optional :tl:`InputRichFile` items referenced by ``rich_text``.
                The ``id`` in links such as ``tg://photo?id=hero`` must match
                the string ``id`` of a corresponding
                :tl:`InputRichFilePhoto` or :tl:`InputRichFileDocument` item;
                it is not a list index.

            rich_media (`dict` | `list`, optional):
                Convenience mapping/list converted into ``rich_files``. Keys
                are ids used by links such as ``tg://media?id=hero``. HTTP(S)
                URLs are uploaded via Telegram and ``tg://media`` is rewritten
                to ``tg://photo``, ``tg://video``, ``tg://audio`` or
                ``tg://document`` based on the media type.

        Example:
            .. code-block:: python

                results = [
                    # Option with title and description sending a message.
                    builder.article(
                        title='First option',
                        description='This is the first option',
                        text='Text sent after clicking this option',
                    ),
                    # Option with title URL to be opened when clicked.
                    builder.article(
                        title='Second option',
                        url='https://example.com',
                        text='Text sent if the user clicks the option and not the URL',
                    ),
                    # Sending a message with buttons.
                    # You can use a list or a list of lists to include more buttons.
                    builder.article(
                        title='Third option',
                        text='Text sent with buttons below',
                        buttons=Button.url('https://example.com'),
                    ),
                    # Sending an HTML rich message.
                    builder.article(
                        title='Rich option',
                        rich_text='<h1>Title</h1><p><b>Rich</b> body</p>',
                    ),
                    # Rich message with an attached rich file.
                    builder.rich_article(
                        title='Rich photo',
                        rich_text='<a href="tg://photo?id=hero">Photo</a>',
                        rich_files=[types.InputRichFilePhoto('hero', input_photo)],
                    ),
                ]
        """
        # TODO Does 'article' work always?
        # article, photo, gif, mpeg4_gif, video, audio,
        # voice, document, location, venue, contact, game
        rich_text, rich_files = await self._normalize_rich_media_for_message(
            rich_media=rich_media,
            rich_files=rich_files,
            rich_text=rich_text,
        )

        result = types.InputBotInlineResult(
            id=id or "",
            type="article",
            send_message=await self._message(
                text=text,
                parse_mode=parse_mode,
                rich_text=rich_text,
                rich_parse_mode=rich_parse_mode,
                rich_message=rich_message,
                rich_rtl=rich_rtl,
                rich_noautolink=rich_noautolink,
                rich_files=rich_files,
                link_preview=link_preview,
                geo=geo,
                period=period,
                contact=contact,
                game=game,
                buttons=buttons,
            ),
            title=title,
            description=description,
            url=url,
            thumb=thumb,
            content=content,
        )
        if id is None:
            result.id = hashlib.sha256(bytes(result)).hexdigest()

        return result

    async def rich_article(
        self,
        title,
        rich_text=None,
        *,
        rich_parse_mode="html",
        rich_message=None,
        description=None,
        url=None,
        thumb=None,
        content=None,
        id=None,
        buttons=None,
        rich_rtl=None,
        rich_noautolink=None,
        rich_files=None,
        rich_media=None,
    ):
        """
        Creates an article result that sends a Telegram rich message.

        This is a convenience wrapper over `article` for inline results backed
        by :tl:`InputBotInlineMessageRichMessage`.
        """

        return await self.article(
            title,
            description=description,
            url=url,
            thumb=thumb,
            content=content,
            id=id,
            rich_text=rich_text,
            rich_parse_mode=rich_parse_mode,
            rich_message=rich_message,
            rich_rtl=rich_rtl,
            rich_noautolink=rich_noautolink,
            rich_files=rich_files,
            rich_media=rich_media,
            buttons=buttons,
        )

    async def _normalize_rich_media_for_message(self, rich_media=None, rich_files=None, rich_text=None):
        result = []
        has_rich_files = rich_files is not None
        refs = self._extract_rich_media_refs(rich_text)
        if rich_files:
            result.extend(rich_files if isinstance(rich_files, (list, tuple)) else [rich_files])
        if rich_media:
            for spec in self._iter_rich_media_specs(rich_media):
                media_id = str(spec.get("id"))
                rich_file, resolved_type = await self._make_input_rich_file(
                    spec, refs.get(media_id)
                )
                result.append(rich_file)
                if refs.get(media_id) == "media":
                    rich_text = self._replace_media_ref_type(rich_text, media_id, resolved_type)
        return rich_text, result if result or has_rich_files else None

    @staticmethod
    def _extract_rich_media_refs(rich_text):
        if not rich_text:
            return {}
        refs = {}
        for media_type, media_id in _RICH_MEDIA_REF_RE.findall(rich_text):
            refs.setdefault(media_id, media_type)
        return refs

    @staticmethod
    def _replace_media_ref_type(rich_text, media_id, media_type):
        if not rich_text or media_type == "media":
            return rich_text
        return re.sub(
            rf"tg://media\?id={re.escape(media_id)}(?=\b|[\"'<>\s&])",
            f"tg://{media_type}?id={media_id}",
            rich_text,
        )

    @staticmethod
    def _iter_rich_media_specs(rich_media):
        if isinstance(rich_media, dict):
            if "id" in rich_media:
                yield rich_media
            else:
                for media_id, media in rich_media.items():
                    yield {"id": media_id, "media": media}
            return
        if isinstance(rich_media, (list, tuple)) and not isinstance(rich_media, (str, bytes, bytearray)):
            for item in rich_media:
                if isinstance(item, dict):
                    yield item
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    yield {"id": item[0], "media": item[1]}
                else:
                    raise TypeError("rich_media items must be dicts or (id, media) pairs")
            return
        raise TypeError("rich_media must be a mapping, a spec dict, or a list of specs")

    @staticmethod
    def _infer_url_rich_media_type(url, media_type=None):
        if media_type and media_type != "media":
            return "document" if media_type in {"doc", "file"} else media_type
        clean = str(url).split("?", 1)[0].split("#", 1)[0].lower()
        if clean.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
            return "photo"
        if clean.endswith((".mp4", ".mov", ".m4v", ".webm", ".mkv")):
            return "video"
        if clean.endswith((".mp3", ".ogg", ".oga", ".m4a", ".wav", ".flac")):
            return "audio"
        return "document"

    async def _make_input_rich_file(self, spec, referenced_type=None):
        media_id = str(spec.get("id") or "")
        if not media_id:
            raise ValueError("rich_media spec requires a non-empty 'id'")
        media = spec.get("media", spec.get("file"))
        media_type = spec.get("type") or referenced_type
        if spec.get("photo") is not None:
            media = spec["photo"]
            media_type = media_type or "photo"
        if spec.get("document") is not None:
            media = spec["document"]
            media_type = media_type or "document"
        if media is None:
            raise ValueError("rich_media spec requires 'media', 'photo' or 'document'")

        if isinstance(media, str) and re.match(r"https?://", media):
            resolved_type = self._infer_url_rich_media_type(media, media_type)
            rich_file = await self._upload_url_as_rich_file(media_id, media, resolved_type)
            return rich_file, resolved_type

        if media_type in {None, "photo"}:
            try:
                return types.InputRichFilePhoto(media_id, utils.get_input_photo(media)), "photo"
            except TypeError as e:
                if media_type == "photo":
                    raise ValueError(
                        f"rich_media id {media_id!r} is referenced as photo but the value is not a photo"
                    ) from e
        if media_type in {None, "document", "doc", "file", "audio", "video"}:
            try:
                resolved = media_type if media_type in {"audio", "video"} else "document"
                return types.InputRichFileDocument(media_id, utils.get_input_document(media)), resolved
            except TypeError as e:
                if media_type is not None:
                    raise ValueError(
                        f"rich_media id {media_id!r} is referenced as {media_type} but the value is not a document"
                    ) from e
        raise TypeError("rich_media value must be a Telegram photo/document/media object or an HTTP(S) URL")

    async def _upload_url_as_rich_file(self, media_id, url, media_type):
        _file_handle, media, _as_image = await self._client._file_to_media(
            url,
            force_document=media_type != "photo",
            supports_streaming=media_type == "video",
        )
        uploaded = await self._client(
            functions.messages.UploadMediaRequest(types.InputPeerSelf(), media)
        )
        if media_type == "photo":
            return types.InputRichFilePhoto(media_id, utils.get_input_photo(uploaded.photo))
        return types.InputRichFileDocument(media_id, utils.get_input_document(uploaded.document))

    # noinspection PyIncorrectDocstring
    async def photo(
        self,
        file,
        *,
        id=None,
        include_media=True,
        text=None,
        parse_mode=(),
        link_preview=True,
        geo=None,
        period=60,
        contact=None,
        game=False,
        buttons=None,
    ):
        """
        Creates a new inline result of photo type.

        Args:
            include_media (`bool`, optional):
                Whether the photo file used to display the result should be
                included in the message itself or not. By default, the photo
                is included, and the text parameter alters the caption.

            file (`obj`, optional):
                Same as ``file`` for `client.send_file()
                <telethon.client.uploads.UploadMethods.send_file>`.

        Example:
            .. code-block:: python

                results = [
                    # Sending just the photo when the user selects it.
                    builder.photo('/path/to/photo.jpg'),

                    # Including a caption with some in-memory photo.
                    photo_bytesio = ...
                    builder.photo(
                        photo_bytesio,
                        text='This will be the caption of the sent photo',
                    ),

                    # Sending just the message without including the photo.
                    builder.photo(
                        photo,
                        text='This will be a normal text message',
                        include_media=False,
                    ),
                ]
        """
        try:
            fh = utils.get_input_photo(file)
        except TypeError:
            _, media, _ = await self._client._file_to_media(file, allow_cache=True, as_image=True)
            if isinstance(media, types.InputPhoto):
                fh = media
            else:
                r = await self._client(
                    functions.messages.UploadMediaRequest(types.InputPeerSelf(), media=media)
                )
                fh = utils.get_input_photo(r.photo)

        result = types.InputBotInlineResultPhoto(
            id=id or "",
            type="photo",
            photo=fh,
            send_message=await self._message(
                text=text or "",
                parse_mode=parse_mode,
                link_preview=link_preview,
                media=include_media,
                geo=geo,
                period=period,
                contact=contact,
                game=game,
                buttons=buttons,
            ),
        )
        if id is None:
            result.id = hashlib.sha256(bytes(result)).hexdigest()

        return result

    # noinspection PyIncorrectDocstring
    async def document(
        self,
        file,
        title=None,
        *,
        description=None,
        type=None,
        mime_type=None,
        attributes=None,
        force_document=False,
        voice_note=False,
        video_note=False,
        use_cache=True,
        id=None,
        text=None,
        parse_mode=(),
        link_preview=True,
        geo=None,
        period=60,
        contact=None,
        game=False,
        buttons=None,
        include_media=True,
    ):
        """
        Creates a new inline result of document type.

        `use_cache`, `mime_type`, `attributes`, `force_document`,
        `voice_note` and `video_note` are described in `client.send_file
        <telethon.client.uploads.UploadMethods.send_file>`.

        Args:
            file (`obj`):
                Same as ``file`` for `client.send_file()
                <telethon.client.uploads.UploadMethods.send_file>`.

            title (`str`, optional):
                The title to be shown for this result.

            description (`str`, optional):
                Further explanation of what this result means.

            type (`str`, optional):
                The type of the document. May be one of: article, audio,
                contact, file, geo, gif, photo, sticker, venue, video, voice.
                It will be automatically set if ``mime_type`` is specified,
                and default to ``'file'`` if no matching mime type is found.
                you may need to pass ``attributes`` in order to use ``type``
                effectively.

            attributes (`list`, optional):
                Optional attributes that override the inferred ones, like
                :tl:`DocumentAttributeFilename` and so on.

            include_media (`bool`, optional):
                Whether the document file used to display the result should be
                included in the message itself or not. By default, the document
                is included, and the text parameter alters the caption.

        Example:
            .. code-block:: python

                results = [
                    # Sending just the file when the user selects it.
                    builder.document('/path/to/file.pdf'),

                    # Including a caption with some in-memory file.
                    file_bytesio = ...
                    builder.document(
                        file_bytesio,
                        text='This will be the caption of the sent file',
                    ),

                    # Sending just the message without including the file.
                    builder.document(
                        photo,
                        text='This will be a normal text message',
                        include_media=False,
                    ),
                ]
        """
        if type is None:
            if voice_note:
                type = "voice"
            elif mime_type:
                for ty, mimes in _TYPE_TO_MIMES.items():
                    for mime in mimes:
                        if mime_type == mime:
                            type = ty
                            break

            if type is None:
                type = "file"

        try:
            fh = utils.get_input_document(file)
        except TypeError:
            _, media, _ = await self._client._file_to_media(
                file,
                mime_type=mime_type,
                attributes=attributes,
                force_document=force_document,
                voice_note=voice_note,
                video_note=video_note,
                allow_cache=use_cache,
            )
            if isinstance(media, types.InputDocument):
                fh = media
            else:
                r = await self._client(
                    functions.messages.UploadMediaRequest(types.InputPeerSelf(), media=media)
                )
                fh = utils.get_input_document(r.document)

        result = types.InputBotInlineResultDocument(
            id=id or "",
            type=type,
            document=fh,
            send_message=await self._message(
                # Empty string for text if there's media but text is None.
                # We may want to display a document but send text; however
                # default to sending the media (without text, i.e. stickers).
                text=text or "",
                parse_mode=parse_mode,
                link_preview=link_preview,
                media=include_media,
                geo=geo,
                period=period,
                contact=contact,
                game=game,
                buttons=buttons,
            ),
            title=title,
            description=description,
        )
        if id is None:
            result.id = hashlib.sha256(bytes(result)).hexdigest()

        return result

    # noinspection PyIncorrectDocstring
    async def game(
        self,
        short_name,
        *,
        id=None,
        text=None,
        parse_mode=(),
        link_preview=True,
        geo=None,
        period=60,
        contact=None,
        game=False,
        buttons=None,
    ):
        """
        Creates a new inline result of game type.

        Args:
            short_name (`str`):
                The short name of the game to use.
        """
        result = types.InputBotInlineResultGame(
            id=id or "",
            short_name=short_name,
            send_message=await self._message(
                text=text,
                parse_mode=parse_mode,
                link_preview=link_preview,
                geo=geo,
                period=period,
                contact=contact,
                game=game,
                buttons=buttons,
            ),
        )
        if id is None:
            result.id = hashlib.sha256(bytes(result)).hexdigest()

        return result

    async def _message(
        self,
        *,
        text=None,
        parse_mode=(),
        rich_text=None,
        rich_parse_mode="html",
        rich_message=None,
        rich_rtl=None,
        rich_noautolink=None,
        rich_files=None,
        link_preview=True,
        media=False,
        geo=None,
        period=60,
        contact=None,
        game=False,
        buttons=None,
    ):
        # Empty strings are valid but false-y; if they're empty use dummy '\0'
        rich = rich_message if rich_message is not None else rich_text
        args = (
            "\0" if text == "" else text,
            geo,
            contact,
            game,
            "\0" if rich == "" else rich,
        )
        if sum(1 for x in args if x is not None and x is not False) != 1:
            raise ValueError(
                "Must set exactly one of text, geo, contact, game or rich_text (set {})".format(
                    ", ".join(
                        x[0]
                        for x in zip("text geo contact game rich_text".split(), args)
                        if x[1]
                    )
                    or "none"
                )
            )

        markup = self._client.build_reply_markup(buttons)
        if rich is not None:
            return types.InputBotInlineMessageRichMessage(
                rich_message=self._rich_message(
                    rich_text=rich_text,
                    rich_parse_mode=rich_parse_mode,
                    rich_message=rich_message,
                    rich_rtl=rich_rtl,
                    rich_noautolink=rich_noautolink,
                    rich_files=rich_files,
                ),
                reply_markup=markup,
            )
        elif text is not None:
            text, msg_entities = await self._client._parse_message_text(text, parse_mode)
            if media:
                # "MediaAuto" means it will use whatever media the inline
                # result itself has (stickers, photos, or documents), while
                # respecting the user's text (caption) and formatting.
                return types.InputBotInlineMessageMediaAuto(
                    message=text, entities=msg_entities, reply_markup=markup
                )
            else:
                return types.InputBotInlineMessageText(
                    message=text,
                    no_webpage=not link_preview,
                    entities=msg_entities,
                    reply_markup=markup,
                )
        elif isinstance(geo, (types.InputGeoPoint, types.GeoPoint)):
            return types.InputBotInlineMessageMediaGeo(
                geo_point=utils.get_input_geo(geo), period=period, reply_markup=markup
            )
        elif isinstance(geo, (types.InputMediaVenue, types.MessageMediaVenue)):
            if isinstance(geo, types.InputMediaVenue):
                geo_point = geo.geo_point
            else:
                geo_point = geo.geo

            return types.InputBotInlineMessageMediaVenue(
                geo_point=geo_point,
                title=geo.title,
                address=geo.address,
                provider=geo.provider,
                venue_id=geo.venue_id,
                venue_type=geo.venue_type,
                reply_markup=markup,
            )
        elif isinstance(contact, (types.InputMediaContact, types.MessageMediaContact)):
            return types.InputBotInlineMessageMediaContact(
                phone_number=contact.phone_number,
                first_name=contact.first_name,
                last_name=contact.last_name,
                vcard=contact.vcard,
                reply_markup=markup,
            )
        elif game:
            return types.InputBotInlineMessageGame(reply_markup=markup)
        else:
            raise ValueError("No text, rich_text, game or valid geo or contact given")

    @staticmethod
    def _rich_message(
        *,
        rich_text=None,
        rich_parse_mode="html",
        rich_message=None,
        rich_rtl=None,
        rich_noautolink=None,
        rich_files=None,
    ):
        if rich_message is not None:
            if rich_text is not None:
                raise ValueError("Cannot set both rich_text and rich_message")
            return rich_message

        if rich_text is None:
            raise ValueError("No rich_text or rich_message given")

        mode = rich_parse_mode.lower() if isinstance(rich_parse_mode, str) else rich_parse_mode
        if mode in ("html", "htm"):
            if rich_files is None:
                return richparser.html_to_input_rich_message(
                    rich_text,
                    rtl=rich_rtl,
                    noautolink=rich_noautolink,
                )
            return types.InputRichMessageHTML(
                rich_text,
                rtl=rich_rtl,
                noautolink=rich_noautolink,
                files=rich_files,
            )
        elif mode in ("markdown", "md"):
            return types.InputRichMessageMarkdown(
                rich_text,
                rtl=rich_rtl,
                noautolink=rich_noautolink,
                files=rich_files,
            )

        raise ValueError("rich_parse_mode must be 'html', 'markdown' or 'md'")
