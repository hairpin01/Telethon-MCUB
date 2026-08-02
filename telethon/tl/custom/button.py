from .. import types
from ... import utils


def _parse_style(style=None, icon=None):
    """
    Converts a style string and icon into a KeyboardButtonStyle object.

    Valid style values: 'primary' (blue), 'success' (green), 'danger' (red).
    Icon should be a Telegram custom emoji document_id (int).

    If both icon and style are provided, creates a style with both.
    If only icon is provided, creates a style with just the custom emoji.
    If only style is provided, creates a colored button style.
    Returns None if neither style nor icon is provided.
    """
    if icon is not None:
        if not isinstance(icon, int):
            raise TypeError(f"icon must be an integer (Telegram custom emoji document_id), got {type(icon).__name__}")

        if style is None:
            return types.KeyboardButtonStyle(icon=icon)

        style_lower = style.lower()
        if style_lower == "primary":
            return types.KeyboardButtonStyle(icon=icon, bg_primary=True)
        elif style_lower == "success":
            return types.KeyboardButtonStyle(icon=icon, bg_success=True)
        elif style_lower == "danger":
            return types.KeyboardButtonStyle(icon=icon, bg_danger=True)
        else:
            raise ValueError(f"Unknown style '{style}'. Use: 'primary', 'success', 'danger'")

    if style is None:
        return None

    style_lower = style.lower()
    if style_lower == "primary":
        return types.KeyboardButtonStyle(bg_primary=True)
    elif style_lower == "success":
        return types.KeyboardButtonStyle(bg_success=True)
    elif style_lower == "danger":
        return types.KeyboardButtonStyle(bg_danger=True)
    else:
        raise ValueError(f"Unknown style '{style}'. Use: 'primary', 'success', 'danger'")


class Button:
    """
    .. note::

        This class is used to **define** reply markups, e.g. when
        sending a message or replying to events. When you access
        `Message.buttons <telethon.tl.custom.message.Message.buttons>`
        they are actually `MessageButton
        <telethon.tl.custom.messagebutton.MessageButton>`,
        so you might want to refer to that class instead.

    Helper class to allow defining ``reply_markup`` when
    sending a message with inline or keyboard buttons.

    You should make use of the defined class methods to create button
    instances instead making them yourself (i.e. don't do ``Button(...)``
    but instead use methods line `Button.inline(...) <inline>` etc.

    You can use `inline`, `switch_inline`, `url`, `copy`, `auth`, `buy`
    and `game` together to create inline buttons (under the message).

    You can use `text`, `request_location`, `request_phone` and `request_poll`
    together to create a reply markup (replaces the user keyboard).
    You can also configure the aspect of the reply with these.
    The latest message with a reply markup will be the one shown to the user
    (messages contain the buttons, not the chat itself).

    You **cannot** mix the two type of buttons together,
    and it will error if you try to do so.

    The text for all buttons may be at most 142 characters.
    If more characters are given, Telegram will cut the text
    to 128 characters and add the ellipsis (…) character as
    the 129.

    Most button methods accept a ``style`` keyword argument that sets the
    button color. Valid values are ``'primary'`` (blue), ``'success'`` (green),
    and ``'danger'`` (red). Requires Telegram 12.4+.

    Most button methods also accept an ``icon`` keyword argument that sets a
    custom emoji as the button icon. The ``icon`` should be a Telegram custom
    emoji document_id (int). Requires Telegram Premium.
    """

    def __init__(self, button, *, resize, single_use, selective, persistent, placeholder):
        self.button = button
        self.resize = resize
        self.single_use = single_use
        self.selective = selective
        self.persistent = persistent
        self.placeholder = placeholder

    @staticmethod
    def _is_inline(button):
        """
        Returns `True` if the button belongs to an inline keyboard.
        """
        return isinstance(
            button,
            (
                types.KeyboardButtonCopy,
                types.KeyboardButtonBuy,
                types.KeyboardButtonCallback,
                types.KeyboardButtonGame,
                types.KeyboardButtonSwitchInline,
                types.KeyboardButtonUrl,
                types.InputKeyboardButtonUrlAuth,
                types.KeyboardButtonWebView,
            ),
        )

    @staticmethod
    def inline(text, data=None, *, style=None, icon=None):
        """
        Creates a new inline button with some payload data in it.

        If `data` is omitted, the given `text` will be used as `data`.
        In any case `data` should be either `bytes` or `str`.

        Note that the given `data` must be less or equal to 64 bytes.
        If more than 64 bytes are passed as data, ``ValueError`` is raised.
        If you need to store more than 64 bytes, consider saving the real
        data in a database and a reference to that data inside the button.

        When the user clicks this button, `events.CallbackQuery
        <telethon.events.callbackquery.CallbackQuery>` will trigger with the
        same data that the button contained, so that you can determine which
        button was pressed.

        Args:
            style (`str`, optional):
                Button color. One of ``'primary'``, ``'success'``, ``'danger'``.

            icon (`int`, optional):
                Custom emoji ID to use as button icon. Requires Telegram Premium.
        """
        if not data:
            data = text.encode("utf-8")
        elif not isinstance(data, (bytes, bytearray, memoryview)):
            data = str(data).encode("utf-8")

        if len(data) > 64:
            raise ValueError("Too many bytes for the data")

        return types.KeyboardButtonCallback(text, data, style=_parse_style(style, icon))

    @staticmethod
    def switch_inline(text, query="", same_peer=False, *, style=None, icon=None):
        """
        Creates a new inline button to switch to inline query.

        If `query` is given, it will be the default text to be used
        when making the inline query.

        If ``same_peer is True`` the inline query will directly be
        set under the currently opened chat. Otherwise, the user will
        have to select a different dialog to make the query.

        When the user clicks this button, after a chat is selected, their
        input field will be filled with the username of your bot followed
        by the query text, ready to make inline queries.

        Args:
            style (`str`, optional):
                Button color. One of ``'primary'``, ``'success'``, ``'danger'``.

            icon (`int`, optional):
                Custom emoji ID to use as button icon. Requires Telegram Premium.
        """
        return types.KeyboardButtonSwitchInline(text, query, same_peer, style=_parse_style(style, icon))

    @staticmethod
    def url(text, url=None, *, style=None, icon=None):
        """
        Creates a new inline button to open the desired URL on click.

        If no `url` is given, the `text` will be used as said URL instead.

        You cannot detect that the user clicked this button directly.

        When the user clicks this button, a confirmation box will be shown
        to the user asking whether they want to open the displayed URL unless
        the domain is trusted, and once confirmed the URL will open in their
        device.

        Args:
            style (`str`, optional):
                Button color. One of ``'primary'``, ``'success'``, ``'danger'``.

            icon (`int`, optional):
                Custom emoji ID to use as button icon. Requires Telegram Premium.
        """
        return types.KeyboardButtonUrl(text, url or text, style=_parse_style(style, icon))

    @staticmethod
    def copy(text, copy_text=None, *, style=None, icon=None):
        """
        Creates a new inline button to copy the desired text on click.

        If no `copy_text` is given, the `text` will be copied instead.

        You cannot detect that the user clicked this button directly.

        When the user clicks this button, Telegram will copy the given text
        to their clipboard.

        Args:
            style (`str`, optional):
                Button color. One of ``'primary'``, ``'success'``, ``'danger'``.

            icon (`int`, optional):
                Custom emoji ID to use as button icon. Requires Telegram Premium.
        """
        if copy_text is None:
            copy_text = text

        return types.KeyboardButtonCopy(text, copy_text, style=_parse_style(style, icon))

    @staticmethod
    def auth(text, url=None, *, bot=None, write_access=False, fwd_text=None, style=None, icon=None):
        """
        Creates a new inline button to authorize the user at the given URL.

        You should set the `url` to be on the same domain as the one configured
        for the desired `bot` via `@BotFather <https://t.me/BotFather>`_ using
        the ``/setdomain`` command.

        For more information about letting the user login via Telegram to
        a certain domain, see https://core.telegram.org/widgets/login.

        If no `url` is specified, it will default to `text`.

        Args:
            bot (`hints.EntityLike`):
                The bot that requires this authorization. By default, this
                is the bot that is currently logged in (itself), although
                you may pass a different input peer.

                .. note::

                    For now, you cannot use ID or username for this argument.
                    If you want to use a different bot than the one currently
                    logged in, you must manually use `client.get_input_entity()
                    <telethon.client.users.UserMethods.get_input_entity>`.

            write_access (`bool`):
                Whether write access is required or not.
                This is `False` by default (read-only access).

            fwd_text (`str`):
                The new text to show in the button if the message is
                forwarded. By default, the button text will be the same.

            style (`str`, optional):
                Button color. One of ``'primary'``, ``'success'``, ``'danger'``.

            icon (`int`, optional):
                Custom emoji ID to use as button icon. Requires Telegram Premium.

        When the user clicks this button, a confirmation box will be shown
        to the user asking whether they want to login to the specified domain.
        """
        return types.InputKeyboardButtonUrlAuth(
            text=text,
            url=url or text,
            bot=utils.get_input_user(bot or types.InputUserSelf()),
            request_write_access=write_access,
            fwd_text=fwd_text,
            style=_parse_style(style, icon),
        )

    @classmethod
    def text(
        cls,
        text,
        *,
        resize=None,
        single_use=None,
        selective=None,
        persistent=None,
        placeholder=None,
        style=None,
        icon=None,
    ):
        """
        Creates a new keyboard button with the given text.

        Args:
            text (`str`):
                The title of the button.

            resize (`bool`):
                If present, the entire keyboard will be reconfigured to
                be resized and be smaller if there are not many buttons.

            single_use (`bool`):
                If present, the entire keyboard will be reconfigured to
                be usable only once before it hides itself.

            selective (`bool`):
                If present, the entire keyboard will be reconfigured to
                be "selective". The keyboard will be shown only to specific
                users. It will target users that are @mentioned in the text
                of the message or to the sender of the message you reply to.

            persistent (`bool`):
                If present, always show the keyboard when the regular keyboard
                is hidden. Defaults to false, in which case the custom keyboard
                can be hidden and revealed via the keyboard icon.

            placeholder (`str`):
                The placeholder to be shown in the input field when the keyboard is active;
                1-64 characters

            style (`str`, optional):
                Button color. One of ``'primary'``, ``'success'``, ``'danger'``.

            icon (`int`, optional):
                Custom emoji ID to use as button icon. Requires Telegram Premium.

        When the user clicks this button, a text message with the same text
        as the button will be sent, and can be handled with `events.NewMessage
        <telethon.events.newmessage.NewMessage>`. You cannot distinguish
        between a button press and the user typing and sending exactly the
        same text on their own.
        """
        return cls(
            types.KeyboardButton(text, style=_parse_style(style, icon)),
            resize=resize,
            single_use=single_use,
            selective=selective,
            persistent=persistent,
            placeholder=placeholder,
        )

    @classmethod
    def request_location(
        cls,
        text,
        *,
        resize=None,
        single_use=None,
        selective=None,
        persistent=None,
        placeholder=None,
        style=None,
        icon=None,
    ):
        """
        Creates a new keyboard button to request the user's location on click.

        ``resize``, ``single_use``, ``selective``, ``persistent`` and ``placeholder``
         are documented in `text`.

        Args:
            style (`str`, optional):
                Button color. One of ``'primary'``, ``'success'``, ``'danger'``.

            icon (`int`, optional):
                Custom emoji ID to use as button icon. Requires Telegram Premium.

        When the user clicks this button, a confirmation box will be shown
        to the user asking whether they want to share their location with the
        bot, and if confirmed a message with geo media will be sent.
        """
        return cls(
            types.KeyboardButtonRequestGeoLocation(text, style=_parse_style(style, icon)),
            resize=resize,
            single_use=single_use,
            selective=selective,
            persistent=persistent,
            placeholder=placeholder,
        )

    @classmethod
    def request_phone(
        cls,
        text,
        *,
        resize=None,
        single_use=None,
        selective=None,
        persistent=None,
        placeholder=None,
        style=None,
        icon=None,
    ):
        """
        Creates a new keyboard button to request the user's phone on click.

        ``resize``, ``single_use``, ``selective``, ``persistent`` and ``placeholder``
         are documented in `text`.

        Args:
            style (`str`, optional):
                Button color. One of ``'primary'``, ``'success'``, ``'danger'``.

            icon (`int`, optional):
                Custom emoji ID to use as button icon. Requires Telegram Premium.

        When the user clicks this button, a confirmation box will be shown
        to the user asking whether they want to share their phone with the
        bot, and if confirmed a message with contact media will be sent.
        """
        return cls(
            types.KeyboardButtonRequestPhone(text, style=_parse_style(style, icon)),
            resize=resize,
            single_use=single_use,
            selective=selective,
            placeholder=placeholder,
            persistent=persistent,
        )

    @classmethod
    def request_poll(
        cls,
        text,
        *,
        force_quiz=False,
        resize=None,
        single_use=None,
        selective=None,
        persistent=None,
        placeholder=None,
        style=None,
        icon=None,
    ):
        """
        Creates a new keyboard button to request the user to create a poll.

        If `force_quiz` is `False`, the user will be allowed to choose whether
        they want their poll to be a quiz or not. Otherwise, the user will be
        forced to create a quiz when creating the poll.

        If a poll is a quiz, there will be only one answer that is valid, and
        the votes cannot be retracted. Otherwise, users can vote and retract
        the vote, and the pol might be multiple choice.

        ``resize``, ``single_use``, ``selective``, ``persistent`` and ``placeholder``
         are documented in `text`.

        Args:
            style (`str`, optional):
                Button color. One of ``'primary'``, ``'success'``, ``'danger'``.

            icon (`int`, optional):
                Custom emoji ID to use as button icon. Requires Telegram Premium.

        When the user clicks this button, a screen letting the user create a
        poll will be shown, and if they do create one, the poll will be sent.
        """
        return cls(
            types.KeyboardButtonRequestPoll(text, quiz=force_quiz, style=_parse_style(style, icon)),
            resize=resize,
            single_use=single_use,
            selective=selective,
            persistent=persistent,
            placeholder=placeholder,
        )

    @staticmethod
    def clear(selective=None):
        """
         Clears all keyboard buttons after sending a message with this markup.
         When used, no other button should be present or it will be ignored.

        ``selective`` is as documented in `text`.

        """
        return types.ReplyKeyboardHide(selective=selective)

    @staticmethod
    def force_reply(single_use=None, selective=None, placeholder=None):
        """
        Forces a reply to the message with this markup. If used,
        no other button should be present or it will be ignored.

        ``single_use``, ``selective`` and ``placeholder`` are as documented in `text`.

        """
        return types.ReplyKeyboardForceReply(
            single_use=single_use, selective=selective, placeholder=placeholder
        )

    @staticmethod
    def buy(text, *, style=None, icon=None):
        """
        Creates a new inline button to buy a product.

        This can only be used when sending files of type
        :tl:`InputMediaInvoice`, and must be the first button.

        If the button is not specified, Telegram will automatically
        add the button to the message. See the
        `Payments API <https://core.telegram.org/api/payments>`__
        documentation for more information.

        Args:
            style (`str`, optional):
                Button color. One of ``'primary'``, ``'success'``, ``'danger'``.

            icon (`int`, optional):
                Custom emoji ID to use as button icon. Requires Telegram Premium.
        """
        return types.KeyboardButtonBuy(text, style=_parse_style(style, icon))

    @staticmethod
    def game(text, *, style=None, icon=None):
        """
        Creates a new inline button to start playing a game.

        This should be used when sending files of type
        :tl:`InputMediaGame`, and must be the first button.

        See the
        `Games <https://core.telegram.org/api/bots/games>`__
        documentation for more information on using games.

        Args:
            style (`str`, optional):
                Button color. One of ``'primary'``, ``'success'``, ``'danger'``.

            icon (`int`, optional):
                Custom emoji ID to use as button icon. Requires Telegram Premium.
        """
        return types.KeyboardButtonGame(text, style=_parse_style(style, icon))

    @classmethod
    def request_managed_bot(
        cls,
        text,
        *,
        suggested_name=None,
        suggested_username=None,
        resize=None,
        single_use=None,
        selective=None,
        persistent=None,
        placeholder=None,
        style=None,
        icon=None,
    ):
        """
        Creates a new keyboard button to request the user to create a managed bot.
        (Bot API 9.6)

        The button allows users to create a new bot that will be managed by the
        current bot. This requires the bot to have ``can_manage_bots`` capability.

        Args:
            text (`str`):
                The title of the button.

            suggested_name (`str`, optional):
                Suggested name for the new bot.

            suggested_username (`str`, optional):
                Suggested username for the new bot.

            resize, single_use, selective, persistent, placeholder:
                Documented in `text`.

            style (`str`, optional):
                Button color. One of ``'primary'``, ``'success'``, ``'danger'``.

            icon (`int`, optional):
                Custom emoji ID to use as button icon. Requires Telegram Premium.

        Note:
            This requires the bot to have ``can_manage_bots`` permission.
            Currently uses RequestPeerTypeCreateBot when available in the API.
        """
        from .. import types as tl_types
        
        peer_type = tl_types.RequestPeerTypeCreateBot(
            bot_managed=True,
            suggested_name=suggested_name,
            suggested_username=suggested_username,
        )
        
        return cls(
            tl_types.KeyboardButtonRequestPeer(
                text=text,
                button_id=0,
                peer_type=peer_type,
                max_quantity=1,
                style=_parse_style(style, icon),
            ),
            resize=resize,
            single_use=single_use,
            selective=selective,
            persistent=persistent,
            placeholder=placeholder,
        )
