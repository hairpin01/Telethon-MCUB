import io
import pathlib

import pytest

from telethon import utils
from telethon._updates.entitycache import EntityCache
from telethon.tl.types import (
    MessageMediaGame, Game, PhotoEmpty, Community, CommunityForbidden,
    InputPeerChannel, PeerChannel
)


def test_game_input_media_memory_error():
    large_long = 2**62
    media = MessageMediaGame(Game(
        id=large_long,  # <- key to trigger `MemoryError`
        access_hash=large_long,
        short_name='short_name',
        title='title',
        description='description',
        photo=PhotoEmpty(large_long),
    ))
    input_media = utils.get_input_media(media)
    bytes(input_media)  # <- shouldn't raise `MemoryError`


def test_private_get_extension():
    # Positive cases
    png_header = bytes.fromhex('89 50 4e 47 0d 0a 1a 0a  00 00 00 0d 49 48 44 52')
    png_buffer = io.BytesIO(png_header)

    class CustomFd:
        def __init__(self, name):
            self.name = name

    assert utils._get_extension('foo.bar.baz') == '.baz'
    assert utils._get_extension(pathlib.Path('foo.bar.baz')) == '.baz'
    assert utils._get_extension(CustomFd('foo.bar.baz')) == '.baz'

    # Negative cases
    null_header = bytes.fromhex('00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00')
    null_buffer = io.BytesIO(null_header)

    empty_header = bytes()
    empty_buffer = io.BytesIO(empty_header)

    assert utils._get_extension('foo') == ''
    assert utils._get_extension(pathlib.Path('foo')) == ''
    assert utils._get_extension(null_header) == ''
    assert utils._get_extension(null_buffer) == ''
    assert utils._get_extension(null_buffer) == ''  # make sure it did seek back
    assert utils._get_extension(empty_header) == ''
    assert utils._get_extension(empty_buffer) == ''
    assert utils._get_extension(empty_buffer) == ''  # make sure it did seek back
    assert utils._get_extension(CustomFd('foo')) == ''


def test_rle_encode_trailing_zeros():
    assert utils._rle_encode(b'\x12\x00\x00\x00\x00') == b'\x12\x00\x04'


def test_community_entities_are_channel_like_peers():
    community = Community(123, 'Community', PhotoEmpty(0), None, access_hash=456)
    forbidden = CommunityForbidden(124, 'Forbidden', access_hash=789)

    assert utils.get_peer(community) == PeerChannel(123)
    assert utils.get_peer_id(community) == utils.get_peer_id(PeerChannel(123))
    assert utils.get_input_peer(community) == InputPeerChannel(123, 456)
    assert utils.get_input_peer(forbidden) == InputPeerChannel(124, 789)

    minimum = Community(125, 'Minimum', PhotoEmpty(0), None, min=True, access_hash=1)
    with pytest.raises(TypeError):
        utils.get_input_peer(minimum)
    assert utils.get_input_peer(minimum, check_hash=False) == InputPeerChannel(125, 1)

    cache = EntityCache()
    cache.extend([], [community, forbidden])
    assert cache.get(123).hash == 456
    assert cache.get(124).hash == 789
