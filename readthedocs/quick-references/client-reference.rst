.. _client-ref:

================
Client Reference
================

This page contains a summary of all the important methods and properties that
you may need when using Telethon. They are sorted by relevance and are not in
alphabetical order.

You should use this page to learn about which methods are available, and
if you need a usage example or further description of the arguments, be
sure to follow the links.

.. contents::

TelegramClient
==============

This is a summary of the methods and
properties you will find at :ref:`telethon-client`.

Auth
----

.. currentmodule:: telethon.client.auth.AuthMethods

.. autosummary::
    :nosignatures:

    start
    send_code_request
    sign_in
    qr_login
    log_out
    edit_2fa

Base
----

.. py:currentmodule:: telethon.client.telegrambaseclient.TelegramBaseClient

.. autosummary::
    :nosignatures:

    connect
    disconnect
    is_connected
    disconnected
    loop
    set_proxy

Messages
--------

.. py:currentmodule:: telethon.client.messages.MessageMethods

.. autosummary::
    :nosignatures:

    send_message
    edit_message
    delete_messages
    forward_messages
    iter_messages
    get_messages
    pin_message
    unpin_message
    send_read_acknowledge
    add_poll_answer
    delete_poll_answer
    translate

History
-------

.. py:currentmodule:: telethon.client.history.HistoryMethods

.. autosummary::
    :nosignatures:

    iter_history_batches
    export_history

Uploads
-------

.. py:currentmodule:: telethon.client.uploads.UploadMethods

.. autosummary::
    :nosignatures:

    send_file
    upload_file
    upload_files

Downloads
---------

.. currentmodule:: telethon.client.downloads.DownloadMethods

.. autosummary::
    :nosignatures:

    download_media
    download_profile_photo
    download_file
    iter_download

Dialogs
-------

.. py:currentmodule:: telethon.client.dialogs.DialogMethods

.. autosummary::
    :nosignatures:

    iter_dialogs
    get_dialogs
    edit_folder
    iter_drafts
    get_drafts
    delete_dialog
    conversation

Users
-----

.. py:currentmodule:: telethon.client.users.UserMethods

.. autosummary::
    :nosignatures:

    get_me
    is_bot
    is_user_authorized
    get_entity
    get_input_entity
    get_peer_id
    get_protection_policy
    set_protection_policy
    set_protection_mode
    on_blocked_request
    clear_blocked_request_handler
    add_request_middleware
    remove_request_middleware
    request_middleware

Chats
-----

.. currentmodule:: telethon.client.chats.ChatMethods

.. autosummary::
    :nosignatures:

    iter_participants
    get_participants
    kick_participant
    iter_admin_log
    get_admin_log
    iter_profile_photos
    get_profile_photos
    edit_admin
    edit_permissions
    get_permissions
    get_stats
    action

Parse Mode
----------

.. py:currentmodule:: telethon.client.messageparse.MessageParseMethods

.. autosummary::
    :nosignatures:

    parse_mode

Updates
-------

.. py:currentmodule:: telethon.client.updates.UpdateMethods

.. autosummary::
    :nosignatures:

    on
    run_until_disconnected
    add_event_handler
    remove_event_handler
    list_event_handlers
    catch_up
    set_receive_updates
    add_event_middleware
    remove_event_middleware
    middleware
    add_message_hook
    remove_message_hook
    remove_module_handlers
    wait_inline_send

Topics
------

.. py:currentmodule:: telethon.client.topics.TopicMethods

.. autosummary::
    :nosignatures:

    iter_topics
    get_topics
    get_topic
    create_topic
    edit_topic
    close_topic
    reopen_topic
    delete_topic_history
    pin_topic
    reorder_topics
    iter_topic_messages
    send_to_topic
    send_file_to_topic

Reactions
---------

.. py:currentmodule:: telethon.client.reactions.ReactionMethods

.. autosummary::
    :nosignatures:

    send_reaction
    get_message_reactions_list
    iter_message_reactions
    clear_reaction
    get_message_read_participants
    get_available_reactions
    get_available_effects
    send_story_reaction
    set_default_reaction
    set_chat_available_reactions
    send_photo_as_private

Gifts
-----

.. py:currentmodule:: telethon.client.payments.GiftMethods

.. autosummary::
    :nosignatures:

    get_saved_gifts
    upgrade_gift

Bots
----

.. currentmodule:: telethon.client.bots.BotMethods

.. autosummary::
    :nosignatures:

    inline_query

Buttons
-------

.. currentmodule:: telethon.client.buttons.ButtonMethods

.. autosummary::
    :nosignatures:

    build_reply_markup

Account
-------

.. currentmodule:: telethon.client.account.AccountMethods

.. autosummary::
    :nosignatures:

    takeout
    end_takeout
    add_profile_music
    remove_profile_music
    move_profile_music
    add_profile_album
    get_saved_music_ids
    iter_saved_music
