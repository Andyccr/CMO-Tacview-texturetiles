from __future__ import annotations

from pathlib import Path

from cmo_tacview_tiles.config import load_config, overlay_config
from cmo_tacview_tiles.constants import DEFAULT_OUTPUT_DIR, DEFAULT_WORKERS


def test_load_config_ini(tmp_path: Path, monkeypatch) -> None:
    ini = tmp_path / "cmo-tacview-tiles.ini"
    ini.write_text(
        "[defaults]\n"
        "output = /tmp/tiles\n"
        "workers = 2\n"
        "theater = hormuz\n"
        "delay = 0.25\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg.output == "/tmp/tiles"
    assert cfg.workers == 2
    assert cfg.theater == "hormuz"
    assert cfg.delay == 0.25
    assert cfg.path.resolve() == ini.resolve()


def test_overlay_replaces_defaults() -> None:
    class Args:
        output = DEFAULT_OUTPUT_DIR
        workers = DEFAULT_WORKERS
        timeout = 30.0
        retries = 3
        base_url = "https://warfaresims.slitherine.com/Tacview_Textures/"
        max_tiles = 400
        delay = 0.0

    from cmo_tacview_tiles.config import AppConfig

    overlay_config(
        Args,
        AppConfig(output="/data/tex", workers=8, theater="taiwan"),
    )
    assert Args.output == "/data/tex"
    assert Args.workers == 8
    assert Args.config_theater == "taiwan"
