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

import re
from dataclasses import dataclass, field
from html import escape
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple, Union

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
    checkbox: Optional[bool] = None   # None = no checkbox; True/False = checked state.
    value: Optional[int] = None       # <li value="N">

    def to_html(self) -> str:
        val_attr = f' value="{self.value}"' if self.value is not None else ""
        prefix = ""
        if self.checkbox is not None:
            checked = " checked" if self.checkbox else ""
            prefix = f'<input type="checkbox"{checked}>'
        return f"<li{val_attr}>{prefix}{_ih(self.content)}</li>"

    def to_tl(self) -> dict:
        d: dict = {"_": "InputRichBlockListItem", "text": _it(self.content)}
        if self.checkbox is not None:
            d["checkbox"] = True
            d["checked"] = self.checkbox
        if self.value is not None:
            d["num"] = self.value
        return d


@dataclass
class BlockList:
    """<ul>/<ol> → InputRichBlockList"""
    ordered: bool = False
    items: List[ListItem] = field(default_factory=list)
    start: Optional[int] = None
    reversed_: bool = False

    def to_html(self) -> str:
        tag = "ol" if self.ordered else "ul"
        attrs = ""
        if self.start is not None:
            attrs += f' start="{self.start}"'
        if self.reversed_:
            attrs += " reversed"
        return f"<{tag}{attrs}>{''.join(i.to_html() for i in self.items)}</{tag}>"

    def to_tl(self) -> dict:
        d: dict = {"_": "InputRichBlockList", "ordered": self.ordered,
                   "items": [i.to_tl() for i in self.items]}
        if self.start is not None:
            d["start"] = self.start
        if self.reversed_:
            d["reversed"] = True
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
    is_header: bool = False
    colspan: Optional[int] = None
    rowspan: Optional[int] = None

    def to_html(self) -> str:
        tag = "th" if self.is_header else "td"
        a = ""
        if self.align:
            a += f' align="{escape(self.align, quote=True)}"'
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

    def to_html(self) -> str:
        a = ""
        if self.bordered:
            a += " bordered"
        if self.striped:
            a += " striped"
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


Block = Union[
    BlockParagraph, BlockHeading, BlockPreformatted, BlockFooter,
    BlockDivider, BlockMath, BlockAnchor, BlockList, BlockQuotation,
    BlockPullQuotation, BlockCollage, BlockSlideshow, BlockTable,
    BlockDetails, BlockMap, BlockPhoto, BlockVideo, BlockAudio,
    BlockAnimation, BlockVoiceNote, BlockThinking,
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
                "footer", "blockquote", "aside", "li",
                "figcaption", "caption_credit",
                "td", "th", "summary", "thinking",
                "pre", "math_inline", "math_block",
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
            top.extra.setdefault("blocks", []).append(block)
            return
        if top and top.kind in ("collage", "slideshow"):
            # Collage/slideshow media items are added via _handle_media_void.
            pass
        self.blocks.append(block)

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
            start = _int_attr(ad.get("start"))
            rev = "reversed" in ad
            self._push(_Frame("list", tag, ad, {
                "ordered": ordered, "start": start, "reversed": rev, "items": [],
            }))
            return

        if tag == "li":
            top = self._top()
            value = _int_attr(ad.get("value"))
            self._push(_Frame("li", "li", ad, {
                "value": value, "checkbox": None,
            }))
            return

        if tag == "table":
            bordered = "bordered" in ad or _truthy(ad.get("bordered")) is True
            striped = "striped" in ad or _truthy(ad.get("striped")) is True
            self._push(_Frame("table", "table", ad, {
                "title": None, "bordered": bordered if bordered else None,
                "striped": striped if striped else None, "rows": [],
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
            colspan = _int_attr(ad.get("colspan"))
            rowspan = _int_attr(ad.get("rowspan"))
            self._push(_Frame(tag, tag, ad, {
                "align": align, "colspan": colspan, "rowspan": rowspan,
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
            if eid:
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
            text = "".join(
                i.text if isinstance(i, TextPlain) else "" for i in frame.items
            )
            target = self._inline_target()
            if target:
                target.items.append(TextCode(text))
            return

        if kind == "tg_emoji":
            text = "".join(
                i.text if isinstance(i, TextPlain) else " " for i in frame.items
            ) or " "
            target = self._inline_target()
            if target:
                target.items.append(TextEmoji(frame.extra["emoji_id"], text))
            return

        if kind == "tg_time":
            text = "".join(
                i.text if isinstance(i, TextPlain) else "" for i in frame.items
            )
            target = self._inline_target()
            if target:
                target.items.append(TextDateTime(
                    frame.extra["unix"], frame.extra.get("format"), text
                ))
            return

        if kind == "math_inline":
            text = "".join(
                i.text if isinstance(i, TextPlain) else "" for i in frame.items
            )
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
            text = "".join(
                i.text if isinstance(i, TextPlain) else "" for i in frame.items
            )
            lang = frame.extra.get("language")
            self._emit(BlockPreformatted(text, lang))
            return

        if kind == "math_block":
            text = "".join(
                i.text if isinstance(i, TextPlain) else "" for i in frame.items
            )
            self._emit(BlockMath(text))
            return

        if kind == "thinking":
            text = "".join(
                i.text if isinstance(i, TextPlain) else "" for i in frame.items
            )
            self._emit(BlockThinking(text))
            return

        if kind == "anchor_block":
            text = "".join(
                i.text if isinstance(i, TextPlain) else "" for i in frame.items
            )
            self._emit(BlockAnchor(frame.extra["name"], text))
            return

        if kind == "summary":
            title_text = "".join(
                i.text if isinstance(i, TextPlain) else "" for i in frame.items
            )
            parent = self._top()
            if parent and parent.kind == "details":
                parent.extra["title"] = title_text
            return

        if kind == "details":
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
            title_text = "".join(
                i.text if isinstance(i, TextPlain) else "" for i in frame.items
            )
            parent = self._top()
            if parent and parent.kind == "table":
                parent.extra["title"] = title_text
            return

        if kind in ("td", "th"):
            cell = TableCell(
                content=frame.items,
                align=frame.extra.get("align"),
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
            ))
            return

        if kind == "li":
            item = ListItem(
                content=frame.items,
                checkbox=frame.extra.get("checkbox"),
                value=frame.extra.get("value"),
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
    return blocks_to_tl(parse_rich_html(html))


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
        )
    if kind == "InputRichBlockThinking":
        return types.PageBlockThinking(_tl_text(value.get("text")))

    # Media source references need file mapping to concrete Telegram media ids.
    return types.PageBlockUnsupported()


def html_to_tl_blocks(html: str):
    """Parse Rich HTML into real Telethon PageBlock TL objects."""
    return [_tl_block(block) for block in html_to_input_blocks(html)]


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
        prefix = ""
        if getattr(item, "checkbox", False):
            prefix = "[x] " if getattr(item, "checked", False) else "[ ] "

        if item.__class__.__name__.startswith("Text"):
            return (prefix + _render_text_node(item).strip()).strip()
        if isinstance(item, str):
            return (prefix + _escape_html(item).strip()).strip()
        if hasattr(item, "text"):
            return (prefix + _render_text_node(getattr(item, "text", None)).strip()).strip()

        blocks = getattr(item, "blocks", None)
        if blocks:
            rendered = " ".join(
                rendered
                for rendered in (_render_block(block).strip() for block in blocks)
                if rendered
            )
            return (prefix + rendered).strip()

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
        if block_type in {"PageBlockChannel", "PageBlockMap", "InputPageBlockMap"}:
            label = "[map]" if block_type in {"PageBlockMap", "InputPageBlockMap"} else "[channel]"
            return _render_labeled_block(label, getattr(block, "caption", None))
        if block_type == "PageBlockList":
            return _render_list(block)
        if block_type == "PageBlockOrderedList":
            return _render_list(block, ordered=True)
        if block_type == "PageBlockDivider":
            return "\n---\n"
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

    from .html import unparse

    return unparse(getattr(message, "message", "") or "", getattr(message, "entities", None) or [])
