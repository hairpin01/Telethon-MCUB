import pytest

from telethon.extensions import BinaryReader
from telethon.tl import types, functions


def test_nested_invalid_serialization():
    large_long = 2**62
    request = functions.account.SetPrivacyRequest(
        key=types.InputPrivacyKeyChatInvite(),
        rules=[types.InputPrivacyValueDisallowUsers(users=[large_long])]
    )
    with pytest.raises(TypeError):
        bytes(request)


def test_nested_vector_round_trip():
    entries = [
        [types.TlsBlockDomain(), types.TlsBlockGrease(seed=123)],
        [],
        [types.TlsBlockRandom(length=32), types.TlsBlockPadding()],
    ]
    original = types.TlsBlockPermutation(entries=entries)

    serialized = bytes(original)
    assert serialized.count(b"\x15\xc4\xb5\x1c") == len(entries) + 1

    reader = BinaryReader(serialized)
    restored = reader.tgread_object()

    assert restored.to_dict() == original.to_dict()
    assert reader.position == len(serialized)
