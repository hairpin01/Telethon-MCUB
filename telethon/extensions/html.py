"""
Simple HTML -> Telegram entity parser.
"""

import functools
import re
from collections import deque
from html import escape
from html.parser import HTMLParser
from typing import Iterable, Tuple, List

from ..helpers import add_surrogate, del_surrogate, within_surrogate, strip_text
from ..tl import TLObject
from ..tl.types import (
    MessageEntityBold,
    MessageEntityItalic,
    MessageEntityCode,
    MessageEntityPre,
    MessageEntityEmail,
    MessageEntityUrl,
    MessageEntityTextUrl,
    MessageEntityMentionName,
    MessageEntityUnderline,
    MessageEntityStrike,
    MessageEntityBlockquote,
    MessageEntityCustomEmoji,
    MessageEntitySpoiler,
    TypeMessageEntity,
)

_TAG_TO_ENTITY = {
    "strong": MessageEntityBold,
    "b": MessageEntityBold,
    "em": MessageEntityItalic,
    "i": MessageEntityItalic,
    "u": MessageEntityUnderline,
    "del": MessageEntityStrike,
    "s": MessageEntityStrike,
    "blockquote": MessageEntityBlockquote,
    "code": MessageEntityCode,
    "pre": MessageEntityPre,
    "tg-emoji": MessageEntityCustomEmoji,
    "tg-spoiler": MessageEntitySpoiler,
}

_MAILTO_LEN = len("mailto:")
_LITERAL_TAG = object()
_SUPPORTED_TAGS = frozenset(_TAG_TO_ENTITY) | {"a", "emoji"}
_VALID_TAG_NAME_RE = re.compile(r"^[A-Za-z][-.A-Za-z0-9:_]*$")
_ANGLE_TAG_RE = re.compile(r"<\s*/?\s*([^\s<>/]+)(?:\s[^<>]*?)?\s*/?\s*>")


def _escape_invalid_tag_syntax(text: str) -> str:
    def replacer(match):
        tag_name = match.group(1)
        if _VALID_TAG_NAME_RE.match(tag_name):
            return match.group(0)
        return escape(match.group(0), quote=False)

    return _ANGLE_TAG_RE.sub(replacer, text)


class HTMLToTelegramParser(HTMLParser):
    __slots__ = ("text", "entities", "_building_entities", "_open_tags", "_open_tags_meta")

    def __init__(self):
        super().__init__()
        self.text = ""
        self.entities = []
        self._building_entities = {}
        self._open_tags = deque()
        self._open_tags_meta = deque()

    @staticmethod
    def _parse_tg_mention(url):
        prefix = "tg://user?id="
        if not url.startswith(prefix):
            return None

        user_id = url[len(prefix) :]
        try:
            return int(user_id)
        except ValueError:
            return None

    def _append_text(self, text):
        if not text:
            return

        for state in self._building_entities.values():
            state["entity"].length += len(text)

        self.text += text

    def _mark_literal_starttag(self, tag):
        self._open_tags_meta.popleft()
        self._open_tags_meta.appendleft(_LITERAL_TAG)
        self._append_text(self.get_starttag_text() or f"<{tag}>")

    def handle_starttag(self, tag, attrs):
        self._open_tags.appendleft(tag)
        self._open_tags_meta.appendleft(None)

        if tag not in _SUPPORTED_TAGS:
            self._mark_literal_starttag(tag)
            return

        attrs_dict = dict(attrs)
        EntityType = _TAG_TO_ENTITY.get(tag)
        args = {}

        has_expandable = any(k == "expandable" for k, v in attrs)

        if tag == "pre":
            args["language"] = ""
        elif tag == "a":
            url = attrs_dict.get("href")
            if url is None:
                self._mark_literal_starttag(tag)
                return
            if url.startswith("mailto:"):
                url = url[_MAILTO_LEN:]
                EntityType = MessageEntityEmail
            else:
                mention_user_id = self._parse_tg_mention(url)
                if mention_user_id is not None:
                    EntityType = MessageEntityMentionName
                    args["user_id"] = mention_user_id
                    url = None
                else:
                    # Start with TextUrl and decide if it can be converted to
                    # Url when closing the anchor (if visible text equals href).
                    EntityType = MessageEntityTextUrl
                    args["url"] = del_surrogate(url)
            self._open_tags_meta.popleft()
            self._open_tags_meta.appendleft(url)
        elif tag == "tg-emoji":
            emoji_id = attrs_dict.get("emoji-id")
            if emoji_id is None:
                self._mark_literal_starttag(tag)
                return
            try:
                args["document_id"] = int(emoji_id)
            except ValueError:
                self._mark_literal_starttag(tag)
                return
        elif tag == "emoji":
            document_id = attrs_dict.get("document_id")
            if document_id is None:
                self._mark_literal_starttag(tag)
                return
            try:
                args["document_id"] = int(document_id)
            except ValueError:
                self._mark_literal_starttag(tag)
                return
            EntityType = MessageEntityCustomEmoji
        elif tag == "blockquote":
            if has_expandable:
                expandable_value = attrs_dict.get("expandable")
                if expandable_value is None:
                    normalized_expandable = ""
                else:
                    normalized_expandable = str(expandable_value).strip().lower()

                if normalized_expandable in ("", "true", "1", "yes", "on"):
                    # MTProto uses `collapsed=True` to represent expandable blockquotes.
                    args["collapsed"] = True
                else:
                    # False-like values should behave like a regular blockquote.
                    args["collapsed"] = None
            else:
                args["collapsed"] = None
        elif tag == "code" and "pre" in self._building_entities:
            pre = self._building_entities["pre"]["entity"]
            cls = attrs_dict.get("class", "")
            if cls.startswith("language-"):
                pre.language = cls[9:]
            EntityType = None

        if EntityType:
            state = self._building_entities.get(tag)
            if state:
                state["depth"] += 1
            else:
                self._building_entities[tag] = {
                    "entity": EntityType(offset=len(self.text), length=0, **args),
                    "depth": 1,
                }

    def handle_data(self, text):
        self._append_text(text)

    def handle_endtag(self, tag):
        keep_literal = False
        matched_open_tag = False

        if self._open_tags and self._open_tags[0] == tag:
            matched_open_tag = True
            self._open_tags.popleft()
            keep_literal = self._open_tags_meta.popleft() is _LITERAL_TAG
        elif tag in self._open_tags:
            matched_open_tag = True
            idx = None
            for i, t in enumerate(self._open_tags):
                if t == tag:
                    idx = i
                    break
            if idx is not None:
                keep_literal = self._open_tags_meta[idx] is _LITERAL_TAG
                del self._open_tags[idx]
                del self._open_tags_meta[idx]

        if keep_literal:
            self._append_text(f"</{tag}>")
        elif not matched_open_tag and tag not in _SUPPORTED_TAGS:
            # Preserve unmatched unknown closing tags as plain text.
            self._append_text(f"</{tag}>")

        state = self._building_entities.get(tag)
        if not state:
            return

        state["depth"] -= 1
        if state["depth"] > 0:
            return

        entity = self._building_entities.pop(tag)["entity"]

        if isinstance(entity, MessageEntityTextUrl):
            raw = del_surrogate(self.text[entity.offset : entity.offset + entity.length])
            if raw == entity.url:
                entity = MessageEntityUrl(offset=entity.offset, length=entity.length)

        self.entities.append(entity)


def parse(html: str) -> Tuple[str, List[TypeMessageEntity]]:
    """
    Parses the given HTML message and returns its stripped representation
    plus a list of the MessageEntity's that were found.

    :param html: the message with HTML to be parsed.
    :return: a tuple consisting of (clean message, [message entities]).
    """
    if not html:
        return html, []

    html = _escape_invalid_tag_syntax(html)
    parser = HTMLToTelegramParser()
    parser.feed(add_surrogate(html))
    text = strip_text(parser.text, parser.entities)
    parser.entities.reverse()
    parser.entities.sort(key=lambda entity: entity.offset)
    return del_surrogate(text), parser.entities


def _make_blockquote_formatter():
    def formatter(e, _text):
        if e.collapsed:
            return "<blockquote expandable>", "</blockquote>"
        return "<blockquote>", "</blockquote>"

    return formatter


_blockquote_formatter = _make_blockquote_formatter()

ENTITY_TO_FORMATTER = {
    MessageEntityBold: ("<strong>", "</strong>"),
    MessageEntityItalic: ("<em>", "</em>"),
    MessageEntityCode: ("<code>", "</code>"),
    MessageEntityUnderline: ("<u>", "</u>"),
    MessageEntityStrike: ("<del>", "</del>"),
    MessageEntitySpoiler: ("<tg-spoiler>", "</tg-spoiler>"),
    MessageEntityBlockquote: _blockquote_formatter,
    MessageEntityPre: lambda e, _: (
        ("<pre><code class='language-{}'>".format(escape(e.language)), "</code></pre>")
        if e.language
        else ("<pre><code>", "</code></pre>")
    ),
    MessageEntityEmail: lambda _, t: ('<a href="mailto:{}">'.format(escape(t)), "</a>"),
    MessageEntityUrl: lambda _, t: ('<a href="{}">'.format(escape(del_surrogate(t))), "</a>"),
    MessageEntityTextUrl: lambda e, _: ('<a href="{}">'.format(escape(e.url)), "</a>"),
    MessageEntityMentionName: lambda e, _: ('<a href="tg://user?id={}">'.format(e.user_id), "</a>"),
    MessageEntityCustomEmoji: lambda e, _: (
        '<tg-emoji emoji-id="{}">'.format(e.document_id),
        "</tg-emoji>",
    ),
}


class _TagWrapper:
    def __init__(self, text):
        self.text = text


def unparse(text: str, entities: Iterable[TypeMessageEntity]) -> str:
    """
    Performs the reverse operation to .parse(), effectively returning HTML
    given a normal text and its MessageEntity's.

    :param text: the text to be reconverted into HTML.
    :param entities: the MessageEntity's applied to the text.
    :return: a HTML representation of the combination of both inputs.
    """
    if not text:
        return text
    elif not entities:
        return escape(text, quote=False)

    if isinstance(entities, TLObject):
        entities = (entities,)

    text = add_surrogate(text)
    insert_at = []
    for i, entity in enumerate(entities):
        s = entity.offset
        e = entity.offset + entity.length
        delimiter = ENTITY_TO_FORMATTER.get(type(entity), None)
        if delimiter:
            if callable(delimiter):
                delimiter = delimiter(entity, text[s:e])
            insert_at.append((s, i, _TagWrapper(delimiter[0])))
            insert_at.append((e, -i, _TagWrapper(delimiter[1])))

    insert_at.sort(key=lambda t: (t[0], t[1]))
    next_escape_bound = len(text)
    while insert_at:
        at, _, what = insert_at.pop()
        while within_surrogate(text, at):
            at += 1

        if isinstance(what, _TagWrapper):
            text = (
                text[:at]
                + what.text
                + escape(text[at:next_escape_bound], quote=False)
                + text[next_escape_bound:]
            )
        else:
            text = (
                text[:at]
                + what
                + escape(text[at:next_escape_bound], quote=False)
                + text[next_escape_bound:]
            )
        next_escape_bound = at

    text = escape(text[:next_escape_bound], quote=False) + text[next_escape_bound:]

    return del_surrogate(text)
