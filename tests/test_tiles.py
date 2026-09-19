from __future__ import annotations

from pathlib import Path

import pytest

from cmo_tacview_tiles.tiles import (
    Tile,
    TileError,
    parse_bbox,
    parse_tile_list,
    parse_tile_name,
    tiles_from_bbox,
)


def test_parse_tile_name_variants() -> None:
    assert parse_tile_name("N25E121") == Tile(25, 121)
    assert parse_tile_name("n25e121.webp") == Tile(25, 121)
    assert parse_tile_name("S09W070") == Tile(-9, -70)
    assert parse_tile_name("N00E000") == Tile(0, 0)
    assert parse_tile_name("S51W060.png") == Tile(-51, -60)


def test_tile_filename_and_url() -> None:
    tile = Tile(25, 121)
    assert tile.name == "N25E121"
    assert tile.filename == "N25E121.webp"
    assert tile.url("https://example.test/Tacview_Textures") == (
        "https://example.test/Tacview_Textures/N25E121.webp"
    )


def test_invalid_tile_name() -> None:
    with pytest.raises(TileError):
        parse_tile_name("Taiwan")
    with pytest.raises(TileError):
        parse_tile_name("N2E12")
    with pytest.raises(TileError):
        Tile(95, 0)


def test_bbox_taiwan_strait() -> None:
    tiles = tiles_from_bbox(21, 117, 27, 124)
    names = {t.name for t in tiles}
    assert "N21E117" in names
    assert "N27E124" in names
    assert "N25E121" in names
    assert len(tiles) == 7 * 8  # 21..27 × 117..124 inclusive


def test_bbox_single_cell() -> None:
    tiles = tiles_from_bbox(25.2, 121.1, 25.8, 121.9)
    assert [t.name for t in tiles] == ["N25E121"]


def test_bbox_fractional_edges() -> None:
    tiles = tiles_from_bbox(24.1, 120.0, 26.0, 122.0)
    assert [t.name for t in tiles] == [
        "N24E120",
        "N24E121",
        "N24E122",
        "N25E120",
        "N25E121",
        "N25E122",
        "N26E120",
        "N26E121",
        "N26E122",
    ]


def test_bbox_antimeridian_wrap() -> None:
    tiles = tiles_from_bbox(-2, 179, 0, -179)
    names = [t.name for t in tiles]
    assert "S02E179" in names
    assert "N00W179" in names
    assert "N00W180" in names
    assert "S01E179" in names
    # Should not include the long way around (E000 etc.)
    assert "N00E000" not in names
    assert len(tiles) == 3 * 3  # lat -2..0, lon 179, -180, -179


def test_bbox_western_hemisphere() -> None:
    tiles = tiles_from_bbox(7, -70, 7, -70)
    assert [t.name for t in tiles] == ["N07W070"]


def test_bbox_rejects_south_gt_north() -> None:
    with pytest.raises(TileError):
        tiles_from_bbox(10, 0, 0, 1)


def test_bbox_rejects_full_world() -> None:
    with pytest.raises(TileError, match="entire planet"):
        tiles_from_bbox(-90, -180, 89, 179.0 + 360)


def test_parse_bbox_and_list() -> None:
    assert parse_bbox("21,117,27,124") == (21.0, 117.0, 27.0, 124.0)
    with pytest.raises(TileError):
        parse_bbox("21,117,27")
    tiles = parse_tile_list(["N25E121, N25E122", "S09W070"])
    assert [t.name for t in tiles] == ["S09W070", "N25E121", "N25E122"]


def test_expand_tiles_pad_one() -> None:
    from cmo_tacview_tiles.tiles import expand_tiles

    tiles = expand_tiles([parse_tile_name("N25E121")], 1)
    assert len(tiles) == 9
    assert parse_tile_name("N24E120") in tiles
    assert parse_tile_name("N26E122") in tiles


def test_expand_tiles_antimeridian() -> None:
    from cmo_tacview_tiles.tiles import expand_tiles

    tiles = expand_tiles([parse_tile_name("N00E179")], 1)
    names = {t.name for t in tiles}
    assert "N00W180" in names
    assert "N00E178" in names


def test_tiles_from_file(tmp_path: Path) -> None:
    from cmo_tacview_tiles.tiles import tiles_from_file

    path = tmp_path / "tiles.txt"
    path.write_text("# comment\nN25E121\nN25E122.webp\n\n")
    tiles = tiles_from_file(path)
    assert [t.name for t in tiles] == ["N25E121", "N25E122"]
