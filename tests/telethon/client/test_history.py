import json

import pytest

from telethon.client import HistoryMethods


class _ExportMessage:
    def __init__(self, message_id, text, *, media=False):
        self.id = message_id
        self.text = text
        self.media = object() if media else None

    def to_json(self, **kwargs):
        return json.dumps({"id": self.id, "text": self.text}, **kwargs)


class _HistoryClient(HistoryMethods):
    def __init__(self, messages):
        self.messages = list(messages)
        self.iter_calls = []
        self.download_calls = []

    def iter_messages(self, entity, limit=None, reverse=False, **kwargs):
        self.iter_calls.append(
            {
                "entity": entity,
                "limit": limit,
                "reverse": reverse,
                **kwargs,
            }
        )

        async def _iterator():
            messages = self.messages if reverse else list(reversed(self.messages))
            min_id = kwargs.get("min_id") or 0
            max_id = kwargs.get("max_id") or 0
            count = 0

            for message in messages:
                if min_id and message.id <= min_id:
                    continue
                if max_id and message.id >= max_id:
                    continue
                if limit is not None and count >= limit:
                    break
                count += 1
                yield message

        return _iterator()

    async def download_media(self, message, file, **kwargs):
        self.download_calls.append((message.id, file))
        media_path = file / f"{message.id}.bin"
        media_path.write_text(f"media:{message.id}", encoding="utf-8")
        return str(media_path)


@pytest.mark.asyncio
async def test_iter_history_batches_groups_messages():
    client = _HistoryClient(
        [
            _ExportMessage(1, "one"),
            _ExportMessage(2, "two"),
            _ExportMessage(3, "three"),
            _ExportMessage(4, "four"),
            _ExportMessage(5, "five"),
        ]
    )

    batches = []
    async for batch in client.iter_history_batches("chat", batch_size=2, reverse=True):
        batches.append([message.id for message in batch])

    assert batches == [[1, 2], [3, 4], [5]]
    assert client.iter_calls == [{"entity": "chat", "limit": None, "reverse": True}]


@pytest.mark.asyncio
async def test_export_history_writes_jsonl_and_downloads_media(tmp_path):
    client = _HistoryClient(
        [
            _ExportMessage(1, "one"),
            _ExportMessage(2, "two", media=True),
            _ExportMessage(3, "three"),
        ]
    )
    output = tmp_path / "history.jsonl"
    state_path = tmp_path / "history.state.json"

    result = await client.export_history(
        "chat",
        output,
        batch_size=2,
        media=True,
        state_path=state_path,
    )

    assert result.path == output
    assert result.messages_exported == 3
    assert result.media_downloaded == 1
    assert result.last_message_id == 3
    assert result.state_path == state_path
    assert result.media_dir == tmp_path / "history_media"

    lines = output.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["id"] for line in lines] == [1, 2, 3]

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["last_message_id"] == 3
    assert state["messages_exported_total"] == 3
    assert state["media_downloaded_total"] == 1

    assert client.download_calls == [(2, tmp_path / "history_media")]
    assert (tmp_path / "history_media" / "2.bin").read_text(encoding="utf-8") == "media:2"


@pytest.mark.asyncio
async def test_export_history_resume_uses_state_min_id_and_appends(tmp_path):
    client = _HistoryClient(
        [
            _ExportMessage(1, "one"),
            _ExportMessage(2, "two"),
            _ExportMessage(3, "three"),
            _ExportMessage(4, "four"),
        ]
    )
    output = tmp_path / "history.jsonl"

    first = await client.export_history("chat", output, limit=2, resume=True)
    second = await client.export_history("chat", output, resume=True)

    assert first.messages_exported == 2
    assert first.last_message_id == 2
    assert second.resumed_from == 2
    assert second.messages_exported == 2
    assert second.last_message_id == 4
    assert client.iter_calls[1]["min_id"] == 2

    lines = output.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["id"] for line in lines] == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_export_history_resume_requires_reverse():
    client = _HistoryClient([_ExportMessage(1, "one")])

    with pytest.raises(ValueError, match="resume requires reverse=True"):
        await client.export_history("chat", "history.jsonl", resume=True, reverse=False)
