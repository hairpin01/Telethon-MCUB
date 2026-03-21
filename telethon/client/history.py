from __future__ import annotations

import json
import pathlib
import typing
from dataclasses import dataclass

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


@dataclass(frozen=True)
class HistoryExportResult:
    path: pathlib.Path
    messages_exported: int
    media_downloaded: int
    last_message_id: typing.Optional[int]
    resumed_from: typing.Optional[int] = None
    state_path: typing.Optional[pathlib.Path] = None
    media_dir: typing.Optional[pathlib.Path] = None


def _coerce_path(path, field_name: str) -> pathlib.Path:
    if isinstance(path, pathlib.Path):
        return path
    if isinstance(path, (str, bytes)):
        return pathlib.Path(path)
    if hasattr(path, "__fspath__"):
        return pathlib.Path(path)
    raise TypeError(f"{field_name} must be a filesystem path")


def _default_state_path(output_path: pathlib.Path) -> pathlib.Path:
    if output_path.suffix:
        return output_path.with_suffix(f"{output_path.suffix}.state.json")
    return output_path.with_name(f"{output_path.name}.state.json")


def _default_media_dir(output_path: pathlib.Path) -> pathlib.Path:
    stem = output_path.stem or output_path.name
    return output_path.parent / f"{stem}_media"


def _load_export_state(state_path: pathlib.Path) -> dict[str, typing.Any]:
    with state_path.open("r", encoding="utf-8") as state_file:
        data = json.load(state_file)
    if not isinstance(data, dict):
        raise ValueError("history export state must be a JSON object")
    return data


def _write_export_state(state_path: pathlib.Path, payload: dict[str, typing.Any]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = state_path.with_name(f"{state_path.name}.tmp")
    with temp_path.open("w", encoding="utf-8") as state_file:
        json.dump(payload, state_file, ensure_ascii=False, indent=2, sort_keys=True)
        state_file.write("\n")
    temp_path.replace(state_path)


class HistoryMethods:
    def iter_history_batches(
        self: "TelegramClient",
        entity: "typing.Any",
        *,
        batch_size: int = 100,
        limit: float = None,
        reverse: bool = False,
        **kwargs,
    ) -> typing.AsyncIterator[list["typing.Any"]]:
        """
        Iterate message history in fixed-size batches.
        """
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")

        async def _iterator():
            batch = []
            async for message in self.iter_messages(entity, limit=limit, reverse=reverse, **kwargs):
                batch.append(message)
                if len(batch) >= batch_size:
                    yield batch
                    batch = []

            if batch:
                yield batch

        return _iterator()

    async def export_history(
        self: "TelegramClient",
        entity: "typing.Any",
        output,
        *,
        batch_size: int = 100,
        limit: float = None,
        reverse: bool = True,
        media: bool = False,
        media_dir=None,
        resume: bool = False,
        state_path=None,
        **kwargs,
    ) -> HistoryExportResult:
        """
        Export message history into a JSONL file.
        """
        if resume and not reverse:
            raise ValueError("resume requires reverse=True")
        if resume and kwargs.get("ids") is not None:
            raise ValueError("resume is incompatible with ids")

        output_path = _coerce_path(output, "output")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if state_path is None and resume:
            state_path = _default_state_path(output_path)
        state_path = None if state_path is None else _coerce_path(state_path, "state_path")

        if media:
            if media_dir is None:
                media_dir = _default_media_dir(output_path)
            media_dir = _coerce_path(media_dir, "media_dir")
            media_dir.mkdir(parents=True, exist_ok=True)
        elif media_dir is not None:
            media_dir = _coerce_path(media_dir, "media_dir")
            media_dir.mkdir(parents=True, exist_ok=True)

        resumed_from = None
        total_messages = 0
        total_media = 0
        if resume and state_path and state_path.exists():
            if not output_path.exists():
                raise ValueError("resume state exists but output file is missing")

            state = _load_export_state(state_path)
            resumed_from = int(state.get("last_message_id") or 0) or None
            total_messages = int(state.get("messages_exported_total") or 0)
            total_media = int(state.get("media_downloaded_total") or 0)

        iter_kwargs = dict(kwargs)
        if resumed_from is not None:
            iter_kwargs["min_id"] = max(int(iter_kwargs.get("min_id") or 0), resumed_from)

        file_mode = "a" if resume and output_path.exists() else "w"
        messages_exported = 0
        media_downloaded = 0
        last_message_id = resumed_from

        with output_path.open(file_mode, encoding="utf-8") as export_file:
            async for batch in self.iter_history_batches(
                entity,
                batch_size=batch_size,
                limit=limit,
                reverse=reverse,
                **iter_kwargs,
            ):
                for message in batch:
                    export_file.write(message.to_json(ensure_ascii=False))
                    export_file.write("\n")
                    last_message_id = getattr(message, "id", last_message_id)
                    messages_exported += 1

                    if media_dir is not None and getattr(message, "media", None):
                        await self.download_media(message, media_dir)
                        media_downloaded += 1

                export_file.flush()

                if state_path is not None:
                    _write_export_state(
                        state_path,
                        {
                            "format": "telethon-history-export-v1",
                            "last_message_id": last_message_id,
                            "media_dir": None if media_dir is None else str(media_dir),
                            "media_downloaded_total": total_media + media_downloaded,
                            "messages_exported_total": total_messages + messages_exported,
                            "output": str(output_path),
                            "reverse": reverse,
                        },
                    )

        return HistoryExportResult(
            path=output_path,
            messages_exported=messages_exported,
            media_downloaded=media_downloaded,
            last_message_id=last_message_id,
            resumed_from=resumed_from,
            state_path=state_path,
            media_dir=media_dir,
        )
