from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from vendor.searxng_source import build_backend


def _archive_bytes(*members: tuple[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in members:
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def test_backend_pins_the_approved_upstream_commit() -> None:
    assert build_backend.UPSTREAM_REF == "c19d86faa"
    assert build_backend.UPSTREAM_ARCHIVE_URL.endswith("/c19d86faa")


def test_extract_archive_returns_single_upstream_root(tmp_path: Path) -> None:
    payload = _archive_bytes(
        ("searxng-c19d86faa/setup.py", b"from setuptools import setup\n"),
        ("searxng-c19d86faa/searx/__init__.py", b""),
    )

    source_root = build_backend.extract_upstream_archive(payload, tmp_path)

    assert source_root == tmp_path / "searxng-c19d86faa"
    assert (source_root / "setup.py").is_file()


def test_extract_archive_rejects_path_traversal(tmp_path: Path) -> None:
    payload = _archive_bytes(("../escaped.txt", b"nope"))

    with pytest.raises(RuntimeError, match="unsafe path"):
        build_backend.extract_upstream_archive(payload, tmp_path)


def test_call_hook_executes_inside_upstream_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    observed: dict[str, object] = {}

    def fake_prepare() -> Path:
        return source_root

    def fake_hook(value: str) -> str:
        observed["cwd"] = Path.cwd()
        observed["value"] = value
        return "wheel.whl"

    monkeypatch.setattr(build_backend, "prepare_upstream_source", fake_prepare)

    result = build_backend.call_upstream_hook(fake_hook, "wheel-dir")

    assert result == "wheel.whl"
    assert observed == {"cwd": source_root, "value": "wheel-dir"}
