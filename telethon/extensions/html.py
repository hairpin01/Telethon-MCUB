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
    "ins": MessageEntityUnderline,
    "del": MessageEntityStrike,
    "s": MessageEntityStrike,
    "strike": MessageEntityStrike,
    "blockquote": MessageEntityBlockquote,
    "code": MessageEntityCode,
    "mono": MessageEntityCode,
    "pre": MessageEntityPre,
    "tg-emoji": MessageEntityCustomEmoji,
    "tg-spoiler": MessageEntitySpoiler,
    "spoiler": MessageEntitySpoiler,
    "h1": MessageEntityBold,
    "h2": MessageEntityBold,
    "h3": MessageEntityBold,
    "h4": MessageEntityBold,
    "h5": MessageEntityBold,
    "h6": MessageEntityBold,
}

_MAILTO_LEN = len("mailto:")
_LITERAL_TAG = object()
_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
_BLOCK_TAGS = frozenset({"div", "p"}) | _HEADING_TAGS
_SUPPORTED_TAGS = frozenset(_TAG_TO_ENTITY) | {"a", "br", "div", "emoji", "mono", "p", "span"}
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

    def _append_block_separator(self):
        if self.text and not self.text.endswith("\n"):
            self._append_text("\n")

    def _mark_literal_starttag(self, tag):
        self._open_tags_meta.popleft()
        self._open_tags_meta.appendleft(_LITERAL_TAG)
        self._append_text(self.get_starttag_text() or f"<{tag}>")

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self._append_text("\n")
            return

        if tag in _BLOCK_TAGS:
            self._append_block_separator()

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
        elif tag == "span":
            classes = attrs_dict.get("class", "").split()
            if "tg-spoiler" in classes:
                EntityType = MessageEntitySpoiler
            else:
                self._mark_literal_starttag(tag)
                return
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
        elif (tag == "code" or tag == "mono") and "pre" in self._building_entities:
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
            if tag in _BLOCK_TAGS and matched_open_tag and not keep_literal:
                self._append_block_separator()
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
        if tag in _HEADING_TAGS:
            self._append_block_separator()


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


def _escape_html(value: object) -> str:
    if value is None:
        return ""
    return escape(str(value))


def _render_text_content(node: object) -> str:
    if node is None:
        return ""

    try:
        node_type = node.__class__.__name__
        if node_type == "TextPlain":
            return str(getattr(node, "text", ""))
        if node_type == "TextConcat":
            texts = getattr(node, "texts", None) or ()
            return "".join(_render_text_content(child) for child in texts)
        if hasattr(node, "text"):
            return _render_text_content(getattr(node, "text", None))
        if hasattr(node, "source"):
            return str(getattr(node, "source", ""))
        if hasattr(node, "alt"):
            return str(getattr(node, "alt", ""))
    except Exception:
        return ""

    return ""


def _render_text_link(href: object, text: object) -> str:
    return '<a href="{}">{}</a>'.format(_escape_html(href), _render_text_node(text))


def _render_text_node(node: object) -> str:
    if node is None:
        return ""

    try:
        node_type = node.__class__.__name__

        if node_type == "TextEmpty":
            return ""
        if node_type == "TextPlain":
            return _escape_html(getattr(node, "text", ""))
        if node_type == "TextConcat":
            texts = getattr(node, "texts", None) or ()
            return "".join(_render_text_node(child) for child in texts)

        tag_by_type = {
            "TextBold": ("b", "b"),
            "TextItalic": ("i", "i"),
            "TextUnderline": ("u", "u"),
            "TextStrike": ("s", "s"),
            "TextFixed": ("code", "code"),
            "TextSubscript": ("sub", "sub"),
            "TextSuperscript": ("sup", "sup"),
            "TextMarked": ("tg-spoiler", "tg-spoiler"),
            "TextSpoiler": ("tg-spoiler", "tg-spoiler"),
        }
        if node_type in tag_by_type:
            start_tag, end_tag = tag_by_type[node_type]
            return f"<{start_tag}>{_render_text_node(getattr(node, 'text', None))}</{end_tag}>"

        passthrough_types = {
            "TextBankCard",
            "TextBotCommand",
            "TextCashtag",
            "TextDate",
            "TextHashtag",
            "TextMention",
            "TextWithEntities",
        }
        if node_type in passthrough_types:
            return _render_text_node(getattr(node, "text", None))

        if node_type == "TextMath":
            return '<code class="math">{}</code>'.format(_escape_html(getattr(node, "source", "")))
        if node_type == "TextCustomEmoji":
            document_id = _escape_html(getattr(node, "document_id", ""))
            alt = _escape_html(getattr(node, "alt", ""))
            return '<tg-emoji emoji-id="{}">{}</tg-emoji>'.format(document_id, alt)
        if node_type == "TextUrl":
            return _render_text_link(getattr(node, "url", ""), getattr(node, "text", None))
        if node_type == "TextEmail":
            return _render_text_link(
                "mailto:{}".format(getattr(node, "email", "")),
                getattr(node, "text", None),
            )
        if node_type == "TextPhone":
            return _render_text_link(
                "tel:{}".format(getattr(node, "phone", "")),
                getattr(node, "text", None),
            )
        if node_type == "TextAutoUrl":
            text = getattr(node, "text", None)
            return _render_text_link(_render_text_content(text), text)
        if node_type == "TextAutoEmail":
            text = getattr(node, "text", None)
            return _render_text_link("mailto:{}".format(_render_text_content(text)), text)
        if node_type == "TextAutoPhone":
            text = getattr(node, "text", None)
            return _render_text_link("tel:{}".format(_render_text_content(text)), text)
        if node_type == "TextMentionName":
            user_id = _escape_html(getattr(node, "user_id", ""))
            text = _render_text_node(getattr(node, "text", None))
            return f'<a href="tg://user?id={user_id}">{text}</a>'
        if node_type == "TextImage":
            return "[img:{}]".format(_escape_html(getattr(node, "document_id", "")))
        if node_type == "TextAnchor":
            name = _escape_html(getattr(node, "name", ""))
            return f'<a name="{name}">{_render_text_node(getattr(node, "text", None))}</a>'
    except Exception:
        return ""

    return ""


def _render_code_content(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return _escape_html(value)
    return _render_text_node(value)


def _render_code_block(text: object, language: object = "", class_name: object = None) -> str:
    if class_name is not None:
        code_class = class_name
    elif language:
        code_class = "language-{}".format(language)
    else:
        code_class = ""
    class_attr = ' class="{}"'.format(_escape_html(code_class)) if code_class else ""
    return "<pre><code{}>{}</code></pre>\n".format(class_attr, _render_code_content(text))


def _render_blocks(blocks: object, separator: str = "") -> str:
    try:
        rendered = (_render_block(block) for block in blocks or ())
        return separator.join(part for part in rendered if part)
    except Exception:
        return ""


def _render_caption(caption: object) -> str:
    if caption is None:
        return ""

    try:
        if caption.__class__.__name__ == "PageCaption":
            text = _render_text_node(getattr(caption, "text", None))
            credit = _render_text_node(getattr(caption, "credit", None))
            if text and credit:
                return "{}\n<i>{}</i>".format(text, credit)
            return text or credit
        return _render_text_node(caption)
    except Exception:
        return ""


def _render_labeled_block(label: str, caption: object = None) -> str:
    rendered = label
    rendered_caption = _render_caption(caption)
    if rendered_caption:
        rendered = "{}\n{}".format(rendered, rendered_caption)
    return rendered + "\n"


def _render_block_link(label: str, url: object) -> str:
    if not url:
        return _escape_html(label)
    safe_url = _escape_html(url)
    return '<a href="{}">{}</a>'.format(safe_url, _escape_html(label))


def _render_table(block: object) -> str:
    try:
        lines = []
        title = _render_text_node(getattr(block, "title", None))
        if title:
            lines.append("<b>{}</b>".format(title))

        for row in getattr(block, "rows", None) or ():
            cells = []
            for cell in getattr(row, "cells", None) or ():
                content = _render_text_node(getattr(cell, "text", None)).strip()
                if getattr(cell, "header", False) and content:
                    content = "<b>{}</b>".format(content)
                cells.append(content)
            if cells:
                lines.append(" | ".join(cells))

        return "\n".join(lines) + ("\n" if lines else "")
    except Exception:
        return ""


def _render_related_article(article: object) -> str:
    try:
        url = getattr(article, "url", "")
        title = getattr(article, "title", None) or url or "article"
        rendered = _render_block_link(str(title), url)
        description = getattr(article, "description", None)
        if description:
            rendered = "{} — {}".format(rendered, _escape_html(description))
        return rendered
    except Exception:
        return ""


def _render_related_articles(block: object) -> str:
    try:
        lines = []
        title = _render_text_node(getattr(block, "title", None))
        if title:
            lines.append("<b>{}</b>".format(title))
        for article in getattr(block, "articles", None) or ():
            rendered = _render_related_article(article)
            if rendered:
                lines.append("• {}".format(rendered))
        return "\n".join(lines) + ("\n" if lines else "")
    except Exception:
        return ""


def _render_list_item(item: object) -> str:
    if item is None:
        return ""

    try:
        if item.__class__.__name__.startswith("Text"):
            return _render_text_node(item).strip()
        if isinstance(item, str):
            return _escape_html(item).strip()
        if hasattr(item, "text"):
            return _render_text_node(getattr(item, "text", None)).strip()

        blocks = getattr(item, "blocks", None)
        if blocks:
            return " ".join(
                rendered
                for rendered in (_render_block(block).strip() for block in blocks)
                if rendered
            )

        return _render_text_node(item).strip()
    except Exception:
        return ""


def _render_list(block: object, ordered: bool = False) -> str:
    try:
        items = getattr(block, "items", None) or ()
        is_ordered = ordered or bool(getattr(block, "ordered", False))
        start = getattr(block, "start", None) or 1
        try:
            start = int(start)
        except (TypeError, ValueError):
            start = 1

        lines = []
        for index, item in enumerate(items):
            content = _render_list_item(item)
            if not content:
                continue

            if is_ordered:
                marker = getattr(item, "num", None) or getattr(item, "value", None)
                marker = str(marker) if marker is not None else "{}.".format(start + index)
                if marker[-1:] not in (".", ")", ":"):
                    marker = "{}.".format(marker)
                lines.append("{} {}".format(_escape_html(marker), content))
            else:
                lines.append("• {}".format(content))

        return "\n".join(lines) + ("\n" if lines else "")
    except Exception:
        return ""


def _render_block(block: object) -> str:
    if block is None:
        return ""

    try:
        block_type = block.__class__.__name__

        if block_type == "PageBlockParagraph":
            return _render_text_node(getattr(block, "text", None)) + "\n"
        if block_type == "PageBlockMath":
            return _render_code_block(getattr(block, "source", ""), class_name="math")
        if block_type == "PageBlockCode":
            return _render_code_block(
                getattr(block, "text", getattr(block, "source", "")),
                getattr(block, "language", ""),
            )
        if block_type == "PageBlockPreformatted":
            return _render_code_block(
                getattr(block, "text", None),
                getattr(block, "language", ""),
            )
        bold_blocks = {
            "PageBlockHeader",
            "PageBlockHeading1",
            "PageBlockHeading2",
            "PageBlockHeading3",
            "PageBlockHeading4",
            "PageBlockHeading5",
            "PageBlockHeading6",
            "PageBlockSubheader",
            "PageBlockSubtitle",
            "PageBlockTitle",
        }
        if block_type in bold_blocks:
            return "<b>{}</b>\n".format(_render_text_node(getattr(block, "text", None)))
        italic_blocks = {
            "PageBlockAuthorDate",
            "PageBlockFooter",
            "PageBlockKicker",
        }
        if block_type == "PageBlockAuthorDate":
            return "<i>{}</i>\n".format(_render_text_node(getattr(block, "author", None)))
        if block_type in italic_blocks:
            return "<i>{}</i>\n".format(_render_text_node(getattr(block, "text", None)))
        if block_type in {"PageBlockBlockquote", "PageBlockPullquote"}:
            return "<blockquote>{}</blockquote>\n".format(
                _render_text_node(getattr(block, "text", None))
            )
        if block_type == "PageBlockBlockquoteBlocks":
            content = _render_blocks(getattr(block, "blocks", None)).strip()
            return "<blockquote>{}</blockquote>\n".format(content) if content else ""
        if block_type == "PageBlockDetails":
            title = _render_text_node(getattr(block, "title", None))
            content = _render_blocks(getattr(block, "blocks", None)).strip()
            if title and content:
                return "<b>{}</b>\n{}\n".format(title, content)
            return (title or content) + ("\n" if title or content else "")
        if block_type == "PageBlockCover":
            return _render_block(getattr(block, "cover", None))
        if block_type in {"PageBlockCollage", "PageBlockSlideshow"}:
            return _render_blocks(getattr(block, "items", None)) or "[media]\n"
        if block_type == "PageBlockAnchor":
            return '<a name="{}"></a>\n'.format(_escape_html(getattr(block, "name", "")))
        if block_type == "PageBlockTable":
            return _render_table(block)
        if block_type == "PageBlockRelatedArticles":
            return _render_related_articles(block)
        if block_type == "PageBlockThinking":
            return "<blockquote>{}</blockquote>\n".format(
                _render_text_node(getattr(block, "text", None))
            )
        if block_type == "PageBlockEmbed":
            label = _render_block_link("[embed]", getattr(block, "url", None))
            return _render_labeled_block(label, getattr(block, "caption", None))
        if block_type == "PageBlockEmbedPost":
            author = getattr(block, "author", None) or "[embed post]"
            header = _render_block_link(author, getattr(block, "url", None))
            body = _render_blocks(getattr(block, "blocks", None)).strip()
            caption = _render_caption(getattr(block, "caption", None))
            parts = [part for part in (header, body, caption) if part]
            return "\n".join(parts) + ("\n" if parts else "")
        if block_type in {"PageBlockChannel", "PageBlockMap"}:
            label = "[map]" if block_type == "PageBlockMap" else "[channel]"
            return _render_labeled_block(label, getattr(block, "caption", None))
        if block_type == "PageBlockList":
            return _render_list(block)
        if block_type == "PageBlockOrderedList":
            return _render_list(block, ordered=True)
        if block_type == "PageBlockDivider":
            return "\n---\n"
        if block_type in {
            "PageBlockPhoto",
            "PageBlockVideo",
            "PageBlockAudio",
            "PageBlockDocument",
        }:
            return _render_labeled_block("[media]", getattr(block, "caption", None))
    except Exception:
        return ""

    return ""


def rich_message_to_html(rich_message: object) -> str:
    """Convert a RichMessage TL object to an HTML string."""
    try:
        blocks = getattr(rich_message, "blocks", None) or ()
        return "".join(_render_block(block) for block in blocks).rstrip()
    except Exception:
        return ""


def message_to_html(message: object) -> str:
    """
    Returns HTML for any Telethon Message object.

    Priority:
    1. If message.rich_message is present and has blocks → use rich_message_to_html()
    2. Otherwise → fall back to unparse(message.message, message.entities)
    """
    rich_message = getattr(message, "rich_message", None)
    if getattr(rich_message, "blocks", None):
        return rich_message_to_html(rich_message)

    return unparse(getattr(message, "message", "") or "", getattr(message, "entities", None) or [])
