"""Command-line interface for CMO Tacview texture tiles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Sequence, TextIO

from . import __version__
from .constants import (
    DEFAULT_BASE_URL,
    DEFAULT_CONFIRM_AFTER,
    DEFAULT_MAX_TILES,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
    DEFAULT_WORKERS,
)
from .downloader import DownloadResult, DownloadSummary, download_tiles
from .install import (
    discover_targets,
    format_target_help,
    install_textures,
)
from .theaters import THEATERS, find_theaters, get_theater
from .tiles import (
    Tile,
    TileError,
    merge_tiles,
    parse_bbox,
    parse_tile_list,
    parse_tile_name,
    tiles_from_bbox,
)


class CliError(SystemExit):
    """Abort the CLI with a non-zero status and a message."""

    def __init__(self, message: str, code: int = 2) -> None:
        super().__init__(code)
        self.message = message


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cmo-tacview-tiles",
        description=(
            "Download CMO Sentinel-2 terrain textures for Tacview. "
            "The official host no longer lists the directory, so this tool "
            "builds SRTM tile names from a theater or bounding box and "
            "fetches only those files."
        ),
        epilog=(
            "Textures are licensed by Warfare Sims for use with Command: Modern "
            "Operations only. Download only the theater you are playing."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="verbose logging (repeat for more)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="print only errors and the final summary",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    theaters = sub.add_parser("theaters", help="list built-in theater presets")
    theaters.add_argument("query", nargs="?", help="optional name filter")
    theaters.add_argument("--json", action="store_true", help="JSON output")
    theaters.set_defaults(handler=_cmd_theaters)

    list_p = sub.add_parser("list", help="show tiles for a theater or bounding box")
    _add_selection_args(list_p)
    list_p.add_argument("--json", action="store_true", help="JSON output")
    list_p.set_defaults(handler=_cmd_list)

    dl = sub.add_parser("download", help="download selected tiles")
    _add_selection_args(dl)
    dl.add_argument(
        "-o",
        "--output",
        default=DEFAULT_OUTPUT_DIR,
        help=f"output folder (default: {DEFAULT_OUTPUT_DIR})",
    )
    dl.add_argument(
        "-w",
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"parallel downloads (default: {DEFAULT_WORKERS}; keep this modest)",
    )
    dl.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"per-request timeout seconds (default: {DEFAULT_TIMEOUT:g})",
    )
    dl.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=f"HTTP retries (default: {DEFAULT_RETRIES})",
    )
    dl.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="tile URL prefix",
    )
    dl.add_argument(
        "--max-tiles",
        type=int,
        default=DEFAULT_MAX_TILES,
        help=f"refuse jobs larger than this (default: {DEFAULT_MAX_TILES})",
    )
    dl.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="do not ask for confirmation on large jobs",
    )
    dl.add_argument(
        "--force",
        action="store_true",
        help="re-download tiles even if the local file size already matches",
    )
    dl.add_argument(
        "--dry-run",
        action="store_true",
        help="resolve tiles but do not hit the network",
    )
    dl.add_argument(
        "--limit",
        type=int,
        default=0,
        help="download at most N tiles (useful for testing)",
    )
    dl.set_defaults(handler=_cmd_download)

    probe = sub.add_parser("probe", help="check whether named tiles exist on the host")
    probe.add_argument("tiles", nargs="+", help="tile names, e.g. N25E121")
    probe.add_argument("--base-url", default=DEFAULT_BASE_URL)
    probe.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    probe.add_argument("--json", action="store_true")
    probe.set_defaults(handler=_cmd_probe)

    inst = sub.add_parser("install", help="copy downloaded tiles into Tacview/CMO folders")
    inst.add_argument(
        "-s",
        "--source",
        default=DEFAULT_OUTPUT_DIR,
        help=f"folder of .webp files (default: {DEFAULT_OUTPUT_DIR})",
    )
    inst.add_argument(
        "-t",
        "--target",
        action="append",
        default=[],
        help="destination folder (repeatable). Default: autodetect on Windows",
    )
    inst.add_argument("--dry-run", action="store_true")
    inst.add_argument(
        "--no-overwrite",
        action="store_true",
        help="leave existing destination files untouched",
    )
    inst.add_argument(
        "--list-targets",
        action="store_true",
        help="print detected Tacview folders and exit",
    )
    inst.set_defaults(handler=_cmd_install)

    return parser


def _add_selection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-t",
        "--theater",
        action="append",
        default=[],
        metavar="NAME",
        help="built-in theater preset (repeatable). See: theaters",
    )
    parser.add_argument(
        "--bbox",
        action="append",
        default=[],
        metavar="S,W,N,E",
        help="bounding box south,west,north,east in degrees (repeatable). "
        "If a value is negative write --bbox=-2,-70,8,-60",
    )
    parser.add_argument(
        "--tiles",
        action="append",
        default=[],
        help="comma-separated tile names, e.g. N25E121,N25E122",
    )
    parser.add_argument(
        "--from-file",
        dest="from_file",
        help="text file with one tile name per line",
    )


def _glue_negative_option_values(argv: Sequence[str]) -> List[str]:
    """Allow ``--bbox -2,-70,8,-60`` which argparse would otherwise treat as flags."""
    glued: List[str] = []
    i = 0
    while i < len(argv):
        current = argv[i]
        if (
            current == "--bbox"
            and i + 1 < len(argv)
            and argv[i + 1].startswith("-")
            and not argv[i + 1].startswith("--")
        ):
            glued.append(f"--bbox={argv[i + 1]}")
            i += 2
            continue
        glued.append(current)
        i += 1
    return glued


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    raw = list(argv) if argv is not None else sys.argv[1:]
    args = parser.parse_args(_glue_negative_option_values(raw))
    try:
        return int(args.handler(args, sys.stdout, sys.stderr))
    except TileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyError as exc:
        print(f"error: {exc.args[0]}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130
    except CliError as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        return int(exc.code)


def _cmd_theaters(args: argparse.Namespace, out: TextIO, err: TextIO) -> int:
    rows = find_theaters(args.query)
    if args.json:
        payload = [
            {
                "key": t.key,
                "name": t.name,
                "bbox": {
                    "south": t.south,
                    "west": t.west,
                    "north": t.north,
                    "east": t.east,
                },
                "tiles": t.tile_count,
                "description": t.description,
            }
            for t in rows
        ]
        json.dump(payload, out, indent=2, ensure_ascii=False)
        out.write("\n")
        return 0
    if not rows:
        print("no theaters matched", file=err)
        return 1
    key_w = max(len(t.key) for t in rows)
    name_w = max(len(t.name) for t in rows)
    print(
        f"{'key'.ljust(key_w)}  {'name'.ljust(name_w)}  tiles  bbox (S,W,N,E)",
        file=out,
    )
    for t in rows:
        bbox = f"{t.south:g},{t.west:g},{t.north:g},{t.east:g}"
        print(
            f"{t.key.ljust(key_w)}  {t.name.ljust(name_w)}  {t.tile_count:5d}  {bbox}",
            file=out,
        )
        if not args.query:
            print(f"{''.ljust(key_w)}  {t.description}", file=out)
    return 0


def _cmd_list(args: argparse.Namespace, out: TextIO, err: TextIO) -> int:
    tiles = _resolve_tiles(args)
    if args.json:
        json.dump([t.name for t in tiles], out, indent=2)
        out.write("\n")
        return 0
    print(f"{len(tiles)} tile(s)", file=out)
    for tile in tiles:
        print(tile.filename, file=out)
    return 0


def _cmd_download(args: argparse.Namespace, out: TextIO, err: TextIO) -> int:
    tiles = _resolve_tiles(args)
    if args.limit and args.limit > 0:
        tiles = tiles[: args.limit]
    if not tiles:
        print("error: no tiles selected", file=err)
        return 2

    if len(tiles) > args.max_tiles:
        print(
            f"error: {len(tiles)} tiles exceeds --max-tiles {args.max_tiles}. "
            "Narrow the theater/bbox, or raise the cap if you are sure.",
            file=err,
        )
        return 2

    output = Path(args.output)
    print(f"tiles: {len(tiles)}  output: {output}  workers: {args.workers}", file=out)
    if not args.yes and not args.dry_run and len(tiles) >= DEFAULT_CONFIRM_AFTER:
        if not _confirm(f"Download {len(tiles)} tiles now? [y/N] ", err):
            print("aborted", file=err)
            return 1

    quiet = bool(args.quiet)

    def on_result(result: DownloadResult, current: int, total: int) -> None:
        if quiet:
            return
        extra = ""
        if result.status == "ok":
            extra = f"  {_format_bytes(result.bytes_written)}"
        elif result.error:
            extra = f"  {result.error}"
        print(
            f"[{current:4d}/{total}] {result.status:<7} {result.tile.filename}{extra}",
            file=out,
        )

    summary = download_tiles(
        tiles,
        output,
        base_url=args.base_url,
        workers=args.workers,
        timeout=args.timeout,
        retries=args.retries,
        skip_existing=not args.force,
        force=args.force,
        dry_run=args.dry_run,
        on_result=on_result,
    )
    _print_summary(summary, out)
    return 1 if summary.failed else 0


def _cmd_probe(args: argparse.Namespace, out: TextIO, err: TextIO) -> int:
    from .downloader import _head_size
    from .session import build_session, request_timeout

    tiles = parse_tile_list(args.tiles)
    session = build_session(timeout=args.timeout)
    tmo = request_timeout(session, args.timeout)
    rows = []
    for tile in tiles:
        url = tile.url(args.base_url)
        try:
            size = _head_size(session, url, tmo)
            status = "missing" if size is None else "ok"
            rows.append({"tile": tile.name, "status": status, "bytes": size, "url": url})
        except Exception as exc:  # noqa: BLE001
            rows.append(
                {"tile": tile.name, "status": "fail", "error": str(exc), "url": url}
            )
    if args.json:
        json.dump(rows, out, indent=2)
        out.write("\n")
    else:
        for row in rows:
            size = row.get("bytes")
            size_s = f"  {_format_bytes(size)}" if isinstance(size, int) and size >= 0 else ""
            err_s = f"  {row['error']}" if row.get("error") else ""
            print(f"{row['status']:<7} {row['tile']}{size_s}{err_s}", file=out)
    return 0 if all(r["status"] != "fail" for r in rows) else 1


def _cmd_install(args: argparse.Namespace, out: TextIO, err: TextIO) -> int:
    detected = discover_targets()
    if args.list_targets:
        print(format_target_help(detected), file=out)
        return 0
    if args.target:
        targets = [Path(p) for p in args.target]
    else:
        print(format_target_help(detected), file=out)
        targets = [item.path for item in detected if item.exists]
        if not targets:
            print(
                "error: no Tacview folder detected. Pass --target PATH.",
                file=err,
            )
            return 2

    source = Path(args.source)
    try:
        summary = install_textures(
            source,
            targets,
            dry_run=args.dry_run,
            overwrite=not args.no_overwrite,
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=err)
        return 2

    print(
        f"copied={summary.copied}  skipped={summary.skipped}  "
        f"failed={summary.failed}  targets={len(summary.targets)}",
        file=out,
    )
    for message in summary.errors:
        print(f"error: {message}", file=err)
    return 1 if summary.failed or summary.errors else 0


def _resolve_tiles(args: argparse.Namespace) -> List[Tile]:
    groups: List[List[Tile]] = []
    for key in args.theater:
        groups.append(get_theater(key).tiles())
    for box in args.bbox:
        south, west, north, east = parse_bbox(box)
        groups.append(tiles_from_bbox(south, west, north, east))
    if args.tiles:
        groups.append(parse_tile_list(args.tiles))
    if args.from_file:
        path = Path(args.from_file)
        names = [
            line.split("#", 1)[0].strip()
            for line in path.read_text(encoding="utf-8").splitlines()
        ]
        groups.append(parse_tile_list(n for n in names if n))
    if not groups:
        known = ", ".join(sorted(THEATERS))
        raise TileError(
            "select tiles with --theater, --bbox, --tiles, or --from-file. "
            f"Theaters: {known}"
        )
    return merge_tiles(*groups)


def _confirm(prompt: str, err: TextIO) -> bool:
    if not sys.stdin.isatty():
        # Non-interactive: honour --max-tiles as the safety gate; proceed.
        return True
    try:
        answer = input(prompt)
    except EOFError:
        return False
    return answer.strip().lower() in {"y", "yes"}


def _print_summary(summary: DownloadSummary, out: TextIO) -> None:
    print(
        f"done in {summary.elapsed:.1f}s  "
        f"downloaded={summary.ok}  skipped={summary.skipped}  "
        f"missing={summary.missing}  failed={summary.failed}  "
        f"bytes={_format_bytes(summary.bytes_written)}",
        file=out,
    )
    if summary.failed_results:
        print("failures:", file=out)
        for result in summary.failed_results:
            print(f"  {result.tile.filename}: {result.error}", file=out)


def _format_bytes(n: Optional[int]) -> str:
    if n is None:
        return "?"
    value = float(n)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if abs(value) < 1024 or unit == "GiB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{n} B"


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
