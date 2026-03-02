# Telethon-MCUB Changelog

## v1.42.5 (2026-03-02)

### New Features

#### HTML Parser (`telethon/extensions/html.py`)
- Added support for `<tg-spoiler>` tag
- Added support for `<emoji document_id="...">` tag
- Added support for `<tg-emoji>` tag (already existed)
- Fixed blockquote expandable/collapsible quotes:
  - `<blockquote>` - regular quote
  - `<blockquote expandable>` - expandable quote (expanded by default)
  - `<blockquote expandable="false">` - collapsed quote

#### Payments (`telethon/client/payments.py`)
- Added `get_saved_gifts()` - Get saved star gifts
- Added `upgrade_gift()` - Upgrade star gift
- Added `_get_input_stargift()` - Helper for parsing gift IDs

#### Messages (`telethon/client/messages.py`)
- Added `translate()` - Translate message to specified language

#### Uploads (`telethon/client/uploads.py`)
- Added `upload_files()` - Batch file upload with parallel support

### Bug Fixes

#### Downloads (`telethon/client/downloads.py`)
- Fixed sender leak when `FileMigrateError` occurs (deadlock fix)

#### Network (`telethon/network/mtprotosender.py`)
- Fixed race condition in reconnection logic (deadlock fix)

#### Messages (`telethon/client/messages.py`)
- Fixed `delete_messages()` for inline messages

#### HTML Parser (`telethon/extensions/html.py`)
- Fixed AttributeError when blockquote has `expandable` attribute
- Fixed unparse for proper tag escaping

### Performance Improvements

#### Crypto (`telethon/crypto/aes.py`)
- Added LRU cache for AES objects

#### Entity Cache (`telethon/_updates/entitycache.py`)
- Added L1 access cache for frequently used entities

#### Message Packer (`telethon/extensions/messagepacker.py`)
- Added buffer reuse for efficiency

### Warnings

#### TelegramClient (`telethon/client/telegramclient.py`)
- Added warning if cryptg is not installed

---

## v1.42.4 (2026-03-01)

### New Features

#### Reaction Methods (`telethon/client/reactions.py`)
- `client.send_reaction(entity, message, reaction="👍", big=False, add_to_recent=True)` - Send reaction to message
- `client.get_message_reactions_list(entity, message, reaction=None, limit=100)` - Get list of users who reacted
- `client.set_default_reaction(reaction="👍")` - Set default reaction for new messages
- `client.set_chat_available_reactions(entity, reactions, reactions_limit=None, paid_enabled=None)` - Set available reactions for chat/channel
- `client.send_photo_as_private(entity, photo, caption=None, **kwargs)` - Send photo as private message

#### Message Methods (`telethon/tl/custom/message.py`)
- `message.answer(*args, **kwargs)` - Reply to message with quote (alias for `reply()`)

#### Events (`telethon/events/joinrequest.py`)
- `events.JoinRequest` - New event for chat join requests
  - `event.get_user()` - Get user who requested to join
  - `event.get_users()` - Get all users who requested to join
  - `event.approve()` - Approve join request
  - `event.reject()` - Reject join request
  - `event.approve_all()` - Approve all pending requests
  - `event.reject_all()` - Reject all pending requests

### Bug Fixes
- Fixed AttributeError in HTML parser when `blockquote` tag has `expandable` attribute with `None` value
