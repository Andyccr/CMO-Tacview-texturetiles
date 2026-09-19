from __future__ import annotations

from pathlib import Path

from cmo_tacview_tiles.catalog import Catalog, scan_local, verify_files
from cmo_tacview_tiles.constants import CATALOG_FILENAME
from cmo_tacview_tiles.downloader import download_tiles
from cmo_tacview_tiles.tiles import parse_tile_name
from tests.helpers import make_webp


def test_catalog_roundtrip(tmp_path: Path) -> None:
    catalog = Catalog.load(tmp_path)
    catalog.record(parse_tile_name("N25E121"), "ok", size=1024, etag='"abc"')
    catalog.record(parse_tile_name("N10E010"), "missing")
    catalog.save()
    assert (tmp_path / CATALOG_FILENAME).is_file()
    loaded = Catalog.load(tmp_path)
    assert loaded.get(parse_tile_name("N25E121")).bytes == 1024
    assert loaded.is_known_missing(parse_tile_name("N10E010"))
    assert loaded.failed_tiles() == []


def test_skip_known_missing_avoids_http(tile_server, tmp_path: Path) -> None:
    catalog = Catalog.load(tmp_path)
    missing = parse_tile_name("N10E010")
    catalog.record(missing, "missing")
    before = len(tile_server.requests)
    summary = download_tiles(
        [missing],
        tmp_path,
        base_url=tile_server.base_url,
        retries=0,
        catalog=catalog,
        skip_known_missing=True,
    )
    assert summary.missing == 1
    assert summary.results[0].cached is True
    assert len(tile_server.requests) == before


def test_trust_local_skips_without_head(tile_server, tmp_path: Path) -> None:
    tile = parse_tile_name("N25E121")
    dest = tmp_path / tile.filename
    dest.write_bytes(make_webp(1024, b"A"))
    before = len(tile_server.requests)
    summary = download_tiles(
        [tile],
        tmp_path,
        base_url=tile_server.base_url,
        retries=0,
        trust_local=True,
    )
    assert summary.skipped == 1
    assert len(tile_server.requests) == before


def test_scan_and_verify(tmp_path: Path) -> None:
    good = tmp_path / "N25E121.webp"
    good.write_bytes(make_webp(400))
    bad = tmp_path / "N25E122.webp"
    bad.write_bytes(b"not-a-webp-file-but-long-enough-to-pass-size")
    found = scan_local(tmp_path)
    assert "N25E121" in found
    issues = verify_files(tmp_path)
    assert any(i.name == "N25E122" for i in issues)
    assert not any(i.name == "N25E121" for i in issues)
