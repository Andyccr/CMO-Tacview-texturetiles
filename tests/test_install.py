from __future__ import annotations

from pathlib import Path

from cmo_tacview_tiles.install import install_textures, list_texture_files
from tests.helpers import make_webp


def test_install_and_skip(tmp_path: Path) -> None:
    source = tmp_path / "in"
    target = tmp_path / "out"
    source.mkdir()
    payload = make_webp(400)
    (source / "N25E121.webp").write_bytes(payload)
    (source / "N25E121.webp.part").write_bytes(b"partial")
    summary = install_textures(source, [target])
    assert summary.copied == 1
    assert (target / "N25E121.webp").read_bytes() == payload
    assert not (target / "N25E121.webp.part").exists()

    summary2 = install_textures(source, [target], overwrite=False)
    assert summary2.skipped == 1


def test_list_texture_files_requires_dir(tmp_path: Path) -> None:
    try:
        list_texture_files(tmp_path / "missing")
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError")
