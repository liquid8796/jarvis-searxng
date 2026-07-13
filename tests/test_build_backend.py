from __future__ import annotations

import importlib
import importlib.machinery
import io
import sys
import tarfile
import zipfile
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


def _archive_bytes_with_link(
    *,
    link_name: str,
    link_target: str,
) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        setup = tarfile.TarInfo(name="searxng-c19d86faa/setup.py")
        setup_content = b"from setuptools import setup\n"
        setup.size = len(setup_content)
        archive.addfile(setup, io.BytesIO(setup_content))

        package = tarfile.TarInfo(name="searxng-c19d86faa/searx/__init__.py")
        package.size = 0
        archive.addfile(package, io.BytesIO(b""))

        target = tarfile.TarInfo(
            name="searxng-c19d86faa/utils/templates/etc/apache2.conf"
        )
        target_content = b"Listen 8080\n"
        target.size = len(target_content)
        archive.addfile(target, io.BytesIO(target_content))

        link = tarfile.TarInfo(name=link_name)
        link.type = tarfile.SYMTYPE
        link.linkname = link_target
        archive.addfile(link)
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


def test_extract_archive_accepts_safe_internal_symlink(tmp_path: Path) -> None:
    payload = _archive_bytes_with_link(
        link_name="searxng-c19d86faa/utils/templates/etc/apache2",
        link_target="apache2.conf",
    )

    source_root = build_backend.extract_upstream_archive(payload, tmp_path)

    extracted_link = source_root / "utils/templates/etc/apache2"
    assert extracted_link.is_symlink()
    assert extracted_link.resolve() == (
        source_root / "utils/templates/etc/apache2.conf"
    ).resolve()


def test_extract_archive_rejects_symlink_outside_source_root(tmp_path: Path) -> None:
    payload = _archive_bytes_with_link(
        link_name="searxng-c19d86faa/utils/templates/etc/apache2",
        link_target="../../../../../escaped.conf",
    )

    with pytest.raises(RuntimeError, match="unsafe link"):
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


def test_call_hook_exposes_absolute_source_path_when_dot_cache_is_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_root = tmp_path / "source"
    package_root = source_root / "searx_build_fixture"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text(
        "VALUE = 'loaded'\n", encoding="utf-8"
    )

    stale_root = tmp_path / "stale"
    stale_root.mkdir()
    stale_finder = importlib.machinery.FileFinder(
        str(stale_root),
        (
            importlib.machinery.SourceFileLoader,
            importlib.machinery.SOURCE_SUFFIXES,
        ),
    )

    original_sys_path = list(sys.path)
    original_dot_finder = sys.path_importer_cache.get(".")
    sys.path_importer_cache["."] = stale_finder
    sys.modules.pop("searx_build_fixture", None)

    monkeypatch.setattr(
        build_backend, "prepare_upstream_source", lambda: source_root
    )

    def upstream_like_hook() -> str:
        # The pinned SearXNG setup.py prepends a relative dot. Under uv's
        # isolated backend, that dot can retain a FileFinder for the wrapper
        # directory from sys.path_importer_cache.
        sys.path = ["."] + sys.path
        module = importlib.import_module("searx_build_fixture")
        return module.VALUE

    try:
        assert build_backend.call_upstream_hook(upstream_like_hook) == "loaded"
        assert sys.path == original_sys_path
    finally:
        sys.modules.pop("searx_build_fixture", None)
        if original_dot_finder is None:
            sys.path_importer_cache.pop(".", None)
        else:
            sys.path_importer_cache["."] = original_dot_finder
        sys.path[:] = original_sys_path


def test_setuptools_hook_imports_upstream_searx_with_stale_dot_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_root = tmp_path / "source"
    package_root = source_root / "searx"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "version.py").write_text(
        "VERSION_TAG = '2026.7.13'\n", encoding="utf-8"
    )
    (source_root / "setup.py").write_text(
        "import sys\n"
        "sys.path = ['.'] + sys.path\n"
        "from setuptools import find_packages, setup\n"
        "from searx.version import VERSION_TAG\n"
        "setup(name='searxng-fixture', version=VERSION_TAG, "
        "packages=find_packages())\n",
        encoding="utf-8",
    )

    stale_root = tmp_path / "stale"
    stale_root.mkdir()
    stale_finder = importlib.machinery.FileFinder(
        str(stale_root),
        (
            importlib.machinery.SourceFileLoader,
            importlib.machinery.SOURCE_SUFFIXES,
        ),
    )

    original_dot_finder = sys.path_importer_cache.get(".")
    sys.path_importer_cache["."] = stale_finder
    sys.modules.pop("searx.version", None)
    sys.modules.pop("searx", None)
    monkeypatch.setattr(
        build_backend, "prepare_upstream_source", lambda: source_root
    )

    try:
        requirements = build_backend.get_requires_for_build_wheel({})
        assert isinstance(requirements, list)
    finally:
        sys.modules.pop("searx.version", None)
        sys.modules.pop("searx", None)
        if original_dot_finder is None:
            sys.path_importer_cache.pop(".", None)
        else:
            sys.path_importer_cache["."] = original_dot_finder


def test_prepare_upstream_source_generates_frozen_runtime_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = _archive_bytes(
        ("searxng-c19d86faa/setup.py", b"from setuptools import setup\n"),
        ("searxng-c19d86faa/searx/__init__.py", b""),
        (
            "searxng-c19d86faa/searx/version.py",
            b"import importlib\n"
            b"vf = importlib.import_module('searx.version_frozen')\n"
            b"VERSION_STRING = vf.VERSION_STRING\n",
        ),
    )

    monkeypatch.setattr(build_backend, "download_upstream_archive", lambda: payload)
    monkeypatch.setattr(
        build_backend.tempfile,
        "TemporaryDirectory",
        lambda **_: _FixedTemporaryDirectory(tmp_path / "build"),
    )
    monkeypatch.setattr(build_backend, "_BUILD_DIRECTORY", None)
    monkeypatch.setattr(build_backend, "_PREPARED_SOURCE", None)

    source_root = build_backend.prepare_upstream_source()
    frozen_path = source_root / "searx/version_frozen.py"

    assert frozen_path.is_file()
    namespace: dict[str, str] = {}
    exec(frozen_path.read_text(encoding="utf-8"), namespace)
    assert namespace["VERSION_TAG"] == "0.0.0+c19d86faa"
    assert namespace["GIT_BRANCH"] == "c19d86faa"


class _FixedTemporaryDirectory:
    def __init__(self, path: Path) -> None:
        self.name = str(path)
        path.mkdir(parents=True, exist_ok=True)

    def cleanup(self) -> None:
        return None


def test_built_wheel_contains_frozen_version_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_root = tmp_path / "source"
    package_root = source_root / "searx"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "version.py").write_text(
        "import importlib\n"
        "vf = importlib.import_module('searx.version_frozen')\n"
        "VERSION_TAG = vf.VERSION_TAG\n",
        encoding="utf-8",
    )
    (source_root / "setup.py").write_text(
        "from setuptools import find_packages, setup\n"
        "from searx.version import VERSION_TAG\n"
        "setup(name='searxng', version=VERSION_TAG, packages=find_packages())\n",
        encoding="utf-8",
    )
    build_backend.write_frozen_version(source_root)
    monkeypatch.setattr(
        build_backend, "prepare_upstream_source", lambda: source_root
    )

    wheel_directory = tmp_path / "wheel"
    wheel_directory.mkdir()
    wheel_name = build_backend.build_wheel(str(wheel_directory))

    with zipfile.ZipFile(wheel_directory / wheel_name) as wheel:
        names = set(wheel.namelist())
    assert "searx/version_frozen.py" in names
