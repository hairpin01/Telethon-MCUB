from telethon import Button
from telethon.client.buttons import ButtonMethods
from telethon.tl import types


def test_copy_button_uses_keyboard_button_copy():
    button = Button.copy("Copy", "secret")

    assert isinstance(button, types.KeyboardButtonCopy)
    assert button.text == "Copy"
    assert button.copy_text == "secret"


def test_copy_button_defaults_to_visible_text():
    button = Button.copy("Copy")

    assert button.copy_text == "Copy"


def test_copy_button_builds_inline_markup():
    button = Button.copy("Copy", "secret")

    markup = ButtonMethods.build_reply_markup(button)

    assert isinstance(markup, types.ReplyInlineMarkup)
    assert markup.rows[0].buttons[0] is button


def test_copy_button_supports_style_and_icon():
    button = Button.copy("Copy", "secret", style="success", icon=123)

    assert isinstance(button.style, types.KeyboardButtonStyle)
    assert button.style.bg_success is True
    assert button.style.icon == 123
