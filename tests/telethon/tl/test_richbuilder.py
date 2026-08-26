from telethon.tl.custom import RichBuilder, RichText
from telethon.extensions import richparser
from telethon.tl import types


def test_rich_text_escapes_text_and_attrs():
    rich = RichText().h1("A < B").link("x & y", 'https://e.com/?a="b"')

    assert str(rich) == (
        "<h1>A &lt; B</h1>"
        '<a href="https://e.com/?a=&quot;b&quot;">x &amp; y</a>'
    )


def test_rich_builder_media_link():
    rich = RichBuilder().p("Hi").media("Video", "clip", kind="video")

    assert str(rich) == '<p>Hi</p><a href="tg://video?id=clip">Video</a>'


def test_rich_builder_inline_formatting_blocks():
    rich = (
        RichBuilder()
        .h3("H <3")
        .underline("u")
        .strike("s")
        .sub("sub")
        .sup("sup")
        .math("E = mc^2")
        .inline_math("x^2 + y^2")
        .code("inline_code()")
        .pre("print('Hello')", language="python")
        .quote("quote", expandable=False)
        .quote("quoted <text>", author="Ivan & Co")
        .code_quote("{'x': 1}")
        .footer("bottom <line>")
    )

    assert str(rich) == (
        "<h3>H &lt;3</h3>"
        "<u>u</u>"
        "<s>s</s>"
        "<sub>sub</sub>"
        "<sup>sup</sup>"
        "<tg-math-block>E = mc^2</tg-math-block>"
        "<tg-math>x^2 + y^2</tg-math>"
        "<code>inline_code()</code>"
        '<pre><code class="language-python">print(&#x27;Hello&#x27;)</code></pre>'
        '<blockquote expandable="false">quote</blockquote>'
        '<blockquote>quoted &lt;text&gt;<cite>Ivan &amp; Co</cite></blockquote>'
        '<blockquote expandable="true"><code>{&#x27;x&#x27;: 1}</code></blockquote>'
        '<footer>bottom &lt;line&gt;</footer>'
    )


def test_rich_builder_lists_details_and_table_escape_values():
    rich = (
        RichBuilder()
        .details("Sum <", "Body &")
        .ul(["a < b", "c"])
        .ol(["one", "two"])
        .checklist([("done", True), ("todo <", False)])
        .table(
            [["1 < 2", ("ok", "right")]],
            headers=["A", "B"],
            title="T & C",
            header_align="center",
            bordered=True,
            striped=True,
        )
    )

    assert str(rich) == (
        "<details><summary>Sum &lt;</summary>Body &amp;</details>"
        "<ul><li>a &lt; b</li><li>c</li></ul>"
        "<ol><li>one</li><li>two</li></ol>"
        '<ul><li><input type="checkbox" checked>done</li>'
        '<li><input type="checkbox">todo &lt;</li></ul>'
        '<table bordered striped><caption>T &amp; C</caption><tr>'
        '<th align="center">A</th><th align="center">B</th></tr>'
        '<tr><td>1 &lt; 2</td><td align="right">ok</td></tr></table>'
    )


def test_rich_builder_compact_table_and_button_rows_escape_attributes():
    rich = (
        RichBuilder()
        .table([["cell"]], compact=True)
        .button("Open <x>", type="url", url='https://e.test/?q="x"')
        .button_row([{"text": "Copy", "type": "copy_text", "text_": "copy"}], align="center")
    )

    assert str(rich) == (
        '<table compact><tr><td>cell</td></tr></table>'
        '<tg-button-row><tg-button type="url" url="https://e.test/?q=&quot;x&quot;">Open &lt;x&gt;</tg-button></tg-button-row>'
        '<tg-button-row align="center"><tg-button type="copy_text" text="copy">Copy</tg-button></tg-button-row>'
    )
    message = richparser.html_to_input_rich_message(str(rich))
    assert isinstance(message.blocks[-2], types.PageBlockButtonRow)
    assert message.blocks[-2].buttons[0].type.url == 'https://e.test/?q="x"'
    assert isinstance(message.blocks[-1], types.PageBlockButtonRow)
    assert message.blocks[-1].buttons[0].type.copy_text == 'copy'

def test_rich_builder_official_block_helpers():
    rich = (
        RichBuilder()
        .hr()
        .ol(["step"], start=3, type="a", reversed=True)
        .details("Open", "<b>raw</b>", open=True, raw=True)
        .pullquote("pull <q>", author="Author")
        .photo("https://example.com/p.jpg", caption="Photo <cap>", credit="Cred")
        .video("https://example.com/v.mp4", spoiler=True)
        .audio("https://example.com/a.mp3", caption="Audio")
        .map(41.9, 12.5, zoom=14, caption="Rome")
        .collage(['<img src="https://example.com/1.jpg"/>'], caption="Gallery")
        .slideshow(['<video src="https://example.com/2.mp4"></video>'])
        .table(
            [[{"text": "wide", "colspan": 2, "valign": "middle"}]],
            bordered=True,
        )
        .anchor("top")
        .reference("note-1", "Referenced")
        .emoji(5368324170671202286, "👍")
        .time("tomorrow", unix=1647531900, format="wDT")
        .thinking("Thinking...")
    )

    assert str(rich) == (
        "<hr/>"
        '<ol start="3" type="a" reversed><li>step</li></ol>'
        "<details open><summary>Open</summary><b>raw</b></details>"
        "<aside>pull &lt;q&gt;<cite>Author</cite></aside>"
        '<figure><img src="https://example.com/p.jpg"/>'
        '<figcaption>Photo &lt;cap&gt;<cite>Cred</cite></figcaption></figure>'
        '<video src="https://example.com/v.mp4" tg-spoiler></video>'
        '<figure><audio src="https://example.com/a.mp3"></audio>'
        '<figcaption>Audio</figcaption></figure>'
        '<figure><tg-map lat="41.9" long="12.5" zoom="14"/>'
        '<figcaption>Rome</figcaption></figure>'
        '<tg-collage><img src="https://example.com/1.jpg"/>'
        '<figcaption>Gallery</figcaption></tg-collage>'
        '<tg-slideshow><video src="https://example.com/2.mp4"></video></tg-slideshow>'
        '<table bordered><tr><td colspan="2" valign="middle">wide</td></tr></table>'
        '<a name="top"></a>'
        '<tg-reference name="note-1">Referenced</tg-reference>'
        '<tg-emoji emoji-id="5368324170671202286">👍</tg-emoji>'
        '<tg-time unix="1647531900" format="wDT">tomorrow</tg-time>'
        '<tg-thinking>Thinking...</tg-thinking>'
    )
