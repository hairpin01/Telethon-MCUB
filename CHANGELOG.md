# Telethon-MCUB Changelog

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
