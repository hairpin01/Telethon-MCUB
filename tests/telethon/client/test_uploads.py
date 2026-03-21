import collections
import logging

import pytest

from telethon.client import UploadMethods
from telethon.client.transfers import JsonTransferStateStore


class _ResumeUploadClient(UploadMethods):
    def __init__(self, *, fail_on_part=None):
        self.fail_on_part = fail_on_part
        self.requests = []
        self._max_chunk_size = 1024 * 1024
        self._log = collections.defaultdict(lambda: logging.getLogger("test"))

    async def __call__(self, request):
        self.requests.append(request)
        if self.fail_on_part is not None and request.file_part >= self.fail_on_part:
            raise RuntimeError("upload interrupted")
        return True

    async def get_input_entity(self, entity):
        return entity


@pytest.mark.asyncio
async def test_upload_file_resume_continues_after_interruption(tmp_path):
    data = (b"a" * 4096) + (b"b" * 4096)
    input_file = tmp_path / "upload.bin"
    state_path = tmp_path / "upload.state.json"
    input_file.write_bytes(data)

    first = _ResumeUploadClient(fail_on_part=1)
    with pytest.raises(RuntimeError, match="interrupted"):
        await first.upload_file(
            input_file,
            part_size_kb=4,
            resume=True,
            state_store=state_path,
        )

    second = _ResumeUploadClient()
    uploaded = await second.upload_file(
        input_file,
        part_size_kb=4,
        resume=True,
        state_store=state_path,
    )

    assert uploaded.parts == 2
    assert [request.file_part for request in first.requests] == [0, 1]
    assert [request.file_part for request in second.requests] == [1]
    assert second.requests[0].file_id == first.requests[0].file_id
    assert not state_path.exists()
    assert JsonTransferStateStore(state_path).load(str(input_file.resolve())) is None


@pytest.mark.asyncio
async def test_upload_file_resume_rejects_modified_input_file(tmp_path):
    input_file = tmp_path / "upload.bin"
    state_path = tmp_path / "upload.state.json"
    input_file.write_bytes((b"a" * 4096) + (b"b" * 4096))

    first = _ResumeUploadClient(fail_on_part=1)
    with pytest.raises(RuntimeError):
        await first.upload_file(
            input_file,
            part_size_kb=4,
            resume=True,
            state_store=state_path,
        )

    input_file.write_bytes((b"z" * 4096) + (b"y" * 4096) + (b"x" * 4096))
    second = _ResumeUploadClient()
    with pytest.raises(ValueError, match="resume state does not match this upload"):
        await second.upload_file(
            input_file,
            part_size_kb=4,
            resume=True,
            state_store=state_path,
        )


@pytest.mark.asyncio
async def test_send_file_rejects_resume_for_albums():
    client = _ResumeUploadClient()

    with pytest.raises(ValueError, match="resume is not supported for album uploads"):
        await client.send_file("chat", ["a.jpg", "b.jpg"], resume=True)
