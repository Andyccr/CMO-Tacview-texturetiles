from __future__ import annotations

from pathlib import Path

from cmo_tacview_tiles.downloader import download_one, download_tiles
from cmo_tacview_tiles.tiles import parse_tile_name
from tests.helpers import make_webp


def test_download_ok_and_missing(tile_server, tmp_path: Path) -> None:
    summary = download_tiles(
        [parse_tile_name("N25E121"), parse_tile_name("N99E001")],
        tmp_path,
        base_url=tile_server.base_url,
        workers=2,
        retries=0,
    )
    assert summary.ok == 1
    assert summary.missing == 1
    assert summary.failed == 0
    dest = tmp_path / "N25E121.webp"
    assert dest.exists()
    assert dest.stat().st_size == 1024
    assert dest.read_bytes()[:4] == b"RIFF"


def test_skip_existing_matching_size(tile_server, tmp_path: Path) -> None:
    tile = parse_tile_name("N25E122")
    dest = tmp_path / tile.filename
    dest.write_bytes(make_webp(2048, b"B"))
    before = dest.stat().st_mtime
    summary = download_tiles(
        [tile],
        tmp_path,
        base_url=tile_server.base_url,
        retries=0,
    )
    assert summary.skipped == 1
    assert dest.stat().st_mtime == before


def test_force_redownload(tile_server, tmp_path: Path) -> None:
    tile = parse_tile_name("N25E121")
    dest = tmp_path / tile.filename
    dest.write_bytes(make_webp(1024, b"ZZ"))
    summary = download_tiles(
        [tile],
        tmp_path,
        base_url=tile_server.base_url,
        force=True,
        retries=0,
    )
    assert summary.ok == 1
    assert dest.read_bytes()[12:13] == b"A"


def test_resume_from_partial(tile_server, tmp_path: Path) -> None:
    tile = parse_tile_name("N25E122")
    dest = tmp_path / tile.filename
    part = dest.with_name(dest.name + ".part")
    full = make_webp(2048, b"B")
    part.write_bytes(full[:100])
    result = download_one(
        tile,
        dest,
        base_url=tile_server.base_url,
        retries=0,
        skip_existing=True,
    )
    assert result.status == "ok"
    assert dest.read_bytes() == full
    assert not part.exists()
    ranged = [r for r in tile_server.requests if r[0] == "GET" and r[2]]
    assert ranged, "expected a Range GET for the partial file"


def test_html_payload_is_failure(tile_server, tmp_path: Path) -> None:
    tile_server.html_for.add("N10E010.webp")
    tile = parse_tile_name("N10E010")
    result = download_one(
        tile,
        tmp_path / tile.filename,
        base_url=tile_server.base_url,
        retries=0,
    )
    assert result.status == "fail"
    assert "HTML" in (result.error or "")


def test_dry_run_writes_nothing(tile_server, tmp_path: Path) -> None:
    summary = download_tiles(
        [parse_tile_name("N25E121")],
        tmp_path,
        base_url=tile_server.base_url,
        dry_run=True,
    )
    assert summary.skipped == 1
    assert not (tmp_path / "N25E121.webp").exists()
    assert tile_server.requests == []
