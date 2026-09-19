from __future__ import annotations

from cmo_tacview_tiles.constants import DEFAULT_MAX_TILES
from cmo_tacview_tiles.theaters import THEATERS, get_theater, tiles_for_theaters


def test_known_theaters_exist() -> None:
    for key in ("taiwan", "korea", "hormuz", "giuk", "falklands"):
        theater = get_theater(key)
        assert theater.tile_count > 0
        assert theater.tiles()[0].filename.endswith(".webp")


def test_theater_lookup_is_case_insensitive() -> None:
    assert get_theater("Taiwan").key == "taiwan"


def test_every_theater_fits_default_cap() -> None:
    oversized = {
        key: t.tile_count for key, t in THEATERS.items() if t.tile_count > DEFAULT_MAX_TILES
    }
    assert oversized == {}, f"theaters exceed default cap: {oversized}"


def test_merge_theaters_unique() -> None:
    tiles = tiles_for_theaters(["hormuz", "persian-gulf"])
    names = [t.name for t in tiles]
    assert len(names) == len(set(names))
    assert any(n.startswith("N26E056") or n.startswith("N25E056") for n in names)


def test_taiwan_contains_taipei_tile() -> None:
    names = {t.name for t in get_theater("taiwan").tiles()}
    assert "N25E121" in names
