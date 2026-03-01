"""
Simple HTML -> Telegram entity parser.
"""
import functools
from collections import deque
from html import escape
from html.parser import HTMLParser
from typing import Iterable, Tuple, List

from ..helpers import add_surrogate, del_surrogate, within_surrogate, strip_text
from ..tl import TLObject
from ..tl.types import (
    MessageEntityBold, MessageEntityItalic, MessageEntityCode,
    MessageEntityPre, MessageEntityEmail, MessageEntityUrl,
    MessageEntityTextUrl, MessageEntityMentionName,
    MessageEntityUnderline, MessageEntityStrike, MessageEntityBlockquote,
    MessageEntityCustomEmoji, MessageEntitySpoiler, TypeMessageEntity
)

_TAG_TO_ENTITY = {
    'strong': MessageEntityBold,
    'b': MessageEntityBold,
    'em': MessageEntityItalic,
    'i': MessageEntityItalic,
    'u': MessageEntityUnderline,
    'del': MessageEntityStrike,
    's': MessageEntityStrike,
    'blockquote': MessageEntityBlockquote,
    'code': MessageEntityCode,
    'pre': MessageEntityPre,
    'tg-emoji': MessageEntityCustomEmoji,
}

_MAILTO_LEN = len('mailto:')


class HTMLToTelegramParser(HTMLParser):
    __slots__ = ('text', 'entities', '_building_entities', '_open_tags', '_open_tags_meta')

    def __init__(self):
        super().__init__()
        self.text = ''
        self.entities = []
        self._building_entities = {}
        self._open_tags = deque()
        self._open_tags_meta = deque()

    def handle_starttag(self, tag, attrs):
        self._open_tags.appendleft(tag)
        self._open_tags_meta.appendleft(None)

        attrs_dict = dict(attrs)
        EntityType = _TAG_TO_ENTITY.get(tag)
        args = {}

        if tag == 'pre':
            args['language'] = ''
        elif tag == 'a':
            url = attrs_dict.get('href')
            if url is None:
                return
            if url.startswith('mailto:'):
                url = url[_MAILTO_LEN:]
                EntityType = MessageEntityEmail
            else:
                if self.get_starttag_text() == url:
                    EntityType = MessageEntityUrl
                else:
                    EntityType = MessageEntityTextUrl
                    args['url'] = del_surrogate(url)
                    url = None
            self._open_tags_meta.popleft()
            self._open_tags_meta.appendleft(url)
        elif tag == 'tg-emoji':
            emoji_id = attrs_dict.get('emoji-id')
            if emoji_id is None:
                return
            try:
                args['document_id'] = int(emoji_id)
            except ValueError:
                return
        elif tag == 'blockquote':
            expandable = attrs_dict.get('expandable') or ''
            expandable = expandable.lower() if expandable else ''
            if expandable == 'true':
                args['collapsed'] = False
        elif tag == 'code' and 'pre' in self._building_entities:
            pre = self._building_entities['pre']
            cls = attrs_dict.get('class', '')
            if cls.startswith('language-'):
                pre.language = cls[9:]
            EntityType = None

        if EntityType and tag not in self._building_entities:
            self._building_entities[tag] = EntityType(
                offset=len(self.text),
                length=0,
                **args)

    def handle_data(self, text):
        previous_tag = self._open_tags[0] if len(self._open_tags) > 0 else ''
        if previous_tag == 'a':
            url = self._open_tags_meta[0]
            if url:
                text = url

        for tag, entity in self._building_entities.items():
            entity.length += len(text)

        self.text += text

    def handle_endtag(self, tag):
        try:
            self._open_tags.popleft()
            self._open_tags_meta.popleft()
        except IndexError:
            pass
        entity = self._building_entities.pop(tag, None)
        if entity:
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

    parser = HTMLToTelegramParser()
    parser.feed(add_surrogate(html))
    text = strip_text(parser.text, parser.entities)
    parser.entities.reverse()
    parser.entities.sort(key=lambda entity: entity.offset)
    return del_surrogate(text), parser.entities


ENTITY_TO_FORMATTER = {
    MessageEntityBold: ('<strong>', '</strong>'),
    MessageEntityItalic: ('<em>', '</em>'),
    MessageEntityCode: ('<code>', '</code>'),
    MessageEntityUnderline: ('<u>', '</u>'),
    MessageEntityStrike: ('<del>', '</del>'),
    MessageEntityBlockquote: lambda e, _: (
        '<blockquote expandable="true">' if e.collapsed is False else '<blockquote>',
        '</blockquote>'
    ),
    MessageEntityPre: lambda e, _: (
        "<pre>\n"
        "    <code class='language-{}'>\n"
        "        ".format(e.language), "{}\n"
        "    </code>\n"
        "</pre>"
    ),
    MessageEntityEmail: lambda _, t: ('<a href="mailto:{}">'.format(t), '</a>'),
    MessageEntityUrl: lambda _, t: ('<a href="{}">'.format(t), '</a>'),
    MessageEntityTextUrl: lambda e, _: ('<a href="{}">'.format(escape(e.url)), '</a>'),
    MessageEntityMentionName: lambda e, _: ('<a href="tg://user?id={}">'.format(e.user_id), '</a>'),
    MessageEntityCustomEmoji: lambda e, _: ('<tg-emoji emoji-id="{}">'.format(e.document_id), '</tg-emoji>'),
}


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
        return escape(text)

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
            insert_at.append((s, i, delimiter[0]))
            insert_at.append((e, -i, delimiter[1]))

    insert_at.sort(key=lambda t: (t[0], t[1]))
    next_escape_bound = len(text)
    while insert_at:
        # Same logic as markdown.py
        at, _, what = insert_at.pop()
        while within_surrogate(text, at):
            at += 1

        text = text[:at] + what + escape(text[at:next_escape_bound]) + text[next_escape_bound:]
        next_escape_bound = at

    text = escape(text[:next_escape_bound]) + text[next_escape_bound:]

    return del_surrogate(text)
