"""
Rich HTML → Telegram rich-message AST parser.
Telegram Bot API 10.1+ (sendRichMessage / blocks field).

Usage:
    from richparser import parse_rich_html, render_rich_html

    blocks = parse_rich_html(html_str)         # List[Block]
    tl_dicts = [b.to_tl() for b in blocks]    # dictionaries for TL constructors
    back = render_rich_html(blocks)            # round-trip HTML

Supported Bot API 10.1/10.2 blocks:
    Paragraph · SectionHeading · Preformatted · Footer · Divider
    MathematicalExpression · Anchor · List · BlockQuotation
    PullQuotation · Collage · Slideshow · Table · Details
    Map · Photo · Video · Audio · Animation · VoiceNote · Thinking

Inline: Bold · Italic · Underline · Strikethrough · Spoiler · Code
        Subscript · Superscript · Marked · Url · Mention · Email
        Phone · CustomEmoji · DateTime · MathInline · AnchorLink
        Reference

Input HTML uses official Telegram Rich HTML tags. Some MCUB-friendly
aliases are accepted directly by this parser where practical.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
from html import escape
from urllib.parse import urlsplit
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Union

from ..tl import types

def _attr(attrs: list, *names: str, default: Optional[str] = None) -> Optional[str]:
    names_l = {n.lower() for n in names}
    for k, v in attrs:
        if k.lower() in names_l:
            return "" if v is None else v
    return default


def _attrs_d(attrs: list) -> Dict[str, str]:
    return {k.lower(): ("" if v is None else v) for k, v in attrs}


def _truthy(v: Optional[str]) -> Optional[bool]:
    if v is None:
        return None
    return str(v).strip().lower() in ("", "1", "true", "yes", "on", "checked")


def _int_attr(v: Optional[str], default: Optional[int] = None) -> Optional[int]:
    if v is None:
        return default
    try:
        return int(v)
    except (ValueError, TypeError):
        return default


def _float_attr(v: Optional[str]) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None

def _ih(items: "List[Inline]") -> str:
    """Serialize list of inline items to HTML."""
    return "".join(i.to_html() for i in items)


def _it(items: "List[Inline]") -> dict:
    """Serialize list of inline items to a single TL RichText dict."""
    if not items:
        return {"_": "RichTextEmpty"}
    if len(items) == 1:
        return items[0].to_tl()
    return {"_": "RichTextConcat", "texts": [i.to_tl() for i in items]}


@dataclass
class TextPlain:
    text: str

    def to_html(self) -> str:
        return escape(self.text)

    def to_tl(self) -> dict:
        return {"_": "RichTextPlain", "text": self.text}


def _wrap(tag: str, items: "List[Inline]") -> str:
    return f"<{tag}>{_ih(items)}</{tag}>"


@dataclass
class TextBold:
    items: List["Inline"] = field(default_factory=list)
    def to_html(self) -> str: return _wrap("b", self.items)
    def to_tl(self) -> dict: return {"_": "RichTextBold", "text": _it(self.items)}


@dataclass
class TextItalic:
    items: List["Inline"] = field(default_factory=list)
    def to_html(self) -> str: return _wrap("i", self.items)
    def to_tl(self) -> dict: return {"_": "RichTextItalic", "text": _it(self.items)}


@dataclass
class TextUnderline:
    items: List["Inline"] = field(default_factory=list)
    def to_html(self) -> str: return _wrap("u", self.items)
    def to_tl(self) -> dict: return {"_": "RichTextUnderline", "text": _it(self.items)}


@dataclass
class TextStrike:
    items: List["Inline"] = field(default_factory=list)
    def to_html(self) -> str: return _wrap("s", self.items)
    def to_tl(self) -> dict: return {"_": "RichTextStrikethrough", "text": _it(self.items)}


@dataclass
class TextSpoiler:
    items: List["Inline"] = field(default_factory=list)
    def to_html(self) -> str: return _wrap("tg-spoiler", self.items)
    def to_tl(self) -> dict: return {"_": "RichTextSpoiler", "text": _it(self.items)}


@dataclass
class TextCode:
    text: str
    def to_html(self) -> str: return f"<code>{escape(self.text)}</code>"
    def to_tl(self) -> dict: return {"_": "RichTextCode", "text": self.text}


@dataclass
class TextSubscript:
    items: List["Inline"] = field(default_factory=list)
    def to_html(self) -> str: return _wrap("sub", self.items)
    def to_tl(self) -> dict: return {"_": "RichTextSubscript", "text": _it(self.items)}


@dataclass
class TextSuperscript:
    items: List["Inline"] = field(default_factory=list)
    def to_html(self) -> str: return _wrap("sup", self.items)
    def to_tl(self) -> dict: return {"_": "RichTextSuperscript", "text": _it(self.items)}


@dataclass
class TextMarked:
    """<mark> — RichTextMarked (highlight)."""
    items: List["Inline"] = field(default_factory=list)
    def to_html(self) -> str: return _wrap("mark", self.items)
    def to_tl(self) -> dict: return {"_": "RichTextMarked", "text": _it(self.items)}


@dataclass
class TextUrl:
    url: str
    items: List["Inline"] = field(default_factory=list)
    webpage_id: int = 0
    def to_html(self) -> str:
        return f'<a href="{escape(self.url, quote=True)}">{_ih(self.items)}</a>'
    def to_tl(self) -> dict:
        return {"_": "RichTextUrl", "url": self.url, "webpage_id": self.webpage_id,
                "text": _it(self.items)}


@dataclass
class TextMention:
    user_id: int
    items: List["Inline"] = field(default_factory=list)
    def to_html(self) -> str:
        return f'<a href="tg://user?id={self.user_id}">{_ih(self.items)}</a>'
    def to_tl(self) -> dict:
        return {"_": "RichTextMention", "user_id": self.user_id, "text": _it(self.items)}


@dataclass
class TextEmail:
    email: str
    items: List["Inline"] = field(default_factory=list)
    def to_html(self) -> str:
        return f'<a href="mailto:{escape(self.email, quote=True)}">{_ih(self.items)}</a>'
    def to_tl(self) -> dict:
        return {"_": "RichTextEmailAddress", "email": self.email, "text": _it(self.items)}


@dataclass
class TextPhone:
    phone: str
    items: List["Inline"] = field(default_factory=list)
    def to_html(self) -> str:
        return f'<a href="tel:{escape(self.phone, quote=True)}">{_ih(self.items)}</a>'
    def to_tl(self) -> dict:
        return {"_": "RichTextPhoneNumber", "phone_number": self.phone,
                "text": _it(self.items)}


@dataclass
class TextEmoji:
    emoji_id: str  # Keep as string to avoid losing big integers.
    alt: str = " "
    def to_html(self) -> str:
        return (f'<tg-emoji emoji-id="{escape(self.emoji_id, quote=True)}">'
                f'{escape(self.alt)}</tg-emoji>')
    def to_tl(self) -> dict:
        return {"_": "RichTextCustomEmoji", "document_id": int(self.emoji_id),
                "text": self.alt}


@dataclass
class TextDateTime:
    unix: int
    format: Optional[str] = None
    text: str = ""
    def to_html(self) -> str:
        fmt = f' format="{escape(self.format, quote=True)}"' if self.format else ""
        return f'<tg-time unix="{self.unix}"{fmt}>{escape(self.text)}</tg-time>'
    def to_tl(self) -> dict:
        d: dict = {"_": "RichTextDateTime", "date_time": self.unix, "text": self.text}
        if self.format:
            d["format"] = self.format
        return d


@dataclass
class TextMathInline:
    formula: str
    def to_html(self) -> str: return f"<tg-math>{escape(self.formula)}</tg-math>"
    def to_tl(self) -> dict:
        return {"_": "RichTextMathematicalExpression", "expression": self.formula}


@dataclass
class TextAnchorLink:
    """<a href="#name"> → RichTextAnchorLink."""
    name: str
    items: List["Inline"] = field(default_factory=list)
    def to_html(self) -> str:
        return f'<a href="#{escape(self.name, quote=True)}">{_ih(self.items)}</a>'
    def to_tl(self) -> dict:
        return {"_": "RichTextAnchorLink", "anchor": self.name,
                "url": f"#{self.name}", "text": _it(self.items)}


@dataclass
class TextReference:
    """<tg-reference name="..."> → RichTextReference."""
    name: str
    items: List["Inline"] = field(default_factory=list)
    def to_html(self) -> str:
        return (f'<tg-reference name="{escape(self.name, quote=True)}">'
                f'{_ih(self.items)}</tg-reference>')
    def to_tl(self) -> dict:
        return {"_": "RichTextReference", "anchor": self.name, "text": _it(self.items)}


Inline = Union[
    TextPlain, TextBold, TextItalic, TextUnderline, TextStrike,
    TextSpoiler, TextCode, TextSubscript, TextSuperscript, TextMarked,
    TextUrl, TextMention, TextEmail, TextPhone, TextEmoji, TextDateTime,
    TextMathInline, TextAnchorLink, TextReference,
]


_MAX_NESTING = 100
_INT32_MIN, _INT32_MAX = -(2 ** 31), 2 ** 31 - 1
_INT64_MIN, _INT64_MAX = -(2 ** 63), 2 ** 63 - 1


def _inline_plain(items: object) -> str:
    """Return visible text from parser inline nodes without dropping nesting."""
    result = []
    stack = list(reversed(items or []))
    while stack:
        item = stack.pop()
        if isinstance(item, TextPlain):
            result.append(item.text)
        elif isinstance(item, TextCode):
            result.append(item.text)
        elif isinstance(item, TextMathInline):
            result.append(item.formula)
        elif isinstance(item, TextEmoji):
            result.append(item.alt)
        elif isinstance(item, TextDateTime):
            result.append(item.text)
        elif hasattr(item, "items"):
            stack.extend(reversed(item.items))
    return "".join(result)


def _bounded_int(value: object, minimum: int, maximum: int) -> Optional[int]:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if minimum <= number <= maximum else None


def _safe_href(value: object) -> Optional[str]:
    href = str(value or "")
    scheme = urlsplit(href).scheme.lower()
    return href if not scheme or scheme in {"http", "https", "tg", "mailto", "tel"} else None

@dataclass
class Caption:
    content: List[Inline] = field(default_factory=list)
    credit: Optional[List[Inline]] = None

    def to_html(self) -> str:
        inner = _ih(self.content)
        if self.credit:
            inner += f"<cite>{_ih(self.credit)}</cite>"
        return f"<figcaption>{inner}</figcaption>"

    def to_tl(self) -> dict:
        return {
            "_": "RichBlockCaption",
            "text": _it(self.content),
            "credit": _it(self.credit) if self.credit else {"_": "RichTextEmpty"},
        }

@dataclass
class BlockParagraph:
    """<p> → InputRichBlockParagraph"""
    content: List[Inline] = field(default_factory=list)
    def to_html(self) -> str: return f"<p>{_ih(self.content)}</p>"
    def to_tl(self) -> dict: return {"_": "InputRichBlockParagraph", "text": _it(self.content)}


@dataclass
class BlockHeading:
    """<h1>…<h6> → InputRichBlockSectionHeading"""
    level: int  # 1–6
    content: List[Inline] = field(default_factory=list)
    def to_html(self) -> str:
        return f"<h{self.level}>{_ih(self.content)}</h{self.level}>"
    def to_tl(self) -> dict:
        return {"_": "InputRichBlockSectionHeading", "level": self.level,
                "text": _it(self.content)}


@dataclass
class BlockPreformatted:
    """<pre> / <pre><code class="language-X"> → InputRichBlockPreformatted"""
    text: str
    language: Optional[str] = None
    def to_html(self) -> str:
        if self.language:
            lang = escape(self.language, quote=True)
            return f'<pre><code class="language-{lang}">{escape(self.text)}</code></pre>'
        return f"<pre>{escape(self.text)}</pre>"
    def to_tl(self) -> dict:
        d: dict = {"_": "InputRichBlockPreformatted", "text": self.text}
        if self.language:
            d["language"] = self.language
        return d


@dataclass
class BlockFooter:
    """<footer> → InputRichBlockFooter"""
    content: List[Inline] = field(default_factory=list)
    def to_html(self) -> str: return f"<footer>{_ih(self.content)}</footer>"
    def to_tl(self) -> dict:
        return {"_": "InputRichBlockFooter", "text": _it(self.content)}


@dataclass
class BlockDivider:
    """<hr/> → InputRichBlockDivider"""
    def to_html(self) -> str: return "<hr/>"
    def to_tl(self) -> dict: return {"_": "InputRichBlockDivider"}


@dataclass
class BlockMath:
    """<tg-math-block> → InputRichBlockMathematicalExpression"""
    formula: str
    def to_html(self) -> str: return f"<tg-math-block>{escape(self.formula)}</tg-math-block>"
    def to_tl(self) -> dict:
        return {"_": "InputRichBlockMathematicalExpression", "expression": self.formula}


@dataclass
class BlockAnchor:
    """<a name="x"> (block-level) → InputRichBlockAnchor"""
    name: str
    text: str = ""
    def to_html(self) -> str:
        return f'<a name="{escape(self.name, quote=True)}">{escape(self.text)}</a>'
    def to_tl(self) -> dict:
        return {"_": "InputRichBlockAnchor", "name": self.name}


@dataclass
class ListItem:
    content: List[Inline] = field(default_factory=list)
    blocks: List["Block"] = field(default_factory=list)
    checkbox: Optional[bool] = None   # None = no checkbox; True/False = checked state.
    value: Optional[int] = None       # <li value="N">
    num: Optional[str] = None         # Compatibility metadata for ordered TL items.
    type: Optional[str] = None

    def to_html(self) -> str:
        val_attr = f' value="{self.value}"' if self.value is not None else ""
        num_attr = f' data-num="{escape(self.num, quote=True)}"' if self.num is not None else ""
        prefix = ""
        if self.checkbox is not None:
            checked = " checked" if self.checkbox else ""
            prefix = f'<input type="checkbox"{checked}>'
        type_attr = f' type="{escape(self.type, quote=True)}"' if self.type else ""
        return f"<li{val_attr}{num_attr}{type_attr}>{prefix}{_ih(self.content)}{''.join(block.to_html() for block in self.blocks)}</li>"

    def to_tl(self) -> dict:
        d: dict = {"_": "InputRichBlockListItem", "text": _it(self.content)}
        if self.blocks:
            d["blocks"] = [block.to_tl() for block in self.blocks]
        if self.checkbox is not None:
            d["checkbox"] = True
            d["checked"] = self.checkbox
        if self.value is not None:
            d["value"] = self.value
        if self.num is not None:
            d["num"] = self.num
        if self.type:
            d["type"] = self.type
        return d


@dataclass
class BlockList:
    """<ul>/<ol> → InputRichBlockList"""
    ordered: bool = False
    items: List[ListItem] = field(default_factory=list)
    start: Optional[int] = None
    reversed_: bool = False
    type: Optional[str] = None

    def to_html(self) -> str:
        tag = "ol" if self.ordered else "ul"
        attrs = ""
        if self.start is not None:
            attrs += f' start="{self.start}"'
        if self.reversed_:
            attrs += " reversed"
        if self.type:
            attrs += f' type="{escape(self.type, quote=True)}"'
        return f"<{tag}{attrs}>{''.join(i.to_html() for i in self.items)}</{tag}>"

    def to_tl(self) -> dict:
        d: dict = {"_": "InputRichBlockList", "ordered": self.ordered,
                   "items": [i.to_tl() for i in self.items]}
        if self.start is not None:
            d["start"] = self.start
        if self.reversed_:
            d["reversed"] = True
        if self.type:
            d["type"] = self.type
        return d


@dataclass
class BlockQuotation:
    """<blockquote> → InputRichBlockBlockQuotation"""
    content: List[Inline] = field(default_factory=list)
    author: Optional[List[Inline]] = None
    expandable: Optional[bool] = None

    def to_html(self) -> str:
        inner = _ih(self.content)
        if self.author:
            inner += f"<cite>{_ih(self.author)}</cite>"
        exp = ""
        if self.expandable is not None:
            exp = f' expandable="{"true" if self.expandable else "false"}"'
        return f"<blockquote{exp}>{inner}</blockquote>"

    def to_tl(self) -> dict:
        d: dict = {"_": "InputRichBlockBlockQuotation", "text": _it(self.content)}
        if self.author:
            d["author"] = _it(self.author)
        if self.expandable is not None:
            d["expandable"] = self.expandable
        return d


@dataclass
class BlockPullQuotation:
    """<aside> → InputRichBlockPullQuotation"""
    content: List[Inline] = field(default_factory=list)
    author: Optional[List[Inline]] = None

    def to_html(self) -> str:
        inner = _ih(self.content)
        if self.author:
            inner += f"<cite>{_ih(self.author)}</cite>"
        return f"<aside>{inner}</aside>"

    def to_tl(self) -> dict:
        d: dict = {"_": "InputRichBlockPullQuotation", "text": _it(self.content)}
        if self.author:
            d["author"] = _it(self.author)
        return d


@dataclass
class MediaItem:
    src: str
    spoiler: Optional[bool] = None

    def to_img_html(self) -> str:
        attrs = f' src="{escape(self.src, quote=True)}"'
        if self.spoiler:
            attrs += " tg-spoiler"
        return f"<img{attrs}/>"


@dataclass
class BlockCollage:
    """<tg-collage> → InputRichBlockCollage"""
    items: List[MediaItem] = field(default_factory=list)
    caption: Optional[Caption] = None

    def to_html(self) -> str:
        inner = "".join(i.to_img_html() for i in self.items)
        if self.caption:
            inner += self.caption.to_html()
        return f"<tg-collage>{inner}</tg-collage>"

    def to_tl(self) -> dict:
        d: dict = {"_": "InputRichBlockCollage",
                   "items": [{"src": i.src, **({"spoiler": True} if i.spoiler else {})}
                              for i in self.items]}
        if self.caption:
            d["caption"] = self.caption.to_tl()
        return d


@dataclass
class BlockSlideshow:
    """<tg-slideshow> → InputRichBlockSlideshow"""
    items: List[MediaItem] = field(default_factory=list)
    caption: Optional[Caption] = None

    def to_html(self) -> str:
        inner = "".join(i.to_img_html() for i in self.items)
        if self.caption:
            inner += self.caption.to_html()
        return f"<tg-slideshow>{inner}</tg-slideshow>"

    def to_tl(self) -> dict:
        d: dict = {"_": "InputRichBlockSlideshow",
                   "items": [{"src": i.src, **({"spoiler": True} if i.spoiler else {})}
                              for i in self.items]}
        if self.caption:
            d["caption"] = self.caption.to_tl()
        return d


@dataclass
class TableCell:
    content: List[Inline] = field(default_factory=list)
    align: Optional[str] = None
    valign: Optional[str] = None
    is_header: bool = False
    colspan: Optional[int] = None
    rowspan: Optional[int] = None

    def to_html(self) -> str:
        tag = "th" if self.is_header else "td"
        a = ""
        if self.align:
            a += f' align="{escape(self.align, quote=True)}"'
        if self.valign:
            a += f' valign="{escape(self.valign, quote=True)}"'
        if self.colspan and self.colspan > 1:
            a += f' colspan="{self.colspan}"'
        if self.rowspan and self.rowspan > 1:
            a += f' rowspan="{self.rowspan}"'
        return f"<{tag}{a}>{_ih(self.content)}</{tag}>"

    def to_tl(self) -> dict:
        d: dict = {"_": "RichBlockTableCell", "text": _it(self.content),
                   "header": self.is_header}
        if self.align:
            d["align"] = self.align
        if self.valign:
            d["valign"] = self.valign
        if self.colspan:
            d["colspan"] = self.colspan
        if self.rowspan:
            d["rowspan"] = self.rowspan
        return d


@dataclass
class TableRow:
    cells: List[TableCell] = field(default_factory=list)

    def to_html(self) -> str:
        return f"<tr>{''.join(c.to_html() for c in self.cells)}</tr>"

    def to_tl(self) -> dict:
        return {"_": "RichBlockTableRow", "cells": [c.to_tl() for c in self.cells]}


@dataclass
class BlockTable:
    """<table> → InputRichBlockTable"""
    rows: List[TableRow] = field(default_factory=list)
    title: Optional[str] = None
    bordered: Optional[bool] = None
    striped: Optional[bool] = None
    compact: Optional[bool] = None

    def to_html(self) -> str:
        a = ""
        if self.bordered:
            a += " bordered"
        if self.striped:
            a += " striped"
        if self.compact:
            a += " compact"
        inner = ""
        if self.title:
            inner += f"<caption>{escape(self.title)}</caption>"
        inner += "".join(r.to_html() for r in self.rows)
        return f"<table{a}>{inner}</table>"

    def to_tl(self) -> dict:
        d: dict = {"_": "InputRichBlockTable",
                   "rows": [r.to_tl() for r in self.rows]}
        if self.title:
            d["title"] = self.title
        if self.bordered is not None:
            d["bordered"] = self.bordered
        if self.striped is not None:
            d["striped"] = self.striped
        if self.compact is not None:
            d["compact"] = self.compact
        return d


@dataclass
class BlockDetails:
    """<details> → InputRichBlockDetails"""
    title: str
    blocks: List[Any] = field(default_factory=list)
    open: Optional[bool] = None

    def to_html(self) -> str:
        open_a = " open" if self.open else ""
        return (f"<details{open_a}>"
                f"<summary>{escape(self.title)}</summary>"
                f"{''.join(block.to_html() for block in self.blocks)}</details>")

    def to_tl(self) -> dict:
        d: dict = {"_": "InputRichBlockDetails", "title": self.title,
                   "blocks": [block.to_tl() for block in self.blocks]}
        if self.open is not None:
            d["open"] = self.open
        return d


@dataclass
class BlockMap:
    """<tg-map lat="…" long="…"> → InputRichBlockMap"""
    lat: float
    long: float
    zoom: Optional[int] = None
    caption: Optional[Caption] = None

    def to_html(self) -> str:
        a = f' lat="{self.lat}" long="{self.long}"'
        if self.zoom is not None:
            a += f' zoom="{self.zoom}"'
        if self.caption:
            return f"<figure><tg-map{a}/>{self.caption.to_html()}</figure>"
        return f"<tg-map{a}/>"

    def to_tl(self) -> dict:
        d: dict = {"_": "InputRichBlockMap", "lat": self.lat, "long": self.long}
        if self.zoom is not None:
            d["zoom"] = self.zoom
        if self.caption:
            d["caption"] = self.caption.to_tl()
        return d


@dataclass
class BlockPhoto:
    """<img src="…"> → InputRichBlockPhoto"""
    src: str
    caption: Optional[Caption] = None
    spoiler: Optional[bool] = None

    def to_html(self) -> str:
        a = f' src="{escape(self.src, quote=True)}"'
        if self.spoiler:
            a += " tg-spoiler"
        if self.caption:
            return f"<figure><img{a}/>{self.caption.to_html()}</figure>"
        return f"<img{a}/>"

    def to_tl(self) -> dict:
        d: dict = {"_": "InputRichBlockPhoto", "src": self.src}
        if self.caption:
            d["caption"] = self.caption.to_tl()
        if self.spoiler:
            d["spoiler"] = True
        return d


@dataclass
class BlockVideo:
    """<video src="…"> → InputRichBlockVideo"""
    src: str
    caption: Optional[Caption] = None
    spoiler: Optional[bool] = None

    def to_html(self) -> str:
        a = f' src="{escape(self.src, quote=True)}"'
        if self.spoiler:
            a += " tg-spoiler"
        if self.caption:
            return f"<figure><video{a}></video>{self.caption.to_html()}</figure>"
        return f"<video{a}></video>"

    def to_tl(self) -> dict:
        d: dict = {"_": "InputRichBlockVideo", "src": self.src}
        if self.caption:
            d["caption"] = self.caption.to_tl()
        if self.spoiler:
            d["spoiler"] = True
        return d


@dataclass
class BlockAudio:
    """<audio src="…"> → InputRichBlockAudio"""
    src: str
    caption: Optional[Caption] = None

    def to_html(self) -> str:
        a = f' src="{escape(self.src, quote=True)}"'
        if self.caption:
            return f"<figure><audio{a}></audio>{self.caption.to_html()}</figure>"
        return f"<audio{a}></audio>"

    def to_tl(self) -> dict:
        d: dict = {"_": "InputRichBlockAudio", "src": self.src}
        if self.caption:
            d["caption"] = self.caption.to_tl()
        return d


@dataclass
class BlockAnimation:
    """<tg-animation src="…"> → InputRichBlockAnimation"""
    src: str
    caption: Optional[Caption] = None
    spoiler: Optional[bool] = None

    def to_html(self) -> str:
        a = f' src="{escape(self.src, quote=True)}"'
        if self.spoiler:
            a += " tg-spoiler"
        if self.caption:
            return f"<figure><tg-animation{a}/>{self.caption.to_html()}</figure>"
        return f"<tg-animation{a}/>"

    def to_tl(self) -> dict:
        d: dict = {"_": "InputRichBlockAnimation", "src": self.src}
        if self.caption:
            d["caption"] = self.caption.to_tl()
        if self.spoiler:
            d["spoiler"] = True
        return d


@dataclass
class BlockVoiceNote:
    """<tg-voice src="…"> → InputRichBlockVoiceNote"""
    src: str

    def to_html(self) -> str:
        return f'<tg-voice src="{escape(self.src, quote=True)}"/>'

    def to_tl(self) -> dict:
        return {"_": "InputRichBlockVoiceNote", "src": self.src}


@dataclass
class BlockThinking:
    """<tg-thinking> → InputRichBlockThinking"""
    content: str

    def to_html(self) -> str:
        return f"<tg-thinking>{escape(self.content)}</tg-thinking>"

    def to_tl(self) -> dict:
        return {"_": "InputRichBlockThinking", "text": self.content}


def _button_attr_names(button_type: str) -> set[str]:
    common = {"type", "style"}
    by_type = {
        "url": {"url"}, "web_app": {"url"},
        "callback_data": {"data", "data-base64", "requires-password"},
        "login_url": {"url", "forward-text", "fwd-text", "button-id", "request-write-access"},
        "switch_inline_query": {"query"},
        "switch_inline_query_current_chat": {"query"},
        "switch_inline_query_chosen_chat": {
            "query", "allow-user-chats", "allow-bot-chats", "allow-group-chats", "allow-channel-chats",
        },
        "copy_text": {"text", "copy-text"}, "user_profile": {"user-id"},
    }
    return common | by_type.get(button_type, set())


@dataclass
class Button:
    content: List[Inline] = field(default_factory=list)
    type: str = "url"
    attrs: Dict[str, str] = field(default_factory=dict)
    style: Optional[str] = None

    def to_html(self) -> str:
        attrs = [f'type="{escape(self.type, quote=True)}"']
        if self.style:
            attrs.append(f'style="{escape(self.style, quote=True)}"')
        allowed = _button_attr_names(self.type)
        attrs.extend(
            f'{name}="{escape(value, quote=True)}"'
            for name, value in self.attrs.items() if name in allowed
        )
        return f"<tg-button {' '.join(attrs)}>{_ih(self.content)}</tg-button>"


@dataclass
class BlockButtonRow:
    buttons: List[Button] = field(default_factory=list)
    align: Optional[str] = None

    def to_html(self) -> str:
        align = f' align="{escape(self.align, quote=True)}"' if self.align in {"left", "center", "right"} else ""
        return f"<tg-button-row{align}>{''.join(button.to_html() for button in self.buttons)}</tg-button-row>"

    def to_tl(self) -> dict:
        return {
            "_": "InputRichBlockButtonRow",
            "buttons": [
                {
                    "text": _it(button.content), "type": button.type,
                    "attrs": button.attrs, "style": button.style,
                }
                for button in self.buttons
            ],
            "align": self.align,
        }


Block = Union[
    BlockParagraph, BlockHeading, BlockPreformatted, BlockFooter,
    BlockDivider, BlockMath, BlockAnchor, BlockList, BlockQuotation,
    BlockPullQuotation, BlockCollage, BlockSlideshow, BlockTable,
    BlockDetails, BlockMap, BlockPhoto, BlockVideo, BlockAudio,
    BlockAnimation, BlockVoiceNote, BlockThinking, BlockButtonRow,
]

# Tags that open a block context and accept inline content.
_BLOCK_INLINE_TAGS: Dict[str, str] = {
    "p": "paragraph",
    "h1": "h1", "h2": "h2", "h3": "h3",
    "h4": "h4", "h5": "h5", "h6": "h6",
    "footer": "footer",
    "blockquote": "blockquote",
    "aside": "aside",
}

# Inline tags mapped to wrapper classes.
_INLINE_WRAP: Dict[str, Any] = {
    "b": TextBold, "strong": TextBold,
    "i": TextItalic, "em": TextItalic,
    "u": TextUnderline, "ins": TextUnderline,
    "s": TextStrike, "del": TextStrike, "strike": TextStrike,
    "tg-spoiler": TextSpoiler,
    "sub": TextSubscript,
    "sup": TextSuperscript,
    "mark": TextMarked,
}

_VOID_TAGS = frozenset({"hr", "br", "img", "tg-map", "tg-animation", "tg-voice",
                         "input"})

_MAILTO = "mailto:"
_TEL = "tel:"
_TG_USER = "tg://user?id="


class _Frame:
    """One parser stack frame."""
    __slots__ = ("kind", "tag", "attrs", "items", "extra")

    def __init__(self, kind: str, tag: str, attrs: dict,
                 extra: Optional[dict] = None):
        self.kind = kind
        self.tag = tag
        self.attrs = attrs
        self.items: List[Inline] = []   # Accumulated inline content.
        self.extra: dict = extra or {}  # Helper fields for complex blocks.

    def append_text(self, text: str) -> None:
        if not text:
            return
        if self.items and isinstance(self.items[-1], TextPlain):
            self.items[-1].text += text
        else:
            self.items.append(TextPlain(text))


class RichHTMLParser(HTMLParser):
    """Parse Telegram Rich HTML and return Block objects.

    Supports Bot API 10.1/10.2 rich block shapes.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: List[Block] = []
        self._stack: List[_Frame] = []

    def _push(self, frame: _Frame) -> None:
        if len(self._stack) < _MAX_NESTING:
            self._stack.append(frame)

    def _pop(self) -> Optional[_Frame]:
        return self._stack.pop() if self._stack else None

    def _top(self) -> Optional[_Frame]:
        return self._stack[-1] if self._stack else None

    def _inline_target(self) -> Optional[_Frame]:
        """Return the nearest frame that accepts inline content."""
        for frame in reversed(self._stack):
            if frame.kind in (
                "paragraph", "h1", "h2", "h3", "h4", "h5", "h6",
                "footer", "blockquote", "aside", "details", "li",
                "figcaption", "caption_credit", "table_caption",
                "td", "th", "summary", "thinking",
                "pre", "math_inline", "math_block", "inline_code", "button",
                "tg_emoji", "tg_time",
                # Inline frames accept text too.
                "inline",
            ):
                return frame
        return None

    def _emit(self, block: Block) -> None:
        """Append a completed block to the top level or parent frame."""
        top = self._top()
        if top and top.kind == "details":
            self._flush_parent_inline(top)
            top.extra.setdefault("blocks", []).append(block)
            return
        if top and top.kind == "li":
            self._flush_parent_inline(top)
            top.extra.setdefault("blocks", []).append(block)
            return
        if top and top.kind in ("blockquote", "aside", "td", "th"):
            # These TL shapes hold RichText rather than child PageBlocks.
            if isinstance(block, BlockParagraph):
                top.items.extend(block.content)
                return
        if top and top.kind in ("collage", "slideshow"):
            # Collage/slideshow media items are added via _handle_media_void.
            pass
        self.blocks.append(block)

    @staticmethod
    def _flush_parent_inline(frame: _Frame) -> None:
        if frame.items:
            frame.extra.setdefault("blocks", []).append(BlockParagraph(frame.items))
            frame.items = []

    def _flush_figure(self, frame: _Frame) -> Optional[Block]:
        """Build a media block from a <figure> frame."""
        media_tag = frame.extra.get("media_tag")
        src = frame.extra.get("src", "")
        spoiler = frame.extra.get("spoiler")
        cap_items = frame.extra.get("cap_items", [])
        cap_credit = frame.extra.get("cap_credit")
        caption = Caption(cap_items, cap_credit) if cap_items else None

        if media_tag == "img":
            return BlockPhoto(src, caption, spoiler)
        if media_tag == "video":
            return BlockVideo(src, caption, spoiler)
        if media_tag == "audio":
            return BlockAudio(src, caption)
        if media_tag == "tg-animation":
            return BlockAnimation(src, caption, spoiler)
        if media_tag == "tg-map":
            lat = frame.extra.get("lat", 0.0)
            long = frame.extra.get("long", 0.0)
            zoom = frame.extra.get("zoom")
            return BlockMap(lat, long, zoom, caption)
        return None


    def handle_starttag(self, tag: str, attrs: list) -> None:  # type: ignore[override]
        tag = tag.lower()
        ad = _attrs_d(attrs)

        if tag == "hr":
            self._emit(BlockDivider())
            return

        if tag == "img":
            self._handle_media_void("img", ad)
            return

        if tag == "tg-map":
            self._handle_tg_map(ad)
            return

        if tag == "tg-animation":
            self._handle_media_void("tg-animation", ad)
            return

        if tag == "tg-voice":
            src = ad.get("src", "")
            if src:
                self._emit(BlockVoiceNote(src))
            return

        if tag == "br":
            target = self._inline_target()
            if target:
                target.append_text("\n")
            return

        if tag == "input":
            # <input type="checkbox"> inside <li>.
            top = self._top()
            if top and top.kind == "li":
                checked = "checked" in ad or _truthy(ad.get("checked")) is True
                top.extra["checkbox"] = checked
            return

        if tag in _BLOCK_INLINE_TAGS:
            kind = _BLOCK_INLINE_TAGS[tag]
            extra: dict = {}
            if tag == "blockquote":
                exp_raw = ad.get("expandable")
                extra["expandable"] = _truthy(exp_raw) if exp_raw is not None else None
            self._push(_Frame(kind, tag, ad, extra))
            return

        if tag == "pre":
            self._push(_Frame("pre", "pre", ad))
            return

        if tag == "tg-math-block":
            self._push(_Frame("math_block", "tg-math-block", ad))
            return

        if tag == "tg-thinking":
            self._push(_Frame("thinking", "tg-thinking", ad))
            return

        if tag == "tg-button-row":
            align = ad.get("align", "").lower()
            self._push(_Frame("button_row", tag, ad, {
                "align": align if align in ("left", "center", "right") else None,
                "buttons": [],
            }))
            return

        if tag == "tg-button":
            row = self._top()
            if row and row.kind == "button_row":
                button_type = ad.get("type", "url").lower()
                self._push(_Frame("button", tag, ad, {
                    "type": button_type,
                    "attrs": {name: value for name, value in ad.items()
                              if name in _button_attr_names(button_type)},
                    "style": ad.get("style"),
                }))
            return

        if tag == "figure":
            self._push(_Frame("figure", "figure", ad, {
                "media_tag": None, "src": "", "spoiler": None,
                "cap_items": [], "cap_credit": None,
            }))
            return

        if tag == "figcaption":
            top = self._top()
            if top and top.kind == "figure":
                self._push(_Frame("figcaption", "figcaption", ad))
            return

        if tag == "cite":
            top = self._top()
            if top and top.kind in ("blockquote", "aside", "figcaption"):
                self._push(_Frame("caption_credit", "cite", ad))
            else:
                # Treat cite as inline in regular text.
                self._push(_Frame("inline", "cite", ad, {"wrap": None}))
            return

        if tag == "details":
            open_ = "open" in ad or _truthy(ad.get("open")) is True
            self._push(_Frame("details", "details", ad, {
                "title": ad.get("title"), "open": open_, "blocks": [],
            }))
            return

        if tag == "summary":
            top = self._top()
            if top and top.kind == "details":
                self._push(_Frame("summary", "summary", ad))
            return

        if tag in ("ul", "ol"):
            ordered = tag == "ol"
            start = _bounded_int(ad.get("start"), _INT32_MIN, _INT32_MAX)
            rev = "reversed" in ad
            self._push(_Frame("list", tag, ad, {
                "ordered": ordered, "start": start, "reversed": rev,
                "type": ad.get("type"), "items": [],
            }))
            return

        if tag == "li":
            top = self._top()
            value = _bounded_int(ad.get("value"), _INT32_MIN, _INT32_MAX)
            self._push(_Frame("li", "li", ad, {
                "value": value, "type": ad.get("type"), "checkbox": None, "blocks": [],
                "num": ad.get("data-num", ad.get("num")),
            }))
            return

        if tag == "table":
            bordered = "bordered" in ad or _truthy(ad.get("bordered")) is True
            striped = "striped" in ad or _truthy(ad.get("striped")) is True
            compact = "compact" in ad or _truthy(ad.get("compact")) is True
            self._push(_Frame("table", "table", ad, {
                "title": None, "bordered": bordered if bordered else None,
                "striped": striped if striped else None,
                "compact": compact if compact else None, "rows": [],
            }))
            return

        if tag == "caption":
            top = self._top()
            if top and top.kind == "table":
                self._push(_Frame("table_caption", "caption", ad))
            return

        if tag == "tr":
            self._push(_Frame("tr", "tr", ad, {"cells": []}))
            return

        if tag in ("td", "th"):
            align = ad.get("align")
            valign = ad.get("valign")
            colspan = _bounded_int(ad.get("colspan"), _INT32_MIN, _INT32_MAX)
            rowspan = _bounded_int(ad.get("rowspan"), _INT32_MIN, _INT32_MAX)
            self._push(_Frame(tag, tag, ad, {
                "align": align, "valign": valign, "colspan": colspan, "rowspan": rowspan,
                "is_header": tag == "th",
            }))
            return

        if tag == "tg-collage":
            self._push(_Frame("collage", "tg-collage", ad, {
                "items": [], "cap_items": [], "cap_credit": None,
            }))
            return

        if tag == "tg-slideshow":
            self._push(_Frame("slideshow", "tg-slideshow", ad, {
                "items": [], "cap_items": [], "cap_credit": None,
            }))
            return

        if tag in _INLINE_WRAP:
            self._push(_Frame("inline", tag, ad, {"wrap": _INLINE_WRAP[tag]}))
            return

        if tag == "code":
            # Inside <pre>, collect language; outside it becomes TextCode.
            pre = self._top()
            if pre and pre.kind == "pre":
                lang = ad.get("class", "")
                if lang.startswith("language-"):
                    lang = lang[9:]
                pre.extra["language"] = lang or None
            else:
                self._push(_Frame("inline_code", "code", ad))
            return

        if tag == "a":
            href = ad.get("href", "")
            if not href:
                # block-level anchor
                name = ad.get("name", "")
                if name:
                    self._push(_Frame("anchor_block", "a", ad, {"name": name}))
                else:
                    self._push(_Frame("inline", "a", ad, {"wrap": None}))
                return
            href = _safe_href(href)
            if href is None:
                self._push(_Frame("inline", "a", ad, {"wrap": None}))
                return
            if href.startswith("#"):
                self._push(_Frame("inline", "a", ad, {
                    "wrap": TextAnchorLink, "href": href[1:],
                }))
            elif href.startswith(_MAILTO):
                self._push(_Frame("inline", "a", ad, {
                    "wrap": TextEmail, "href": href[len(_MAILTO):],
                }))
            elif href.startswith(_TEL):
                self._push(_Frame("inline", "a", ad, {
                    "wrap": TextPhone, "href": href[len(_TEL):],
                }))
            elif href.startswith(_TG_USER):
                uid_s = href[len(_TG_USER):]
                try:
                    uid = int(uid_s)
                except ValueError:
                    uid = 0
                self._push(_Frame("inline", "a", ad, {
                    "wrap": TextMention, "user_id": uid,
                }))
            else:
                self._push(_Frame("inline", "a", ad, {
                    "wrap": TextUrl, "href": href,
                }))
            return

        if tag == "tg-emoji":
            eid = ad.get("emoji-id", "")
            if _bounded_int(eid, _INT64_MIN, _INT64_MAX) is not None:
                # tg-emoji contains alt text, so open a frame.
                self._push(_Frame("tg_emoji", "tg-emoji", ad, {"emoji_id": eid}))
            return

        if tag == "tg-time":
            unix = _int_attr(ad.get("unix"), 0)
            fmt = ad.get("format")
            self._push(_Frame("tg_time", "tg-time", ad, {
                "unix": unix, "format": fmt,
            }))
            return

        if tag == "tg-math":
            self._push(_Frame("math_inline", "tg-math", ad))
            return

        if tag == "tg-reference":
            name = ad.get("name", "")
            self._push(_Frame("inline", "tg-reference", ad, {
                "wrap": TextReference, "ref_name": name,
            }))
            return

        # span with class="tg-spoiler".
        if tag == "span":
            cls = ad.get("class", "")
            if "tg-spoiler" in cls.split():
                self._push(_Frame("inline", "span", ad, {"wrap": TextSpoiler}))
            # Otherwise ignore span as a transparent container.
            return

        # Unknown tags are ignored.

    def handle_startendtag(self, tag: str, attrs: list) -> None:  # type: ignore[override]
        """Handle self-closing tags."""
        self.handle_starttag(tag, attrs)
        if tag.lower() not in _VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        tag = tag.lower()

        # Find the matching frame in the stack from top to bottom.
        idx = None
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i].tag == tag:
                idx = i
                break
        if idx is None:
            return

        # Close all nested frames up to the matching one.
        while len(self._stack) > idx + 1:
            self._close_top()

        self._close_top()

    def _close_top(self) -> None:
        """Close the top stack frame and emit its result."""
        frame = self._pop()
        if frame is None:
            return

        kind = frame.kind

        if kind == "inline":
            wrap = frame.extra.get("wrap")
            target = self._inline_target()
            if target is None:
                return

            if wrap is None:
                # Transparent container: move items directly.
                target.items.extend(frame.items)
                return

            if wrap == TextUrl:
                node: Inline = TextUrl(frame.extra["href"], frame.items)
            elif wrap == TextMention:
                node = TextMention(frame.extra.get("user_id", 0), frame.items)
            elif wrap == TextEmail:
                node = TextEmail(frame.extra["href"], frame.items)
            elif wrap == TextPhone:
                node = TextPhone(frame.extra["href"], frame.items)
            elif wrap == TextAnchorLink:
                node = TextAnchorLink(frame.extra["href"], frame.items)
            elif wrap == TextReference:
                node = TextReference(frame.extra.get("ref_name", ""), frame.items)
            else:
                # TextBold, TextItalic, TextSpoiler, etc.
                node = wrap(frame.items)

            target.items.append(node)
            return

        if kind == "inline_code":
            text = _inline_plain(frame.items)
            target = self._inline_target()
            if target:
                target.items.append(TextCode(text))
            return

        if kind == "button":
            row = self._top()
            if row and row.kind == "button_row":
                attrs = dict(frame.extra["attrs"])
                attrs.pop("type", None)
                attrs.pop("style", None)
                row.extra["buttons"].append(Button(
                    frame.items, frame.extra["type"], attrs, frame.extra["style"]
                ))
            return

        if kind == "button_row":
            self._emit(BlockButtonRow(frame.extra["buttons"], frame.extra["align"]))
            return

        if kind == "tg_emoji":
            text = _inline_plain(frame.items) or " "
            target = self._inline_target()
            if target:
                target.items.append(TextEmoji(frame.extra["emoji_id"], text))
            return

        if kind == "tg_time":
            text = _inline_plain(frame.items)
            target = self._inline_target()
            if target:
                target.items.append(TextDateTime(
                    frame.extra["unix"], frame.extra.get("format"), text
                ))
            return

        if kind == "math_inline":
            text = _inline_plain(frame.items)
            target = self._inline_target()
            if target:
                target.items.append(TextMathInline(text))
            return

        if kind in ("paragraph",):
            self._emit(BlockParagraph(frame.items))
            return

        if kind in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(kind[1])
            self._emit(BlockHeading(level, frame.items))
            return

        if kind == "footer":
            self._emit(BlockFooter(frame.items))
            return

        if kind == "blockquote":
            exp = frame.extra.get("expandable")
            author = frame.extra.get("author_items")
            self._emit(BlockQuotation(frame.items, author, exp))
            return

        if kind == "aside":
            author = frame.extra.get("author_items")
            self._emit(BlockPullQuotation(frame.items, author))
            return

        if kind == "caption_credit":
            parent = self._top()
            if parent is None:
                return
            if parent.kind in ("blockquote", "aside"):
                parent.extra["author_items"] = frame.items
            elif parent.kind == "figcaption":
                parent.extra["credit_items"] = frame.items
            elif parent.kind in ("collage", "slideshow"):
                parent.extra["cap_credit"] = frame.items
            return

        if kind == "pre":
            text = _inline_plain(frame.items)
            lang = frame.extra.get("language")
            self._emit(BlockPreformatted(text, lang))
            return

        if kind == "math_block":
            text = _inline_plain(frame.items)
            self._emit(BlockMath(text))
            return

        if kind == "thinking":
            text = _inline_plain(frame.items)
            self._emit(BlockThinking(text))
            return

        if kind == "anchor_block":
            text = _inline_plain(frame.items)
            self._emit(BlockAnchor(frame.extra["name"], text))
            return

        if kind == "summary":
            title_text = _inline_plain(frame.items)
            parent = self._top()
            if parent and parent.kind == "details":
                parent.extra["title"] = title_text
            return

        if kind == "details":
            self._flush_parent_inline(frame)
            title = frame.extra.get("title", "")
            open_ = frame.extra.get("open", None)
            self._emit(BlockDetails(title or "", frame.extra.get("blocks", []), open_ or None))
            return

        if kind == "figcaption":
            parent = self._top()
            if parent is None:
                return
            credit = frame.extra.get("credit_items")
            if parent.kind == "figure":
                parent.extra["cap_items"] = frame.items
                parent.extra["cap_credit"] = credit
            elif parent.kind in ("collage", "slideshow"):
                parent.extra["cap_items"] = frame.items
                parent.extra["cap_credit"] = credit
            return

        if kind == "figure":
            block = self._flush_figure(frame)
            if block:
                self._emit(block)
            return

        if kind == "table_caption":
            title_text = _inline_plain(frame.items)
            parent = self._top()
            if parent and parent.kind == "table":
                parent.extra["title"] = title_text
            return

        if kind in ("td", "th"):
            cell = TableCell(
                content=frame.items,
                align=frame.extra.get("align"),
                valign=frame.extra.get("valign"),
                is_header=frame.extra.get("is_header", False),
                colspan=frame.extra.get("colspan"),
                rowspan=frame.extra.get("rowspan"),
            )
            parent = self._top()
            if parent and parent.kind == "tr":
                parent.extra["cells"].append(cell)
            return

        if kind == "tr":
            row = TableRow(frame.extra.get("cells", []))
            parent = self._top()
            if parent and parent.kind == "table":
                parent.extra["rows"].append(row)
            return

        if kind == "table":
            self._emit(BlockTable(
                rows=frame.extra.get("rows", []),
                title=frame.extra.get("title"),
                bordered=frame.extra.get("bordered"),
                striped=frame.extra.get("striped"),
                compact=frame.extra.get("compact"),
            ))
            return

        if kind == "li":
            if frame.extra.get("blocks"):
                self._flush_parent_inline(frame)
            item = ListItem(
                content=frame.items,
                blocks=frame.extra.get("blocks", []),
                checkbox=frame.extra.get("checkbox"),
                value=frame.extra.get("value"),
                num=frame.extra.get("num"),
                type=frame.extra.get("type"),
            )
            parent = self._top()
            if parent and parent.kind == "list":
                parent.extra["items"].append(item)
            return

        if kind == "list":
            self._emit(BlockList(
                ordered=frame.extra.get("ordered", False),
                items=frame.extra.get("items", []),
                start=frame.extra.get("start"),
                reversed_=frame.extra.get("reversed", False),
                type=frame.extra.get("type"),
            ))
            return

        if kind in ("collage", "slideshow"):
            cap_items = frame.extra.get("cap_items", [])
            cap_credit = frame.extra.get("cap_credit")
            caption = Caption(cap_items, cap_credit) if cap_items else None
            items = frame.extra.get("items", [])
            if kind == "collage":
                self._emit(BlockCollage(items, caption))
            else:
                self._emit(BlockSlideshow(items, caption))
            return

    def _handle_media_void(self, tag: str, ad: dict) -> None:
        """Handle media tags: img, tg-animation, etc."""
        src = ad.get("src", "")
        spoiler = _truthy(ad.get("tg-spoiler")) or ("tg-spoiler" in ad)

        top = self._top()

        if top and top.kind == "figure":
            top.extra["media_tag"] = tag
            top.extra["src"] = src
            top.extra["spoiler"] = spoiler or None
            return

        if top and top.kind in ("collage", "slideshow"):
            top.extra["items"].append(MediaItem(src, spoiler or None))
            return

        # Standalone media.
        if tag == "img":
            self._emit(BlockPhoto(src, None, spoiler or None))
        elif tag == "tg-animation":
            self._emit(BlockAnimation(src, None, spoiler or None))

    def _handle_tg_map(self, ad: dict) -> None:
        top = self._top()
        lat = _float_attr(ad.get("lat")) or 0.0
        long_ = _float_attr(ad.get("long")) or 0.0
        zoom = _int_attr(ad.get("zoom"))

        if top and top.kind == "figure":
            top.extra["media_tag"] = "tg-map"
            top.extra["src"] = ""
            top.extra["lat"] = lat
            top.extra["long"] = long_
            top.extra["zoom"] = zoom
            return

        self._emit(BlockMap(lat, long_, zoom))

    def handle_data(self, data: str) -> None:  # type: ignore[override]
        target = self._inline_target()
        if target:
            target.append_text(data)

    def close(self) -> None:
        super().close()
        while self._stack:
            self._close_top()

def parse_rich_html(html: str) -> List[Block]:
    """Parse a Rich HTML string into Block objects.

    Example::

        blocks = parse_rich_html("<h1>Hello</h1><p>Text <b>bold</b></p>")
        tl_blocks = [b.to_tl() for b in blocks]
    """
    if not html:
        return []
    parser = RichHTMLParser()
    parser.feed(html)
    parser.close()
    return parser.blocks


def render_rich_html(blocks: List[Block]) -> str:
    """Serialize Block objects back into a Rich HTML string."""
    return "".join(b.to_html() for b in blocks)


def blocks_to_tl(blocks: List[Block]) -> List[dict]:
    """Convert Block objects into parser TL dictionaries."""
    return [b.to_tl() for b in blocks]


# Fast path: HTML → parser TL dictionaries in one call.
def html_to_input_blocks(html: str) -> List[dict]:
    """HTML → parser InputRichBlock* dictionaries."""
    blocks = parse_rich_html(html)
    _validate_rich_blocks(blocks)
    return blocks_to_tl(blocks)


def _tl_text(value: Any):
    if value is None:
        return types.TextEmpty()
    if isinstance(value, str):
        return types.TextPlain(value) if value else types.TextEmpty()
    if not isinstance(value, dict):
        return value

    kind = value.get("_")
    if kind in ("RichTextEmpty", "TextEmpty"):
        return types.TextEmpty()
    if kind in ("RichTextPlain", "TextPlain"):
        return types.TextPlain(value.get("text", ""))
    if kind in ("RichTextConcat", "TextConcat"):
        return types.TextConcat([_tl_text(item) for item in value.get("texts", [])])

    wrappers = {
        "RichTextBold": types.TextBold,
        "RichTextItalic": types.TextItalic,
        "RichTextUnderline": types.TextUnderline,
        "RichTextStrikethrough": types.TextStrike,
        "RichTextSpoiler": types.TextSpoiler,
        "RichTextSubscript": types.TextSubscript,
        "RichTextSuperscript": types.TextSuperscript,
        "RichTextMarked": types.TextMarked,
    }
    if kind in wrappers:
        return wrappers[kind](_tl_text(value.get("text")))

    if kind == "RichTextCode":
        return types.TextFixed(types.TextPlain(value.get("text", "")))
    if kind == "RichTextUrl":
        return types.TextUrl(
            _tl_text(value.get("text")),
            value.get("url", ""),
            int(value.get("webpage_id") or 0),
        )
    if kind == "RichTextEmailAddress":
        return types.TextEmail(_tl_text(value.get("text")), value.get("email", ""))
    if kind == "RichTextPhoneNumber":
        return types.TextPhone(_tl_text(value.get("text")), value.get("phone_number", ""))
    if kind == "RichTextCustomEmoji":
        return types.TextCustomEmoji(
            int(value.get("document_id") or 0),
            value.get("text") or value.get("alt") or " ",
        )
    if kind == "RichTextMathematicalExpression":
        return types.TextMath(value.get("expression", ""))
    if kind == "RichTextAnchorLink":
        return types.TextUrl(_tl_text(value.get("text")), value.get("url") or f"#{value.get('anchor', '')}", 0)
    if kind == "RichTextReference":
        return types.TextUrl(_tl_text(value.get("text")), f"#{value.get('anchor', '')}", 0)
    if kind == "RichTextMention":
        return types.TextUrl(_tl_text(value.get("text")), f"tg://user?id={value.get('user_id', 0)}", 0)
    if kind == "RichTextDateTime":
        return types.TextPlain(value.get("text", ""))

    return types.TextPlain(str(value))


def _tl_caption(value: Any):
    if not isinstance(value, dict):
        return types.PageCaption(_tl_text(value), types.TextEmpty())
    return types.PageCaption(
        _tl_text(value.get("text")),
        _tl_text(value.get("credit")),
    )


def _tl_list_item(value: dict, ordered: bool = False):
    blocks = value.get("blocks")
    if blocks:
        content = _tl_text(value.get("text"))
        rendered_blocks = [_tl_block(block) for block in blocks]
        if content.__class__.__name__ != "TextEmpty":
            rendered_blocks.insert(0, types.PageBlockParagraph(content))
        return types.PageListItemBlocks(
            rendered_blocks,
            checkbox=value.get("checkbox"), checked=value.get("checked"),
        )
    text = _tl_text(value.get("text"))
    checkbox = value.get("checkbox")
    checked = value.get("checked")
    if ordered:
        num = value.get("num")
        return types.PageListOrderedItemText(
            text,
            checkbox=checkbox,
            checked=checked,
            num=str(num) if num is not None else None,
            value=value.get("value"),
            type=value.get("type"),
        )
    return types.PageListItemText(text, checkbox=checkbox, checked=checked)


def _tl_table_cell(value: dict):
    align = (value.get("align") or "").lower()
    valign = (value.get("valign") or "").lower()
    return types.PageTableCell(
        header=value.get("header"),
        align_center=True if align == "center" else None,
        align_right=True if align == "right" else None,
        valign_middle=True if valign == "middle" else None,
        valign_bottom=True if valign == "bottom" else None,
        text=_tl_text(value.get("text")),
        colspan=value.get("colspan"),
        rowspan=value.get("rowspan"),
    )


def _tl_table_row(value: dict):
    return types.PageTableRow([_tl_table_cell(cell) for cell in value.get("cells", [])])


def _button_url(attrs: dict) -> str:
    url = _safe_href(attrs.get("url", ""))
    if url is None:
        raise ValueError("button URL must use a safe scheme")
    return url


def _tl_button(value: dict):
    attrs = value.get("attrs", {})
    button_type = value.get("type", "url")
    if button_type == "url":
        button = types.InlineButtonTypeUrl(_button_url(attrs))
    elif button_type == "web_app":
        button = types.InlineButtonTypeWebView(_button_url(attrs))
    elif button_type == "callback_data":
        encoded = attrs.get("data-base64")
        if encoded is not None:
            try:
                # Compatibility attribute for callback bytes that are not UTF-8.
                data = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError, TypeError):
                data = attrs.get("data", "").encode("utf-8")
        else:
            data = attrs.get("data", "").encode("utf-8")
        if not 1 <= len(data) <= 64:
            raise ValueError("callback_data must contain 1 to 64 bytes")
        button = types.InlineButtonTypeCallback(
            data, requires_password=_truthy(attrs.get("requires-password"))
        )
    elif button_type == "login_url":
        button = types.InlineButtonTypeUrlAuth(
            _button_url(attrs), _bounded_int(attrs.get("button-id"), _INT32_MIN, _INT32_MAX) or 0,
            attrs.get("forward-text", attrs.get("fwd-text")),
        )
    elif button_type in ("switch_inline_query", "switch_inline_query_current_chat"):
        button = types.InlineButtonTypeSwitchInline(
            attrs.get("query", ""), same_peer=button_type.endswith("current_chat")
        )
    elif button_type == "switch_inline_query_chosen_chat":
        peer_types = []
        for attr, peer_type in (
            ("allow-user-chats", types.InlineQueryPeerTypePM),
            ("allow-bot-chats", types.InlineQueryPeerTypeBotPM),
            ("allow-group-chats", types.InlineQueryPeerTypeChat),
            ("allow-channel-chats", types.InlineQueryPeerTypeBroadcast),
        ):
            if _truthy(attrs.get(attr)):
                peer_types.append(peer_type())
        button = types.InlineButtonTypeSwitchInline(attrs.get("query", ""), peer_types=peer_types)
    elif button_type == "copy_text":
        button = types.InlineButtonTypeCopy(attrs.get("text", attrs.get("copy-text", "")))
    elif button_type == "disabled":
        button = types.InlineButtonTypeDisabled()
    elif button_type == "game":
        button = types.InlineButtonTypeGame()
    elif button_type == "buy":
        button = types.InlineButtonTypeBuy()
    elif button_type == "user_profile":
        button = types.InlineButtonTypeUserProfile(
            _bounded_int(attrs.get("user-id"), _INT64_MIN, _INT64_MAX) or 0
        )
    else:
        button = types.InlineButtonTypeUrl(attrs.get("url", ""))

    style_name = value.get("style")
    styles = {
        "primary": {"bg_primary": True}, "danger": {"bg_danger": True},
        "success": {"bg_success": True}, "link": {"link": True},
    }
    style = types.RichButtonStyle(**styles[style_name]) if style_name in styles else None
    return types.PageButton(_tl_text(value.get("text")), button, style)


def _tl_block(value: Any):
    if not isinstance(value, dict):
        return value

    kind = value.get("_")
    if kind == "InputRichBlockParagraph":
        return types.PageBlockParagraph(_tl_text(value.get("text")))
    if kind == "InputRichBlockSectionHeading":
        level = max(1, min(6, int(value.get("level") or 1)))
        return getattr(types, f"PageBlockHeading{level}")(_tl_text(value.get("text")))
    if kind == "InputRichBlockPreformatted":
        return types.PageBlockPreformatted(
            types.TextPlain(value.get("text", "")),
            value.get("language") or "",
        )
    if kind == "InputRichBlockFooter":
        return types.PageBlockFooter(_tl_text(value.get("text")))
    if kind == "InputRichBlockDivider":
        return types.PageBlockDivider()
    if kind == "InputRichBlockMathematicalExpression":
        return types.PageBlockMath(value.get("expression", ""))
    if kind == "InputRichBlockAnchor":
        return types.PageBlockAnchor(value.get("name", ""))
    if kind == "InputRichBlockDetails":
        return types.PageBlockDetails(
            [_tl_block(block) for block in value.get("blocks", [])],
            _tl_text(value.get("title", "")),
            open=value.get("open"),
        )
    if kind == "InputRichBlockList":
        ordered = bool(value.get("ordered"))
        items = [_tl_list_item(item, ordered=ordered) for item in value.get("items", [])]
        if ordered:
            return types.PageBlockOrderedList(
                items,
                reversed=value.get("reversed"),
                start=value.get("start"),
                type=value.get("type"),
            )
        return types.PageBlockList(items)
    if kind == "InputRichBlockBlockQuotation":
        return types.PageBlockBlockquote(
            _tl_text(value.get("text")),
            _tl_text(value.get("author")),
        )
    if kind == "InputRichBlockPullQuotation":
        return types.PageBlockPullquote(
            _tl_text(value.get("text")),
            _tl_text(value.get("author")),
        )
    if kind == "InputRichBlockTable":
        return types.PageBlockTable(
            _tl_text(value.get("title")),
            [_tl_table_row(row) for row in value.get("rows", [])],
            bordered=value.get("bordered"),
            striped=value.get("striped"),
            compact=value.get("compact"),
        )
    if kind == "InputRichBlockButtonRow":
        align = value.get("align")
        return types.PageBlockButtonRow(
            [_tl_button(button) for button in value.get("buttons", [])],
            align_left=True if align == "left" else None,
            align_center=True if align == "center" else None,
            align_right=True if align == "right" else None,
        )
    if kind == "InputRichBlockThinking":
        return types.PageBlockThinking(_tl_text(value.get("text")))

    # Media source references need file mapping to concrete Telegram media ids.
    return types.PageBlockUnsupported()


def html_to_tl_blocks(html: str):
    """Parse Rich HTML into real Telethon PageBlock TL objects."""
    blocks = parse_rich_html(html)
    _validate_rich_blocks(blocks)
    return [_tl_block(block) for block in blocks_to_tl(blocks)]


def _validate_rich_blocks(blocks: list[Block]) -> None:
    """Validate nested Rich blocks without recursing through rich-text metadata."""
    pending = [(block, 0) for block in reversed(blocks)]
    seen = set()
    count = 0
    while pending:
        block, depth = pending.pop()
        if id(block) in seen:
            raise ValueError("rich message block graph contains a cycle")
        seen.add(id(block))
        if depth > _MAX_NESTING:
            raise ValueError("rich message block nesting exceeds 100 levels")
        count += 1
        if count > 100:
            raise ValueError("rich message cannot contain more than 100 blocks")

        name = block.__class__.__name__
        if isinstance(block, BlockButtonRow) or name == "PageBlockButtonRow":
            if not 1 <= len(getattr(block, "buttons", ()) or ()) <= 8:
                raise ValueError("tg-button-row must contain 1 to 8 buttons")

        children = []
        if isinstance(block, BlockDetails) or name == "PageBlockDetails":
            children.extend(getattr(block, "blocks", ()) or ())
        elif isinstance(block, BlockList) or name in {"PageBlockList", "PageBlockOrderedList"}:
            for item in getattr(block, "items", ()) or ():
                children.extend(getattr(item, "blocks", ()) or ())
        elif isinstance(block, (BlockCollage, BlockSlideshow)) or name in {"PageBlockCollage", "PageBlockSlideshow"}:
            children.extend(getattr(block, "items", ()) or ())
        elif name == "PageBlockCover":
            cover = getattr(block, "cover", None)
            if cover is not None:
                children.append(cover)
        pending.extend((child, depth + 1) for child in reversed(children))


def validate_rich_message(rich_message: object) -> None:
    """Validate prebuilt InputRichMessage/RichMessage block limits."""
    _validate_rich_blocks(list(getattr(rich_message, "blocks", ()) or ()))


def html_to_input_rich_message(
    html: str,
    *,
    rtl: Optional[bool] = None,
    noautolink: Optional[bool] = None,
    photos=None,
    documents=None,
    users=None,
):
    """Parse Rich HTML into a real ``types.InputRichMessage`` instance."""
    return types.InputRichMessage(
        html_to_tl_blocks(html),
        rtl=rtl,
        noautolink=noautolink,
        photos=photos,
        documents=documents,
        users=users,
    )


# Received RichMessage rendering helpers.
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


def _render_text_link(href: object, text: object, depth: int = 0) -> str:
    visible = _render_text_node(text, depth + 1)
    safe_href = _safe_href(href)
    return '<a href="{}">{}</a>'.format(_escape_html(safe_href), visible) if safe_href else visible


def _render_text_node(node: object, depth: int = 0) -> str:
    if node is None or depth >= _MAX_NESTING:
        return ""

    try:
        node_type = node.__class__.__name__

        if node_type == "TextEmpty":
            return ""
        if node_type == "TextPlain":
            return _escape_html(getattr(node, "text", ""))
        if node_type == "TextConcat":
            texts = getattr(node, "texts", None) or ()
            return "".join(_render_text_node(child, depth + 1) for child in texts)

        tag_by_type = {
            "TextBold": ("b", "b"),
            "TextItalic": ("i", "i"),
            "TextUnderline": ("u", "u"),
            "TextStrike": ("s", "s"),
            "TextFixed": ("code", "code"),
            "TextSubscript": ("sub", "sub"),
            "TextSuperscript": ("sup", "sup"),
            "TextMarked": ("mark", "mark"),
            "TextSpoiler": ("tg-spoiler", "tg-spoiler"),
        }
        if node_type in tag_by_type:
            start_tag, end_tag = tag_by_type[node_type]
            return f"<{start_tag}>{_render_text_node(getattr(node, 'text', None), depth + 1)}</{end_tag}>"

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
            return _render_text_node(getattr(node, "text", None), depth + 1)

        if node_type == "TextMath":
            return '<tg-math>{}</tg-math>'.format(_escape_html(getattr(node, "source", "")))
        if node_type == "TextCustomEmoji":
            document_id = _escape_html(getattr(node, "document_id", ""))
            alt = _escape_html(getattr(node, "alt", ""))
            return '<tg-emoji emoji-id="{}">{}</tg-emoji>'.format(document_id, alt)
        if node_type == "TextUrl":
            return _render_text_link(getattr(node, "url", ""), getattr(node, "text", None), depth)
        if node_type == "TextEmail":
            return _render_text_link(
                "mailto:{}".format(getattr(node, "email", "")),
                getattr(node, "text", None), depth,
            )
        if node_type == "TextPhone":
            return _render_text_link(
                "tel:{}".format(getattr(node, "phone", "")),
                getattr(node, "text", None), depth,
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
    return "<pre><code{}>{}</code></pre>".format(class_attr, _render_code_content(text))


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


def _render_media_block(block: object, label: str, id_attr: str = None, scheme: str = None) -> str:
    rendered_label = label
    url = getattr(block, "url", None)
    if not url and id_attr and scheme:
        media_id = getattr(block, id_attr, None)
        if media_id is not None:
            url = "tg://{}?id={}".format(scheme, media_id)

    if url:
        rendered_label = _render_block_link(label, url)
    else:
        rendered_label = _escape_html(label)

    if getattr(block, "spoiler", False):
        rendered_label = "<tg-spoiler>{}</tg-spoiler>".format(rendered_label)

    return _render_labeled_block(rendered_label, getattr(block, "caption", None))


def _render_block_link(label: str, url: object) -> str:
    safe_url = _safe_href(url)
    if not safe_url:
        return _escape_html(label)
    return '<a href="{}">{}</a>'.format(_escape_html(safe_url), _escape_html(label))


def _render_table(block: object) -> str:
    try:
        attrs = ""
        for name in ("bordered", "striped", "compact"):
            if getattr(block, name, False):
                attrs += " " + name
        title = _render_text_node(getattr(block, "title", None))
        rows = []
        for row in getattr(block, "rows", None) or ():
            cells = []
            for cell in getattr(row, "cells", None) or ():
                tag = "th" if getattr(cell, "header", False) else "td"
                cell_attrs = ""
                if getattr(cell, "align_center", False):
                    cell_attrs += ' align="center"'
                elif getattr(cell, "align_right", False):
                    cell_attrs += ' align="right"'
                if getattr(cell, "valign_middle", False):
                    cell_attrs += ' valign="middle"'
                elif getattr(cell, "valign_bottom", False):
                    cell_attrs += ' valign="bottom"'
                for name in ("colspan", "rowspan"):
                    value = getattr(cell, name, None)
                    if value and value > 1:
                        cell_attrs += f' {name}="{value}"'
                cells.append("<{}{}>{}</{}>".format(
                    tag, cell_attrs, _render_text_node(getattr(cell, "text", None)), tag
                ))
            if cells:
                rows.append("<tr>{}</tr>".format("".join(cells)))
        caption = f"<caption>{title}</caption>" if title else ""
        return f"<table{attrs}>{caption}{''.join(rows)}</table>" if rows or caption else ""
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
        prefix = ""
        if getattr(item, "checkbox", False):
            prefix = '<input type="checkbox"{}>'.format(
                " checked" if getattr(item, "checked", False) else ""
            )

        if item.__class__.__name__.startswith("Text"):
            return prefix + _render_text_node(item)
        if isinstance(item, str):
            return prefix + _escape_html(item)
        if hasattr(item, "text"):
            return prefix + _render_text_node(getattr(item, "text", None))

        blocks = getattr(item, "blocks", None)
        if blocks:
            return prefix + "".join(_render_block(block) for block in blocks)

        return (prefix + _render_text_node(item).strip()).strip()
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

        items_html = []
        for index, item in enumerate(items):
            content = _render_list_item(item)
            if content:
                value = getattr(item, "value", None)
                value_attr = f' value="{_escape_html(value)}"' if value is not None else ""
                num = getattr(item, "num", None)
                num_attr = f' data-num="{_escape_html(num)}"' if num is not None else ""
                item_type = getattr(item, "type", None)
                type_attr = f' type="{_escape_html(item_type)}"' if item_type else ""
                items_html.append(f"<li{value_attr}{num_attr}{type_attr}>{content}</li>")
        tag = "ol" if is_ordered else "ul"
        attrs = f' start="{start}"' if is_ordered and start != 1 else ""
        if is_ordered and getattr(block, "reversed", False):
            attrs += " reversed"
        list_type = getattr(block, "type", None)
        if is_ordered and list_type:
            attrs += f' type="{_escape_html(list_type)}"'
        return f"<{tag}{attrs}>{''.join(items_html)}</{tag}>" if items_html else ""
    except Exception:
        return ""


def _render_button(button: object) -> str:
    button_type = getattr(button, "type", None)
    type_name = button_type.__class__.__name__ if button_type else ""
    attrs = []
    mapping = {
        "InlineButtonTypeUrl": ("url", ("url",)),
        "InlineButtonTypeWebView": ("web_app", ("url",)),
        "InlineButtonTypeCopy": ("copy_text", ("copy_text",)),
        "InlineButtonTypeDisabled": ("disabled", ()),
        "InlineButtonTypeGame": ("game", ()),
        "InlineButtonTypeBuy": ("buy", ()),
        "InlineButtonTypeUserProfile": ("user_profile", ("user_id",)),
    }
    if type_name in {"InlineButtonTypeUrl", "InlineButtonTypeWebView", "InlineButtonTypeUrlAuth"}:
        if _safe_href(getattr(button_type, "url", "")) is None:
            return '<tg-button type="disabled">{}</tg-button>'.format(
                _render_text_node(getattr(button, "text", None))
            )
    if type_name == "InlineButtonTypeCallback":
        attrs.append('type="callback_data"')
        data = getattr(button_type, "data", b"")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = None
        if text is not None and not any(ord(char) < 32 or ord(char) == 127 for char in text):
            attrs.append(f'data="{_escape_html(text)}"')
        else:
            encoded = base64.b64encode(data).decode("ascii")
            attrs.append(f'data-base64="{encoded}"')
        if getattr(button_type, "requires_password", False):
            attrs.append('requires-password="true"')
    elif type_name == "InlineButtonTypeUrlAuth":
        attrs.append('type="login_url"')
        attrs.append(f'url="{_escape_html(getattr(button_type, "url", ""))}"')
        attrs.append(f'button-id="{_escape_html(getattr(button_type, "button_id", 0))}"')
        fwd_text = getattr(button_type, "fwd_text", None)
        if fwd_text is not None:
            attrs.append(f'forward-text="{_escape_html(fwd_text)}"')
    elif type_name == "InlineButtonTypeSwitchInline":
        same_peer = getattr(button_type, "same_peer", False)
        peer_types = getattr(button_type, "peer_types", None) or ()
        if peer_types:
            attrs.append('type="switch_inline_query_chosen_chat"')
            peer_attrs = {
                "InlineQueryPeerTypePM": "allow-user-chats",
                "InlineQueryPeerTypeBotPM": "allow-bot-chats",
                "InlineQueryPeerTypeChat": "allow-group-chats",
                "InlineQueryPeerTypeMegagroup": "allow-group-chats",
                "InlineQueryPeerTypeBroadcast": "allow-channel-chats",
            }
            attrs.extend(peer_attrs[peer.__class__.__name__] for peer in peer_types
                         if peer.__class__.__name__ in peer_attrs)
        else:
            attrs.append('type="switch_inline_query_current_chat"' if same_peer else 'type="switch_inline_query"')
        attrs.append(f'query="{_escape_html(getattr(button_type, "query", ""))}"')
    else:
        name, fields = mapping.get(type_name, ("url", ("url",)))
        attrs.append(f'type="{name}"')
        for field_name in fields:
            attr_name = "text" if type_name == "InlineButtonTypeCopy" else field_name.replace("_", "-")
            attrs.append(f'{attr_name}="{_escape_html(getattr(button_type, field_name, ""))}"')

    style = getattr(button, "style", None)
    if style:
        for name, field_name in (("primary", "bg_primary"), ("danger", "bg_danger"),
                                 ("success", "bg_success"), ("link", "link")):
            if getattr(style, field_name, False):
                attrs.append(f'style="{name}"')
                break
    return "<tg-button {}>{}</tg-button>".format(
        " ".join(attrs), _render_text_node(getattr(button, "text", None))
    )


def _render_block(block: object) -> str:
    if block is None:
        return ""

    try:
        block_type = block.__class__.__name__

        if block_type == "PageBlockParagraph":
            return "<p>{}</p>".format(_render_text_node(getattr(block, "text", None)))
        if block_type == "PageBlockMath":
            return "<tg-math-block>{}</tg-math-block>".format(_escape_html(getattr(block, "source", "")))
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
        if block_type.startswith("PageBlockHeading") and block_type[-1:] in "123456":
            level = block_type[-1]
            return "<h{}>{}</h{}>".format(level, _render_text_node(getattr(block, "text", None)), level)
        bold_blocks = {"PageBlockHeader", "PageBlockSubheader", "PageBlockSubtitle", "PageBlockTitle"}
        if block_type in bold_blocks:
            return "<b>{}</b>\n".format(_render_text_node(getattr(block, "text", None)))
        italic_blocks = {
            "PageBlockAuthorDate",
            "PageBlockFooter",
            "PageBlockKicker",
        }
        if block_type == "PageBlockAuthorDate":
            return "<i>{}</i>\n".format(_render_text_node(getattr(block, "author", None)))
        if block_type == "PageBlockFooter":
            return "<footer>{}</footer>".format(_render_text_node(getattr(block, "text", None)))
        if block_type in italic_blocks:
            return "<i>{}</i>\n".format(_render_text_node(getattr(block, "text", None)))
        if block_type in {"PageBlockBlockquote", "PageBlockPullquote"}:
            tag = "blockquote" if block_type == "PageBlockBlockquote" else "aside"
            content = _render_text_node(getattr(block, "text", None))
            author = _render_text_node(
                getattr(block, "author", None) or getattr(block, "caption", None)
            )
            cite = f"<cite>{author}</cite>" if author else ""
            return f"<{tag}>{content}{cite}</{tag}>"
        if block_type == "PageBlockBlockquoteBlocks":
            content = _render_blocks(getattr(block, "blocks", None)).strip()
            return "<blockquote>{}</blockquote>\n".format(content) if content else ""
        if block_type == "PageBlockDetails":
            title = _render_text_node(getattr(block, "title", None))
            content = _render_blocks(getattr(block, "blocks", None))
            open_attr = " open" if getattr(block, "open", False) else ""
            return f"<details{open_attr}><summary>{title}</summary>{content}</details>"
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
            return "<tg-thinking>{}</tg-thinking>".format(
                _render_text_node(getattr(block, "text", None))
            )
        if block_type == "PageBlockButtonRow":
            if getattr(block, "align_center", False):
                align = "center"
            elif getattr(block, "align_right", False):
                align = "right"
            elif getattr(block, "align_left", False):
                align = "left"
            else:
                align = ""
            align_attr = f' align="{align}"' if align else ""
            buttons = "".join(_render_button(button) for button in getattr(block, "buttons", None) or ())
            return f"<tg-button-row{align_attr}>{buttons}</tg-button-row>"
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
        if block_type in {"PageBlockChannel", "PageBlockMap", "InputPageBlockMap"}:
            label = "[map]" if block_type in {"PageBlockMap", "InputPageBlockMap"} else "[channel]"
            return _render_labeled_block(label, getattr(block, "caption", None))
        if block_type == "PageBlockList":
            return _render_list(block)
        if block_type == "PageBlockOrderedList":
            return _render_list(block, ordered=True)
        if block_type == "PageBlockDivider":
            return "<hr>"
        media_labels = {
            "PageBlockPhoto": ("[photo]", "photo_id", "photo"),
            "PageBlockVideo": ("[video]", "video_id", "video"),
            "PageBlockAudio": ("[audio]", "audio_id", "audio"),
            "PageBlockDocument": ("[document]", "document_id", "document"),
        }
        if block_type in media_labels:
            return _render_media_block(block, *media_labels[block_type])
        if block_type == "PageBlockUnsupported":
            return "[unsupported]\n"
    except Exception:
        return ""

    return ""


def rich_message_to_html(rich_message: object) -> str:
    validate_rich_message(rich_message)
    """Convert a RichMessage TL object to an HTML string."""
    try:
        blocks = getattr(rich_message, "blocks", None) or ()
        return "".join(_render_block(block) for block in blocks).rstrip()
    except Exception:
        return ""


def rich_message_to_text(rich_message: object) -> str:
    """Render visible RichMessage content directly, without HTML tag leakage."""
    def text_node(node: object, depth: int = 0) -> str:
        if node is None or depth >= _MAX_NESTING:
            return ""
        name = node.__class__.__name__
        if name == "TextPlain":
            return str(getattr(node, "text", ""))
        if name == "TextMath":
            return str(getattr(node, "source", ""))
        if name == "TextCustomEmoji":
            return str(getattr(node, "alt", ""))
        if name == "TextConcat":
            return "".join(text_node(child, depth + 1) for child in getattr(node, "texts", None) or ())
        if hasattr(node, "text"):
            return text_node(getattr(node, "text"), depth + 1)
        return ""

    def caption_text(caption: object) -> list[str]:
        if caption is None:
            return []
        if caption.__class__.__name__ == "PageCaption":
            return [text_node(getattr(caption, "text", None)), text_node(getattr(caption, "credit", None))]
        return [text_node(caption)]

    parts = []

    def append_block(block: object, depth: int = 0) -> None:
        if block is None or depth >= _MAX_NESTING:
            return
        name = block.__class__.__name__
        if name == "PageBlockMath":
            parts.append(str(getattr(block, "source", "")))
        elif name == "PageBlockButtonRow":
            parts.extend(text_node(getattr(button, "text", None)) for button in getattr(block, "buttons", None) or ())
        elif name in {"PageBlockList", "PageBlockOrderedList"}:
            for item in getattr(block, "items", None) or ():
                if hasattr(item, "text"):
                    parts.append(text_node(item.text))
                else:
                    for child in getattr(item, "blocks", None) or ():
                        append_block(child, depth + 1)
        elif name == "PageBlockTable":
            parts.append(text_node(getattr(block, "title", None)))
            for row in getattr(block, "rows", None) or ():
                parts.extend(text_node(getattr(cell, "text", None)) for cell in getattr(row, "cells", None) or ())
        elif name == "PageBlockDetails":
            parts.append(text_node(getattr(block, "title", None)))
            for child in getattr(block, "blocks", None) or ():
                append_block(child, depth + 1)
        elif hasattr(block, "text"):
            parts.append(text_node(getattr(block, "text", None)))
        parts.extend(caption_text(getattr(block, "caption", None)))
        if name == "PageBlockCover":
            cover = getattr(block, "cover", None)
            if cover is not None:
                append_block(cover, depth + 1)
        if name in {"PageBlockCollage", "PageBlockSlideshow"}:
            for child in getattr(block, "items", None) or ():
                append_block(child, depth + 1)

    for block in getattr(rich_message, "blocks", None) or ():
        append_block(block)
    return "\n".join(part for part in parts if part)


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

    from .html import unparse

    return unparse(getattr(message, "message", "") or "", getattr(message, "entities", None) or [])
