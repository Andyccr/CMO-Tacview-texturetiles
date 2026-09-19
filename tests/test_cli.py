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


def test_theaters_query(capsys) -> None:
    assert main(["theaters", "hormuz"]) == 0
    out = capsys.readouterr().out
    assert "hormuz" in out
    assert "Strait of Hormuz" in out
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
            "N25E121,N10E010",
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


def test_bbox_accepts_leading_minus(capsys) -> None:
    assert main(["list", "--bbox", "-2,-70,1,-68"]) == 0
    out = capsys.readouterr().out
    assert "S02W070.webp" in out
    assert "N01W068.webp" in out


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


def test_probe_local_server(tile_server, capsys) -> None:
    code = main(
        [
            "probe",
            "N25E121",
            "N10E010",
            "--base-url",
            tile_server.base_url,
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "N25E121" in out
    assert "ok" in out
    assert "missing" in out


def test_unknown_theater(capsys) -> None:
    assert main(["list", "--theater", "atlantis"]) == 2
    assert "unknown theater" in capsys.readouterr().err


def test_status_and_verify(tmp_path: Path, capsys) -> None:
    (tmp_path / "N24E054.webp").write_bytes(make_webp(400))
    assert main(["status", "--theater", "hormuz", "-o", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "present=1" in out
    assert "planned=" in out
    assert main(["verify", "-o", str(tmp_path), "--json"]) == 0


def test_list_pad(capsys) -> None:
    assert main(["list", "--tiles", "N25E121", "--pad", "1", "--json"]) == 0
    names = json.loads(capsys.readouterr().out)
    assert len(names) == 9


def test_download_json_and_catalog(tile_server, tmp_path: Path, capsys) -> None:
    from cmo_tacview_tiles.constants import CATALOG_FILENAME

    code = main(
        [
            "download",
            "--tiles",
            "N25E121,N10E010",
            "--output",
            str(tmp_path),
            "--base-url",
            tile_server.base_url,
            "--retries",
            "0",
            "--yes",
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["downloaded"] == 1
    assert payload["missing"] == 1
    assert (tmp_path / CATALOG_FILENAME).is_file()
    # second run should use the catalog for the 404
    before = len(tile_server.requests)
    assert (
        main(
            [
                "download",
                "--tiles",
                "N10E010",
                "--output",
                str(tmp_path),
                "--base-url",
                tile_server.base_url,
                "--retries",
                "0",
                "--yes",
                "-q",
            ]
        )
        == 0
    )
    assert "cached" in capsys.readouterr().out
    assert len(tile_server.requests) == before


def test_sync_skips_local(tile_server, tmp_path: Path, capsys) -> None:
    (tmp_path / "N25E121.webp").write_bytes(make_webp(1024, b"A"))
    code = main(
        [
            "sync",
            "--tiles",
            "N25E121,N10E010",
            "--output",
            str(tmp_path),
            "--base-url",
            tile_server.base_url,
            "--retries",
            "0",
            "--yes",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "pending of 2" in out
    assert (tmp_path / "N25E121.webp").exists()


def test_clean_partials(tmp_path: Path, capsys) -> None:
    part = tmp_path / "N25E121.webp.part"
    part.write_bytes(b"partial")
    assert main(["clean", "-o", str(tmp_path)]) == 0
    assert not part.exists()
    assert "removed" in capsys.readouterr().out


def test_doctor_local_host(tile_server, tmp_path: Path, capsys) -> None:
    code = main(
        [
            "doctor",
            "-o",
            str(tmp_path),
            "--base-url",
            tile_server.base_url,
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "host" in out
    assert "ok" in out


def test_list_uses_config_theater(tmp_path: Path, capsys) -> None:
    ini = tmp_path / "cfg.ini"
    ini.write_text("[defaults]\ntheater = hormuz\n", encoding="utf-8")
    assert main(["list", "--config", str(ini), "--json"]) == 0
    names = json.loads(capsys.readouterr().out)
    assert "N24E054" in names
