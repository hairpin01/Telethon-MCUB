from __future__ import annotations

import json
import pathlib
import typing
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class FileTransferState:
    transfer_type: str
    resume_key: str
    location_fingerprint: str
    offset: int = 0
    output_path: typing.Optional[str] = None
    file_size: typing.Optional[int] = None
    dc_id: typing.Optional[int] = None
    request_size: typing.Optional[int] = None
    chunk_size: typing.Optional[int] = None
    version: int = 1

    def to_dict(self) -> dict[str, typing.Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, typing.Any]) -> "FileTransferState":
        return cls(
            transfer_type=data["transfer_type"],
            resume_key=data["resume_key"],
            location_fingerprint=data["location_fingerprint"],
            offset=int(data.get("offset", 0) or 0),
            output_path=data.get("output_path"),
            file_size=data.get("file_size"),
            dc_id=data.get("dc_id"),
            request_size=data.get("request_size"),
            chunk_size=data.get("chunk_size"),
            version=int(data.get("version", 1) or 1),
        )


class JsonTransferStateStore:
    def __init__(self, path):
        self.path = pathlib.Path(path)

    def _read(self) -> dict[str, typing.Any]:
        if not self.path.exists():
            return {"version": 1, "transfers": {}}

        with self.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        if not isinstance(data, dict):
            raise ValueError("transfer state store must be a JSON object")

        transfers = data.get("transfers")
        if transfers is None:
            transfers = {}
        if not isinstance(transfers, dict):
            raise ValueError("transfer state store 'transfers' must be a JSON object")

        data["transfers"] = transfers
        return data

    def _write(self, data: dict[str, typing.Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_name(f"{self.path.name}.tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        tmp_path.replace(self.path)

    def load(self, key: str) -> typing.Optional[FileTransferState]:
        data = self._read()
        raw = data["transfers"].get(key)
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise ValueError("transfer state entry must be a JSON object")
        return FileTransferState.from_dict(raw)

    def save(self, key: str, state: FileTransferState) -> FileTransferState:
        data = self._read()
        data["transfers"][key] = state.to_dict()
        self._write(data)
        return state

    def delete(self, key: str) -> None:
        data = self._read()
        removed = data["transfers"].pop(key, None)
        if data["transfers"]:
            if removed is not None or self.path.exists():
                self._write(data)
        elif self.path.exists():
            self.path.unlink()
