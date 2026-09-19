"""Named CMO theaters mapped to 1° bounding boxes.

Boxes are closed on all sides and slightly generous so a scenario near the
edge still gets neighbouring tiles. They are *not* the entire planet — the
official texture host asks players to download only the area they need.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from .tiles import Tile, tiles_from_bbox, unique_tiles


@dataclass(frozen=True)
class Theater:
    key: str
    name: str
    south: float
    west: float
    north: float
    east: float
    description: str = ""

    @property
    def bbox(self) -> tuple:
        return (self.south, self.west, self.north, self.east)

    def tiles(self) -> List[Tile]:
        return tiles_from_bbox(self.south, self.west, self.north, self.east)

    @property
    def tile_count(self) -> int:
        return len(self.tiles())


def _t(
    key: str,
    name: str,
    south: float,
    west: float,
    north: float,
    east: float,
    description: str,
) -> Theater:
    return Theater(key, name, south, west, north, east, description)


# Keys stay stable; they are CLI flags. Keep regions compact so a default
# download stays within the publisher's "only what you need" request.
_THEATER_LIST: List[Theater] = [
    _t("taiwan", "Taiwan Strait", 21.0, 117.0, 27.0, 124.0, "Taiwan, strait, and opposite coast"),
    _t("korea", "Korean Peninsula", 33.0, 123.0, 43.0, 132.0, "ROK, DPRK, and Yellow Sea approaches"),
    _t("japan-south", "Southern Japan", 30.0, 128.0, 36.0, 142.0, "Kyushu, Shikoku, Kanto, Nansei"),
    _t("hokkaido", "Hokkaido / Kuriles", 40.0, 139.0, 46.0, 151.0, "Hokkaido and southern Kuril Islands"),
    _t("scs-north", "Northern South China Sea", 15.0, 108.0, 24.0, 122.0, "Paracels, Hainan, Luzon Strait"),
    _t("spratly", "Spratly Islands", 6.0, 111.0, 13.0, 119.0, "Southern SCS / Spratly area"),
    _t("philippines", "Philippines", 5.0, 117.0, 20.0, 127.0, "Philippine archipelago"),
    _t("malacca", "Malacca Strait", -6.0, 95.0, 8.0, 108.0, "Malacca, Singapore, and approaches"),
    _t("guam", "Guam / Marianas", 12.0, 143.0, 22.0, 147.0, "Guam and Northern Marianas"),
    _t("hormuz", "Strait of Hormuz", 24.0, 54.0, 28.0, 59.0, "Hormuz and Gulf of Oman entrance"),
    _t("persian-gulf", "Persian Gulf", 23.0, 47.0, 32.0, 58.0, "Gulf, Zagros coast, and Strait of Hormuz"),
    _t("red-sea", "Red Sea", 12.0, 32.0, 30.0, 44.0, "Red Sea, Bab el-Mandeb, and Sinai"),
    _t("levant", "Levant", 31.0, 32.0, 38.0, 43.0, "Eastern Med, Syria, Israel, Lebanon"),
    _t("black-sea", "Black Sea", 40.0, 27.0, 48.0, 42.0, "Black Sea and Turkish Straits"),
    _t("ukraine", "Ukraine", 44.0, 22.0, 53.0, 41.0, "Ukraine and northern Black Sea"),
    _t("baltic", "Baltic Sea", 53.0, 10.0, 66.0, 31.0, "Baltic, Gotland, and Gulf of Finland"),
    _t("giuk", "GIUK Gap", 60.0, -25.0, 67.0, 2.0, "Greenland–Iceland–UK gap"),
    _t("iceland", "Iceland", 63.0, -25.0, 67.0, -13.0, "Iceland and Denmark Strait"),
    _t("norway", "North Norway / Barents", 63.0, 5.0, 72.0, 25.0, "North Norway and Barents approaches"),
    _t("uk-north", "Northern UK", 54.0, -11.0, 62.0, 2.0, "Scotland, GIUK southern edge"),
    _t("gibraltar", "Gibraltar / W Med", 34.0, -10.0, 38.0, 2.0, "Strait of Gibraltar and Alboran"),
    _t("med-central", "Central Mediterranean", 30.0, 8.0, 42.0, 20.0, "Italy, Sicily, Libya, Tunisia"),
    _t("falklands", "Falkland Islands", -56.0, -63.0, -50.0, -53.0, "Falklands / Malvinas"),
    _t("hawaii", "Hawaii", 18.0, -161.0, 23.0, -154.0, "Hawaiian Islands"),
    _t("california", "US West Coast South", 32.0, -126.0, 38.0, -116.0, "Southern/central California approaches"),
    _t("caribbean", "Caribbean / Venezuela", 8.0, -72.0, 18.0, -59.0, "Southern Caribbean and Venezuela"),
    _t("india-west", "Arabian Sea / West India", 8.0, 66.0, 25.0, 78.0, "Western India and Arabian Sea"),
    _t("india-east", "Bay of Bengal", 5.0, 78.0, 23.0, 95.0, "Eastern India, Bangladesh, Andaman"),
    _t("okinawa", "Okinawa / Ryukyu", 24.0, 122.0, 28.0, 132.0, "Okinawa and Ryukyu chain"),
    _t("aden", "Gulf of Aden", 11.0, 42.0, 16.0, 54.0, "Bab el-Mandeb, Aden, and north Somalia"),
    _t("suwalki", "Suwalki Gap", 52.0, 20.0, 56.0, 26.0, "Suwalki corridor and Kaliningrad approaches"),
]

THEATERS: Dict[str, Theater] = {t.key: t for t in _THEATER_LIST}


def get_theater(key: str) -> Theater:
    theater = THEATERS.get(key.lower().strip())
    if theater is None:
        known = ", ".join(sorted(THEATERS))
        raise KeyError(f"unknown theater {key!r}. Choose one of: {known}")
    return theater


def theaters_from_keys(keys: Iterable[str]) -> List[Theater]:
    return [get_theater(k) for k in keys]


def tiles_for_theaters(keys: Iterable[str]) -> List[Tile]:
    tiles: List[Tile] = []
    for theater in theaters_from_keys(keys):
        tiles.extend(theater.tiles())
    return unique_tiles(tiles)


def find_theaters(query: Optional[str] = None) -> List[Theater]:
    if not query:
        return list(_THEATER_LIST)
    needle = query.lower()
    return [
        t
        for t in _THEATER_LIST
        if needle in t.key or needle in t.name.lower() or needle in t.description.lower()
    ]
