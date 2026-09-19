"""Optional INI config for default output, workers, and theater."""

from __future__ import annotations

import os
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from .constants import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_TILES,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
    DEFAULT_WORKERS,
)

CONFIG_NAMES = (".cmo-tacview-tiles.ini", "cmo-tacview-tiles.ini")


@dataclass
class AppConfig:
    output: Optional[str] = None
    workers: Optional[int] = None
    timeout: Optional[float] = None
    retries: Optional[int] = None
    base_url: Optional[str] = None
    theater: Optional[str] = None
    max_tiles: Optional[int] = None
    delay: Optional[float] = None
    path: Optional[Path] = None


def config_search_paths(explicit: Optional[Path] = None) -> Sequence[Path]:
    if explicit is not None:
        return [Path(explicit)]
    paths = [Path(name) for name in CONFIG_NAMES]
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        paths.append(Path(xdg) / "cmo-tacview-tiles" / "config.ini")
    home = Path.home()
    paths.append(home / ".config" / "cmo-tacview-tiles" / "config.ini")
    env = os.environ.get("CMO_TACVIEW_CONFIG")
    if env:
        paths.insert(0, Path(env))
    return paths


def load_config(explicit: Optional[Path] = None) -> AppConfig:
    parser = ConfigParser()
    for path in config_search_paths(explicit):
        if path.is_file():
            parser.read(path, encoding="utf-8")
            cfg = _from_parser(parser)
            cfg.path = path
            return cfg
    if explicit is not None:
        raise FileNotFoundError(f"config file not found: {explicit}")
    return AppConfig()


def _from_parser(parser: ConfigParser) -> AppConfig:
    section = "defaults" if parser.has_section("defaults") else (
        "download" if parser.has_section("download") else None
    )
    get = (lambda key, fallback=None: parser.get(section, key, fallback=fallback)) if section else (lambda k, fallback=None: fallback)
    getint = (lambda key: parser.getint(section, key) if parser.has_option(section, key) else None) if section else (lambda k: None)
    getfloat = (lambda key: parser.getfloat(section, key) if parser.has_option(section, key) else None) if section else (lambda k: None)

    theater = get("theater")
    return AppConfig(
        output=get("output") or None,
        workers=getint("workers"),
        timeout=getfloat("timeout"),
        retries=getint("retries"),
        base_url=get("base_url") or None,
        theater=theater.strip() if theater else None,
        max_tiles=getint("max_tiles"),
        delay=getfloat("delay"),
    )


def overlay_config(args: object, config: AppConfig) -> None:
    """Fill argparse defaults from config when the user did not override them."""
    if config.output and getattr(args, "output", None) == DEFAULT_OUTPUT_DIR:
        args.output = config.output  # type: ignore[attr-defined]
    if config.workers is not None and getattr(args, "workers", None) == DEFAULT_WORKERS:
        args.workers = config.workers  # type: ignore[attr-defined]
    if config.timeout is not None and getattr(args, "timeout", None) == DEFAULT_TIMEOUT:
        args.timeout = config.timeout  # type: ignore[attr-defined]
    if config.retries is not None and getattr(args, "retries", None) == DEFAULT_RETRIES:
        args.retries = config.retries  # type: ignore[attr-defined]
    if config.base_url and getattr(args, "base_url", None) == DEFAULT_BASE_URL:
        args.base_url = config.base_url  # type: ignore[attr-defined]
    if config.max_tiles is not None and getattr(args, "max_tiles", None) == DEFAULT_MAX_TILES:
        args.max_tiles = config.max_tiles  # type: ignore[attr-defined]
    if config.delay is not None and getattr(args, "delay", None) == 0:
        args.delay = config.delay  # type: ignore[attr-defined]
    args.config_theater = config.theater  # type: ignore[attr-defined]
    args.config_path = str(config.path) if config.path else None  # type: ignore[attr-defined]
