from html import escape


class RichText:
    """Small HTML text builder for Telegram rich/parsed messages."""

    def __init__(self, text=""):
        self._parts = []
        if text:
            self.text(text)

    def __str__(self):
        return "".join(self._parts)

    def raw(self, html):
        self._parts.append(str(html))
        return self

    def text(self, value):
        self._parts.append(escape(str(value)))
        return self

    @staticmethod
    def _attrs(**attrs):
        result = []
        for key, val in attrs.items():
            if val is None or val is False:
                continue
            if key.endswith("_"):
                key = key[:-1]
            key = key.replace("_", "-")
            if val is True:
                result.append(f" {key}")
            else:
                result.append(f' {key}="{escape(str(val), quote=True)}"')
        return "".join(result)

    @classmethod
    def _tag_html(cls, tag_name, value, **attrs):
        attr_text = cls._attrs(**attrs)
        return f"<{tag_name}{attr_text}>{escape(str(value))}</{tag_name}>"

    @classmethod
    def _tag_raw_html(cls, tag_name, html, **attrs):
        attr_text = cls._attrs(**attrs)
        return f"<{tag_name}{attr_text}>{html}</{tag_name}>"

    @classmethod
    def _void_tag_html(cls, tag_name, slash=False, **attrs):
        attr_text = cls._attrs(**attrs)
        return f"<{tag_name}{attr_text}{'/' if slash else ''}>"

    def tag(self, tag_name, value, **attrs):
        return self.raw(self._tag_html(tag_name, value, **attrs))

    def tag_raw(self, tag_name, html, **attrs):
        return self.raw(self._tag_raw_html(tag_name, html, **attrs))

    def br(self):
        return self.raw("<br>")

    def hr(self):
        return self.raw("<hr/>")

    divider = hr

    def p(self, value):
        return self.tag("p", value)

    def h1(self, value):
        return self.tag("h1", value)

    def h2(self, value):
        return self.tag("h2", value)

    def h3(self, value):
        return self.tag("h3", value)

    def h4(self, value):
        return self.tag("h4", value)

    def h5(self, value):
        return self.tag("h5", value)

    def h6(self, value):
        return self.tag("h6", value)

    def bold(self, value):
        return self.tag("b", value)

    b = bold

    def italic(self, value):
        return self.tag("i", value)

    i = italic

    def underline(self, value):
        return self.tag("u", value)

    u = underline

    def strike(self, value):
        return self.tag("s", value)

    s = strike

    def subscript(self, value):
        return self.tag("sub", value)

    sub = subscript

    def superscript(self, value):
        return self.tag("sup", value)

    sup = superscript

    def code(self, value):
        return self.tag("code", value)

    def math(self, value):
        return self.tag("tg-math-block", value)

    def inline_math(self, value):
        return self.tag("tg-math", value)

    def pre(self, value, language=None):
        if language:
            code = self._tag_html("code", value, class_=f"language-{language}")
            return self.tag_raw("pre", code)
        return self.tag("pre", value)

    def spoiler(self, value):
        return self.tag("tg-spoiler", value)

    def quote(self, value, *, author=None, expandable=None, raw=False):
        attrs = {}
        html = str(value) if raw else escape(str(value))
        if author is not None:
            html += self._tag_html("cite", author)
        if expandable is not None:
            attrs["expandable"] = "true" if expandable else "false"
        return self.tag_raw("blockquote", html, **attrs)

    def code_quote(self, value, *, expandable=True, author=None):
        return self.quote(
            self._tag_html("code", value),
            author=author,
            expandable=expandable,
            raw=True,
        )

    blockquote = quote

    def details(self, title, body, *, open=None, raw=False):
        return self.tag_raw(
            "details",
            "{}{}".format(
                self._tag_html("summary", title),
                str(body) if raw else escape(str(body)),
            ),
            open=open,
        )

    def li(self, value, *, raw=False, checkbox=None, checked=None, value_attr=None, type=None):
        prefix = ""
        if checkbox is not None:
            prefix = self._void_tag_html(
                "input", type="checkbox", checked=checked if checkbox else None
            )
        attrs = {"value": value_attr, "type": type}
        html = str(value) if raw else escape(str(value))
        return self._tag_raw_html("li", prefix + html, **attrs)

    def ul(self, items, *, raw=False):
        return self.tag_raw(
            "ul", "".join(self.li(item, raw=raw) for item in items)
        )

    def ol(self, items, *, start=None, type=None, reversed=None, raw=False):
        return self.tag_raw(
            "ol",
            "".join(self.li(item, raw=raw) for item in items),
            start=start,
            type=type,
            reversed=reversed,
        )

    def checklist(self, items):
        html = "".join(
            "<li><input{}>{}</li>".format(
                self._attrs(type="checkbox", checked=checked),
                escape(str(text)),
            )
            for text, checked in items
        )
        return self.tag_raw("ul", html)

    @staticmethod
    def _cell(value, default_align=None):
        attrs = {}
        if isinstance(value, tuple):
            if len(value) == 2:
                value, align = value
                attrs["align"] = align
            elif len(value) >= 3:
                cell_value, align, extra_attrs = value[0], value[1], value[2]
                value = cell_value
                attrs = dict(extra_attrs or {})
                attrs.setdefault("align", align)
        elif isinstance(value, dict):
            attrs = {k: v for k, v in value.items() if k != "text"}
            value = value.get("text", "")

        if default_align is not None:
            attrs.setdefault("align", default_align)

        return value, attrs

    def table(
        self,
        rows,
        headers=None,
        *,
        title=None,
        header_align=None,
        aligns=None,
        bordered=None,
        striped=None,
        compact=None,
    ):
        body = []
        if title:
            body.append(self._tag_html("caption", title))
        if headers:
            body.append(
                "<tr>{}</tr>".format(
                    "".join(
                        self._tag_html("th", value, **attrs)
                        for value, attrs in (
                            self._cell(cell, header_align) for cell in headers
                        )
                    )
                )
            )
        for row in rows:
            body.append(
                "<tr>{}</tr>".format(
                    "".join(
                        self._tag_html("td", value, **attrs)
                        for value, attrs in (
                            self._cell(
                                cell,
                                aligns[index]
                                if aligns is not None and index < len(aligns)
                                else None,
                            )
                            for index, cell in enumerate(row)
                        )
                    )
                )
            )
        return self.tag_raw(
            "table", "".join(body), bordered=bordered, striped=striped, compact=compact
        )

    def button(self, value, *, type="url", style=None, raw=False, **attrs):
        """Append a parser-consumable single-button official row."""
        html = str(value) if raw else escape(str(value))
        button = self._tag_raw_html("tg-button", html, type=type, style=style, **attrs)
        return self.tag_raw("tg-button-row", button)

    def button_row(self, buttons, *, align=None, raw=False):
        """Append a ``tg-button-row`` from button HTML or button specifications."""
        parts = []
        for button in buttons:
            if isinstance(button, str):
                parts.append(button if raw else self._tag_html("tg-button", button))
            elif isinstance(button, dict):
                values = dict(button)
                value = values.pop("text", "")
                parts.append(self._tag_raw_html("tg-button", str(value) if values.pop("raw", False) else escape(str(value)), **values))
            else:
                parts.append(str(button))
        return self.tag_raw("tg-button-row", "".join(parts), align=align)

    def footer(self, value):
        return self.tag("footer", value)

    def pullquote(self, value, *, author=None, raw=False):
        html = str(value) if raw else escape(str(value))
        if author is not None:
            html += self._tag_html("cite", author)
        return self.tag_raw("aside", html)

    aside = pullquote

    def anchor(self, name, text=""):
        return self.tag("a", text, name=name)

    def reference(self, name, value):
        return self.tag("tg-reference", value, name=name)

    def emoji(self, emoji_id, alt=" "):
        return self.tag("tg-emoji", alt, emoji_id=emoji_id)

    def time(self, text, *, unix, format=None):
        return self.tag("tg-time", text, unix=unix, format=format)

    @classmethod
    def _media_html(cls, tag, src, *, caption=None, credit=None, spoiler=None):
        media = cls._void_tag_html(tag, slash=True, src=src, tg_spoiler=spoiler)
        if tag in {"video", "audio"}:
            media = cls._tag_raw_html(tag, "", src=src, tg_spoiler=spoiler)
        if caption is None and credit is None:
            return media

        caption_html = ""
        if caption is not None:
            caption_html += escape(str(caption))
        if credit is not None:
            caption_html += cls._tag_html("cite", credit)
        return cls._tag_raw_html(
            "figure", media + cls._tag_raw_html("figcaption", caption_html)
        )

    def photo(self, src, *, caption=None, credit=None, spoiler=None):
        return self.raw(
            self._media_html("img", src, caption=caption, credit=credit, spoiler=spoiler)
        )

    image = photo

    def video(self, src, *, caption=None, credit=None, spoiler=None):
        return self.raw(
            self._media_html("video", src, caption=caption, credit=credit, spoiler=spoiler)
        )

    def audio(self, src, *, caption=None, credit=None):
        return self.raw(self._media_html("audio", src, caption=caption, credit=credit))

    def map(self, lat, long, *, zoom=None, caption=None):
        media = self._void_tag_html("tg-map", slash=True, lat=lat, long=long, zoom=zoom)
        if caption is None:
            return self.raw(media)
        return self.tag_raw(
            "figure", media + self._tag_html("figcaption", caption)
        )

    def collage(self, items, *, caption=None):
        html = "".join(str(item) for item in items)
        if caption is not None:
            html += self._tag_html("figcaption", caption)
        return self.tag_raw("tg-collage", html)

    def slideshow(self, items, *, caption=None):
        html = "".join(str(item) for item in items)
        if caption is not None:
            html += self._tag_html("figcaption", caption)
        return self.tag_raw("tg-slideshow", html)

    def thinking(self, value):
        return self.tag("tg-thinking", value)

    def link(self, text, url):
        return self.tag("a", text, href=url)

    def media(self, text, media_id, kind="media"):
        return self.link(text, f"tg://{kind}?id={media_id}")


class RichBuilder(RichText):
    """Alias with a more explicit name for chain-style rich HTML building."""
