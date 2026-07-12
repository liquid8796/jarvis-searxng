from __future__ import annotations

import io
import os
import posixpath
import tarfile
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any, TypeVar

from setuptools import build_meta as _setuptools_backend

UPSTREAM_REF = "c19d86faa"
UPSTREAM_ARCHIVE_URL = (
    "https://codeload.github.com/searxng/searxng/tar.gz/" + UPSTREAM_REF
)
_DOWNLOAD_TIMEOUT_SECONDS = 120
_USER_AGENT = "searxng-vercel-build-wrapper/1.0"

_Result = TypeVar("_Result")
_BUILD_DIRECTORY: tempfile.TemporaryDirectory[str] | None = None
_PREPARED_SOURCE: Path | None = None


def _validate_member(member: tarfile.TarInfo) -> None:
    path = PurePosixPath(member.name)
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"SearXNG archive contains an unsafe path: {member.name}")

    if not (member.issym() or member.islnk()):
        return

    link = PurePosixPath(member.linkname)
    if link.is_absolute():
        raise RuntimeError(f"SearXNG archive contains an unsafe link: {member.name}")

    # Symbolic-link targets are relative to the link's parent directory.
    # Hard-link targets in a tar archive are relative to the archive root.
    link_base = path.parent if member.issym() else PurePosixPath()
    resolved_link = PurePosixPath(posixpath.normpath(str(link_base / link)))
    archive_root = path.parts[0] if path.parts else ""
    if (
        resolved_link.is_absolute()
        or ".." in resolved_link.parts
        or not resolved_link.parts
        or resolved_link.parts[0] != archive_root
    ):
        raise RuntimeError(f"SearXNG archive contains an unsafe link: {member.name}")


def extract_upstream_archive(payload: bytes, destination: Path) -> Path:
    """Extract an upstream tarball and return its single source root."""
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        members = archive.getmembers()
        if not members:
            raise RuntimeError("Downloaded SearXNG archive is empty")
        for member in members:
            _validate_member(member)
        archive.extractall(destination, members=members, filter="data")

    roots = {
        PurePosixPath(member.name).parts[0]
        for member in members
        if PurePosixPath(member.name).parts
    }
    if len(roots) != 1:
        raise RuntimeError("SearXNG archive must contain exactly one source root")

    source_root = destination / roots.pop()
    if not (source_root / "setup.py").is_file() or not (
        source_root / "searx"
    ).is_dir():
        raise RuntimeError("Downloaded archive is not a valid SearXNG source tree")
    return source_root


def download_upstream_archive() -> bytes:
    request = urllib.request.Request(
        UPSTREAM_ARCHIVE_URL,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/gzip"},
    )
    try:
        with urllib.request.urlopen(
            request, timeout=_DOWNLOAD_TIMEOUT_SECONDS
        ) as response:
            return response.read()
    except OSError as exc:
        raise RuntimeError(
            f"Unable to download pinned SearXNG source {UPSTREAM_REF}: {exc}"
        ) from exc


def prepare_upstream_source() -> Path:
    global _BUILD_DIRECTORY, _PREPARED_SOURCE
    if _PREPARED_SOURCE is not None:
        return _PREPARED_SOURCE

    _BUILD_DIRECTORY = tempfile.TemporaryDirectory(prefix="searxng-vercel-build-")
    destination = Path(_BUILD_DIRECTORY.name)
    _PREPARED_SOURCE = extract_upstream_archive(
        download_upstream_archive(), destination
    )
    return _PREPARED_SOURCE


def call_upstream_hook(
    hook: Callable[..., _Result], *args: Any, **kwargs: Any
) -> _Result:
    source_root = prepare_upstream_source()
    previous_directory = Path.cwd()
    try:
        os.chdir(source_root)
        return hook(*args, **kwargs)
    finally:
        os.chdir(previous_directory)


def get_requires_for_build_wheel(
    config_settings: dict[str, Any] | None = None,
) -> list[str]:
    return call_upstream_hook(
        _setuptools_backend.get_requires_for_build_wheel, config_settings
    )


def prepare_metadata_for_build_wheel(
    metadata_directory: str,
    config_settings: dict[str, Any] | None = None,
) -> str:
    return call_upstream_hook(
        _setuptools_backend.prepare_metadata_for_build_wheel,
        metadata_directory,
        config_settings,
    )


def build_wheel(
    wheel_directory: str,
    config_settings: dict[str, Any] | None = None,
    metadata_directory: str | None = None,
) -> str:
    return call_upstream_hook(
        _setuptools_backend.build_wheel,
        wheel_directory,
        config_settings,
        metadata_directory,
    )


def get_requires_for_build_sdist(
    config_settings: dict[str, Any] | None = None,
) -> list[str]:
    return call_upstream_hook(
        _setuptools_backend.get_requires_for_build_sdist, config_settings
    )


def build_sdist(
    sdist_directory: str,
    config_settings: dict[str, Any] | None = None,
) -> str:
    return call_upstream_hook(
        _setuptools_backend.build_sdist, sdist_directory, config_settings
    )
