from __future__ import annotations

import json
from pathlib import Path

import pytest

from cmo_tacview_tiles.cli import main
from tests.helpers import make_webp


def test_version() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0


def test_theaters_json(capsys) -> None:
    assert main(["theaters", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    keys = {row["key"] for row in payload}
    assert "taiwan" in keys
    assert payload[0]["tiles"] > 0


def test_list_theater(capsys) -> None:
    assert main(["list", "--theater", "hormuz"]) == 0
    out = capsys.readouterr().out
    assert "N24E054.webp" in out
    assert "tile(s)" in out


def test_list_requires_selection(capsys) -> None:
    assert main(["list"]) == 2
    assert "select tiles" in capsys.readouterr().err


def test_download_limit_from_local_server(tile_server, tmp_path: Path, capsys) -> None:
    code = main(
        [
            "download",
            "--tiles",
            "N25E121,N99E001",
            "--output",
            str(tmp_path),
            "--base-url",
            tile_server.base_url,
            "--workers",
            "2",
            "--retries",
            "0",
            "--yes",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "downloaded=1" in captured.out
    assert "missing=1" in captured.out
    assert (tmp_path / "N25E121.webp").exists()


def test_download_refuses_over_max_tiles(capsys) -> None:
    code = main(
        [
            "download",
            "--bbox",
            "0,0,20,30",
            "--max-tiles",
            "10",
            "--dry-run",
        ]
    )
    assert code == 2
    assert "exceeds --max-tiles" in capsys.readouterr().err


def test_install_copies(tmp_path: Path, capsys) -> None:
    source = tmp_path / "src"
    dest = tmp_path / "dest"
    source.mkdir()
    (source / "N25E121.webp").write_bytes(make_webp(512))
    (source / "readme.txt").write_text("ignore")
    code = main(
        ["install", "--source", str(source), "--target", str(dest)]
    )
    assert code == 0
    assert (dest / "N25E121.webp").exists()
    assert not (dest / "readme.txt").exists()
    assert "copied=1" in capsys.readouterr().out


def test_unknown_theater(capsys) -> None:
    assert main(["list", "--theater", "atlantis"]) == 2
    assert "unknown theater" in capsys.readouterr().err
