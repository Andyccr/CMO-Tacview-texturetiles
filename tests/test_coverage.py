from __future__ import annotations

from cmo_tacview_tiles.coverage import classify_tile, render_map, tiles_geojson
from cmo_tacview_tiles.tiles import parse_tile_name, tiles_from_bbox


def test_render_map_contains_glyph() -> None:
    tiles = tiles_from_bbox(25, 121, 26, 122)
    states = {
        "N25E121": "present",
        "N25E122": "unpublished",
        "N26E121": "planned",
        "N26E122": "failed",
    }
    grid = render_map(tiles, states)
    assert "#" in grid
    assert "." in grid
    assert "N26" in grid
    assert "E121" in grid


def test_geojson_polygon() -> None:
    tile = parse_tile_name("N25E121")
    geo = tiles_geojson([tile], {"N25E121": "present"})
    assert geo["type"] == "FeatureCollection"
    ring = geo["features"][0]["geometry"]["coordinates"][0]
    assert ring[0] == [121.0, 25.0]
    assert ring[2] == [122.0, 26.0]


def test_classify_prefers_local() -> None:
    tile = parse_tile_name("N10E010")
    assert classify_tile(tile, local={"N10E010": True}, catalog_status="missing") == "present"
    assert classify_tile(tile, catalog_status="missing") == "unpublished"
