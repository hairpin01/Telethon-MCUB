import pathlib

import pytest

from telethon.client import DownloadMethods
from telethon.client.transfers import JsonTransferStateStore
from telethon.tl import types


class _ResumeDownloadClient(DownloadMethods):
    def __init__(self, data, *, fail_after_chunks=None):
        self.data = data
        self.fail_after_chunks = fail_after_chunks
        self.iter_calls = []
        self._max_chunk_size = 1024 * 1024

    def _iter_download(
        self,
        file,
        *,
        offset=0,
        request_size=1024 * 1024,
        dc_id=None,
        msg_data=None,
        cdn_redirect=None,
        **kwargs,
    ):
        self.iter_calls.append(
            {
                "file": file,
                "offset": offset,
                "request_size": request_size,
                "dc_id": dc_id,
            }
        )

        async def _iterator():
            emitted = 0
            pos = offset
            while pos < len(self.data):
                chunk = self.data[pos : pos + request_size]
                if not chunk:
                    break
                pos += len(chunk)
                yield chunk
                emitted += 1
                if self.fail_after_chunks is not None and emitted >= self.fail_after_chunks:
                    raise RuntimeError("download interrupted")

        return _iterator()


class _CaptureDownloadMediaClient(DownloadMethods):
    def __init__(self):
        self.captured = None

    async def _download_document(self, document, file, date, thumb, progress_callback, msg_data, **kwargs):
        self.captured = {
            "document": document,
            "file": file,
            "thumb": thumb,
            "msg_data": msg_data,
            **kwargs,
        }
        return "ok"


def _document_location(doc_id: int):
    return types.InputDocumentFileLocation(
        id=doc_id,
        access_hash=doc_id + 100,
        file_reference=b"ref",
        thumb_size="",
    )


def _document(doc_id: int, size: int):
    return types.Document(
        id=doc_id,
        access_hash=doc_id + 100,
        file_reference=b"ref",
        date=None,
        mime_type="application/octet-stream",
        size=size,
        thumbs=[],
        dc_id=2,
        attributes=[],
    )


@pytest.mark.asyncio
async def test_download_file_resume_continues_after_interruption(tmp_path):
    data = (b"a" * 4096) + (b"b" * 4096) + (b"c" * 4096)
    output = tmp_path / "file.bin"
    state_path = tmp_path / "file.state.json"
    location = _document_location(1)

    first = _ResumeDownloadClient(data, fail_after_chunks=1)
    with pytest.raises(RuntimeError, match="interrupted"):
        await first.download_file(
            location,
            output,
            file_size=len(data),
            part_size_kb=4,
            resume=True,
            state_store=state_path,
        )

    assert output.read_bytes() == data[:4096]

    second = _ResumeDownloadClient(data)
    result = await second.download_file(
        location,
        output,
        file_size=len(data),
        part_size_kb=4,
        resume=True,
        state_store=state_path,
    )

    assert result is None
    assert output.read_bytes() == data
    assert first.iter_calls[0]["offset"] == 0
    assert second.iter_calls[0]["offset"] == 4096
    assert not state_path.exists()
    assert JsonTransferStateStore(state_path).load(str(output.resolve())) is None


@pytest.mark.asyncio
async def test_download_file_resume_bootstraps_from_existing_partial_file(tmp_path):
    data = (b"a" * 4096) + (b"b" * 4096)
    output = tmp_path / "file.bin"
    output.write_bytes(data[:4096])
    location = _document_location(2)

    client = _ResumeDownloadClient(data)
    await client.download_file(
        location,
        output,
        file_size=len(data),
        part_size_kb=4,
        resume=True,
    )

    assert output.read_bytes() == data
    assert client.iter_calls[0]["offset"] == 4096


@pytest.mark.asyncio
async def test_download_file_resume_rejects_state_for_different_file(tmp_path):
    data = (b"a" * 4096) + (b"b" * 4096)
    output = tmp_path / "file.bin"
    state_path = tmp_path / "file.state.json"

    first = _ResumeDownloadClient(data, fail_after_chunks=1)
    with pytest.raises(RuntimeError):
        await first.download_file(
            _document_location(10),
            output,
            file_size=len(data),
            part_size_kb=4,
            resume=True,
            state_store=state_path,
        )

    second = _ResumeDownloadClient(data)
    with pytest.raises(ValueError, match="resume state does not match this download"):
        await second.download_file(
            _document_location(11),
            output,
            file_size=len(data),
            part_size_kb=4,
            resume=True,
            state_store=state_path,
        )


@pytest.mark.asyncio
async def test_download_media_document_forwards_resume_arguments(tmp_path):
    client = _CaptureDownloadMediaClient()
    state_path = tmp_path / "state.json"
    document = _document(42, 8192)

    result = await client.download_media(
        document,
        tmp_path / "file.bin",
        resume=True,
        resume_key="doc:42",
        state_store=state_path,
    )

    assert result == "ok"
    assert client.captured["resume"] is True
    assert client.captured["resume_key"] == "doc:42"
    assert client.captured["state_store"] == state_path
