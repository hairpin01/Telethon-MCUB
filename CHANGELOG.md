# Telethon-MCUB Changelog

## v1.42.12post1 (2026-03-18)

### Fix protection

- Fixed `ScamModuleDetected` for `ImportBotAuthorizationRequest` (delete metods from `scam_modules` list)

## v1.42.11 (2026-03-15)

### New Features

#### Colored Inline Buttons (`telethon/tl/custom/button.py`, `telethon/tl/types/__init__.py`)
- Added `style` parameter to all `Button` helper methods supporting `KeyboardButtonStyle`
- Supported styles: `'primary'` (blue), `'success'` (green), `'danger'` (red)
- Requires Telegram 12.4+ on the client side

Methods updated:
- `Button.inline(text, data, *, style=None)`
- `Button.switch_inline(text, query, same_peer, *, style=None)`
- `Button.url(text, url, *, style=None)`
- `Button.auth(text, url, *, style=None, ...)`
- `Button.text(text, *, style=None, ...)`
- `Button.request_location(text, *, style=None, ...)`
- `Button.request_phone(text, *, style=None, ...)`
- `Button.request_poll(text, *, style=None, ...)`
- `Button.buy(text, *, style=None)`
- `Button.game(text, *, style=None)`

Usage:
```python
# Colored inline buttons
Button.inline("Confirm ✅", b"confirm", style="success")   # green
Button.inline("Cancel ❌",  b"cancel",  style="danger")    # red
Button.inline("Next →",     b"next",    style="primary")   # blue

# Works with switch_inline too
Button.switch_inline("Search", query="", style="primary")

# Under the hood maps to KeyboardButtonStyle TL object
# style="success" -> KeyboardButtonStyle(bg_success=True)
# style="danger"  -> KeyboardButtonStyle(bg_danger=True)
# style="primary" -> KeyboardButtonStyle(bg_primary=True)
```

---


## v1.42.10 (2026-03-07)

### Performance Improvements

#### TL Serialization Optimization (`telethon/extensions/binaryreader.py`)
- Added LRU cache (1024 entries) for constructor_id -> class lookup
- Optimized read() method with local variables
- Fast-path checks for bool/vector before dictionary lookup

#### Chunk Size Optimization (`telethon/client/telegrambaseclient.py`, `telethon/utils.py`, `telethon/client/downloads.py`, `telethon/client/uploads.py`)
- Added configurable `max_chunk_size` parameter to `TelegramClient` constructor (default: 512KB)
- Increased maximum chunk size to 1MB for upload/download operations
- New `get_appropriated_part_size()` now accepts `max_chunk_size` parameter
- Backward compatible: existing code works without changes

Usage:
```python
# Default 512KB (backward compatible)
client = TelegramClient(session, api_id, api_hash)

# Custom chunk size
client = TelegramClient(session, api_id, api_hash, max_chunk_size=1024*1024)  # 1MB

# Override per file
await client.download_file(media, part_size_kb=512)
await client.upload_file(file, part_size_kb=512)
```

#### uvloop Support (`telethon/__init__.py`)
- Added `install_uvloop()` function for easy uvloop integration
- Works on Unix-like systems (Linux, macOS)
- Returns `False` on Windows or if uvloop is not installed

Usage:
```python
import telethon
telethon.install_uvloop()
```

## v1.42.9.post6 (2026-03-04)

### Security / Protection

- Fixed masking for restricted system peers when `from_id` is missing (private/system dialogs may come with `from_id=None`).
- Added regression test for `peer_id=777000` + `from_id=None`.

### Documentation

- Added AntiScamModules usage example (blocked dangerous request and expected `ScamModuleDetected`):

```python
from telethon import functions
from telethon.client.protection import ScamModuleDetected

try:
    req = functions.InvokeWithoutUpdatesRequest(
        query=functions.InvokeWithTakeoutRequest(
            takeout_id=1,
            query=functions.account.DeleteAccountRequest(reason="test"),
        )
    )
    await client(req)
except ScamModuleDetected as e:
    print(e)  # Method 'DeleteAccountRequest' blocked!
```

## v1.42.9.post3 (2026-03-04)

### Release

- Post-release with inline media improvements and parser fixes.
- Fixed `invert_media` forwarding for inline message edits in `client.edit_message()`.
- No API-breaking changes.

## v1.42.8 (2026-03-04)

### New Features

#### Reactions (`telethon/client/reactions.py`)
- Added `iter_message_reactions()` - Async iterator over message reactions with pagination
- Added `clear_reaction()` - Remove own reaction from a message
- Added `get_message_read_participants()` - Get users who read a message
- Added `get_available_reactions()` - Get account-available reactions
- Added `get_available_effects()` - Get account-available message effects
- Added `send_story_reaction()` - Send reaction to a story
- Enhanced `get_message_reactions_list()` with `offset` support for pagination

### Security Improvements

#### Protection (`telethon/client/protection.py`, `telethon/client/users.py`)
- Added recursive detection of dangerous requests inside `Invoke*` wrappers
- Extended blocked request list with:
  - `auth.ResetAuthorizationsRequest`
  - `auth.LogOutRequest`
  - `account.InitTakeoutSessionRequest`
- Hardened batched request checking in `_call()`

### Bug Fixes

#### Core Client
- Fixed flood threshold forwarding in `UserMethods.__call__`
- Fixed `_dispatch_event()` dispatch for pre-built events (e.g. album hack flow)
- Fixed generator-based request handling in `_call()`

### Documentation
- Synced quick reference with all public `TelegramClient` methods

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
