"""Command-line interface for CMO Tacview texture tiles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Sequence, TextIO

from . import __version__
from .catalog import Catalog, scan_local, verify_files
from .constants import (
    DEFAULT_BASE_URL,
    DEFAULT_CONFIRM_AFTER,
    DEFAULT_MAX_TILES,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
    DEFAULT_WORKERS,
)
from .coverage import classify_tile, render_map, tiles_geojson
from .downloader import DownloadResult, download_tiles, probe_tiles
from .install import discover_targets, format_target_help, install_textures
from .selection import SelectionRequest, resolve_selection
from .tiles import Tile, TileError, merge_tiles
from .util import format_bytes, glue_negative_option_values


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
    list_p.add_argument(
        "--check",
        action="store_true",
        help="HEAD each tile (uses the catalog to skip known 404s)",
    )
    list_p.add_argument("-o", "--output", default=DEFAULT_OUTPUT_DIR, help="catalog folder")
    list_p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    list_p.add_argument("-w", "--workers", type=int, default=DEFAULT_WORKERS)
    list_p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    list_p.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    list_p.add_argument("--refresh-missing", action="store_true")
    list_p.add_argument("--map", action="store_true", help="print an ASCII coverage grid")
    list_p.set_defaults(handler=_cmd_list)

    dl = sub.add_parser("download", help="download selected tiles")
    _add_selection_args(dl)
    dl.add_argument("-o", "--output", default=DEFAULT_OUTPUT_DIR, help=f"output folder (default: {DEFAULT_OUTPUT_DIR})")
    dl.add_argument("-w", "--workers", type=int, default=DEFAULT_WORKERS, help=f"parallel downloads (default: {DEFAULT_WORKERS})")
    dl.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    dl.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    dl.add_argument("--base-url", default=DEFAULT_BASE_URL)
    dl.add_argument("--max-tiles", type=int, default=DEFAULT_MAX_TILES)
    dl.add_argument("-y", "--yes", action="store_true", help="do not ask for confirmation on large jobs")
    dl.add_argument("--force", action="store_true", help="re-download even if size already matches")
    dl.add_argument("--dry-run", action="store_true", help="resolve tiles but do not hit the network")
    dl.add_argument("--limit", type=int, default=0, help="download at most N tiles")
    dl.add_argument("--trust-local", action="store_true", help="skip existing files without a HEAD request")
    dl.add_argument("--refresh-missing", action="store_true", help="re-probe tiles the catalog marked 404")
    dl.add_argument("--retry-failed", action="store_true", help="include tiles the catalog marked failed")
    dl.add_argument("--no-catalog", action="store_true", help="do not read or write the sidecar catalog")
    dl.add_argument("--json", action="store_true", help="print the summary as JSON")
    dl.add_argument("-q", "--quiet", action="store_true", help="print only the final summary")
    dl.set_defaults(handler=_cmd_download)

    probe = sub.add_parser("probe", help="check whether tiles exist on the host")
    probe.add_argument("names", nargs="*", help="tile names, e.g. N25E121")
    _add_selection_args(probe)
    probe.add_argument("--base-url", default=DEFAULT_BASE_URL)
    probe.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    probe.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    probe.add_argument("-w", "--workers", type=int, default=DEFAULT_WORKERS)
    probe.add_argument("-o", "--output", default=DEFAULT_OUTPUT_DIR, help="catalog folder")
    probe.add_argument("--refresh-missing", action="store_true")
    probe.add_argument("--no-catalog", action="store_true")
    probe.add_argument("--json", action="store_true")
    probe.set_defaults(handler=_cmd_probe)

    status = sub.add_parser("status", help="compare a theater against local files and the catalog")
    _add_selection_args(status)
    status.add_argument("-o", "--output", default=DEFAULT_OUTPUT_DIR)
    status.add_argument("--json", action="store_true")
    status.add_argument("--map", action="store_true", help="print an ASCII coverage grid")
    status.add_argument("--geojson", action="store_true", help="print a GeoJSON FeatureCollection")
    status.set_defaults(handler=_cmd_status)

    ver = sub.add_parser("verify", help="check local WebP files for truncated or corrupt data")
    ver.add_argument("-o", "--output", default=DEFAULT_OUTPUT_DIR)
    ver.add_argument("--json", action="store_true")
    ver.set_defaults(handler=_cmd_verify)

    inst = sub.add_parser("install", help="copy downloaded tiles into Tacview/CMO folders")
    inst.add_argument("-s", "--source", default=DEFAULT_OUTPUT_DIR, help=f"folder of .webp files (default: {DEFAULT_OUTPUT_DIR})")
    inst.add_argument("-t", "--target", action="append", default=[], help="destination folder (repeatable)")
    inst.add_argument("--dry-run", action="store_true")
    inst.add_argument("--no-overwrite", action="store_true")
    inst.add_argument("--list-targets", action="store_true")
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
    parser.add_argument(
        "--pad",
        type=int,
        default=0,
        help="expand the selection by N degrees of neighbouring tiles",
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    raw = list(argv) if argv is not None else sys.argv[1:]
    args = parser.parse_args(glue_negative_option_values(raw))
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
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _cmd_theaters(args: argparse.Namespace, out: TextIO, err: TextIO) -> int:
    from .theaters import find_theaters

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
    tiles = resolve_selection(SelectionRequest.from_args(args))
    catalog = Catalog.load(Path(args.output)) if args.check else None
    states = {}
    if args.check:
        probed = probe_tiles(
            tiles,
            base_url=args.base_url,
            workers=args.workers,
            timeout=args.timeout,
            retries=args.retries,
            catalog=catalog,
            skip_known_missing=not args.refresh_missing,
        )
        if catalog is not None:
            catalog.save()
        rows = [
            {
                "tile": p.tile.name,
                "status": p.status,
                "bytes": p.bytes,
                "cached": p.cached,
            }
            for p in probed
        ]
        states = {
            p.tile.name: {
                "ok": "present",
                "missing": "unpublished",
                "fail": "failed",
            }.get(p.status, "unknown")
            for p in probed
        }
        if args.json:
            json.dump(rows, out, indent=2)
            out.write("\n")
        else:
            print(f"{len(tiles)} tile(s)", file=out)
            for p in probed:
                extra = f"  {format_bytes(p.bytes)}" if p.bytes else ""
                cached = "  cached" if p.cached else ""
                print(f"{p.status:<7} {p.tile.filename}{extra}{cached}", file=out)
        if args.map and not args.json:
            print(render_map(tiles, states), file=out)
        return 0 if all(p.status != "fail" for p in probed) else 1

    if args.json:
        json.dump([t.name for t in tiles], out, indent=2)
        out.write("\n")
        return 0
    print(f"{len(tiles)} tile(s)", file=out)
    for tile in tiles:
        print(tile.filename, file=out)
    if args.map:
        local = scan_local(Path(args.output))
        catalog = Catalog.load(Path(args.output))
        states = {
            t.name: classify_tile(
                t,
                local=local,
                catalog_status=(catalog.get(t).status if catalog.get(t) else None),
            )
            for t in tiles
        }
        print(render_map(tiles, states), file=out)
    return 0


def _cmd_download(args: argparse.Namespace, out: TextIO, err: TextIO) -> int:
    request = SelectionRequest.from_args(args)
    output = Path(args.output)
    catalog = None if args.no_catalog else Catalog.load(output)

    tiles: List[Tile] = []
    if not request.is_empty():
        tiles = resolve_selection(request)
    if args.retry_failed:
        if catalog is None:
            print("error: --retry-failed needs the catalog (omit --no-catalog)", file=err)
            return 2
        tiles = merge_tiles(tiles, catalog.failed_tiles())
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

    if not args.json:
        print(f"tiles: {len(tiles)}  output: {output}  workers: {args.workers}", file=out)
    if not args.yes and not args.dry_run and len(tiles) >= DEFAULT_CONFIRM_AFTER:
        if not _confirm(f"Download {len(tiles)} tiles now? [y/N] ", err):
            print("aborted", file=err)
            return 1

    quiet = bool(args.quiet) or bool(args.json)

    def on_result(result: DownloadResult, current: int, total: int) -> None:
        if quiet:
            return
        extra = ""
        if result.status == "ok":
            extra = f"  {format_bytes(result.bytes_written)}"
        elif result.error:
            extra = f"  {result.error}"
        cached = "  cached" if result.cached else ""
        print(
            f"[{current:4d}/{total}] {result.status:<7} {result.tile.filename}{extra}{cached}",
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
        trust_local=args.trust_local,
        skip_known_missing=not args.refresh_missing,
        catalog=catalog,
        on_result=on_result,
    )
    if catalog is not None and not args.dry_run:
        catalog.save()
    if args.json:
        json.dump(summary.to_dict(), out, indent=2)
        out.write("\n")
    else:
        _print_summary(summary, out)
    return 1 if summary.failed else 0


def _cmd_probe(args: argparse.Namespace, out: TextIO, err: TextIO) -> int:
    request = SelectionRequest.from_args(args)
    if args.names:
        request.tiles = list(request.tiles) + list(args.names)
    if request.is_empty():
        print("error: pass tile names or --theater/--bbox/--tiles", file=err)
        return 2
    tiles = resolve_selection(request)
    catalog = None if args.no_catalog else Catalog.load(Path(args.output))
    rows = probe_tiles(
        tiles,
        base_url=args.base_url,
        workers=args.workers,
        timeout=args.timeout,
        retries=args.retries,
        catalog=catalog,
        skip_known_missing=not args.refresh_missing,
    )
    if catalog is not None:
        catalog.save()
    if args.json:
        json.dump(
            [
                {
                    "tile": r.tile.name,
                    "status": r.status,
                    "bytes": r.bytes,
                    "etag": r.etag,
                    "cached": r.cached,
                    "url": r.url,
                    "error": r.error,
                }
                for r in rows
            ],
            out,
            indent=2,
        )
        out.write("\n")
    else:
        for row in rows:
            size_s = f"  {format_bytes(row.bytes)}" if isinstance(row.bytes, int) and row.bytes >= 0 else ""
            err_s = f"  {row.error}" if row.error else ""
            cached = "  cached" if row.cached else ""
            print(f"{row.status:<7} {row.tile.name}{size_s}{err_s}{cached}", file=out)
    return 0 if all(r.status != "fail" for r in rows) else 1


def _cmd_status(args: argparse.Namespace, out: TextIO, err: TextIO) -> int:
    tiles = resolve_selection(SelectionRequest.from_args(args))
    output = Path(args.output)
    local = scan_local(output)
    catalog = Catalog.load(output)
    states = {
        t.name: classify_tile(
            t,
            local=local,
            catalog_status=(catalog.get(t).status if catalog.get(t) else None),
        )
        for t in tiles
    }
    counts = {"present": 0, "unpublished": 0, "planned": 0, "failed": 0}
    for state in states.values():
        counts[state] = counts.get(state, 0) + 1
    payload = {
        "tiles": len(tiles),
        "output": str(output),
        "present": counts["present"],
        "unpublished": counts["unpublished"],
        "planned": counts["planned"],
        "failed": counts["failed"],
        "states": states,
    }
    if args.geojson:
        json.dump(tiles_geojson(tiles, states), out, indent=2)
        out.write("\n")
        return 0
    if args.json:
        json.dump(payload, out, indent=2)
        out.write("\n")
    else:
        print(
            f"tiles={len(tiles)}  present={counts['present']}  "
            f"unpublished={counts['unpublished']}  planned={counts['planned']}  "
            f"failed={counts['failed']}  output={output}",
            file=out,
        )
        if args.map:
            print(render_map(tiles, states), file=out)
    return 0


def _cmd_verify(args: argparse.Namespace, out: TextIO, err: TextIO) -> int:
    output = Path(args.output)
    catalog = Catalog.load(output)
    issues = verify_files(output, catalog)
    if args.json:
        json.dump([issue.__dict__ for issue in issues], out, indent=2)
        out.write("\n")
    elif not issues:
        local = scan_local(output)
        print(f"ok  {len(local)} webp file(s) in {output}", file=out)
    else:
        for issue in issues:
            print(f"fail  {issue.name or '-'}  {issue.problem}", file=out)
    return 1 if issues else 0


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


def _confirm(prompt: str, err: TextIO) -> bool:
    if not sys.stdin.isatty():
        return True
    try:
        answer = input(prompt)
    except EOFError:
        return False
    return answer.strip().lower() in {"y", "yes"}


def _print_summary(summary, out: TextIO) -> None:
    extra = ""
    if summary.cached_missing:
        extra = f"  cached_missing={summary.cached_missing}"
    print(
        f"done in {summary.elapsed:.1f}s  "
        f"downloaded={summary.ok}  skipped={summary.skipped}  "
        f"missing={summary.missing}  failed={summary.failed}  "
        f"bytes={format_bytes(summary.bytes_written)}{extra}",
        file=out,
    )
    if summary.failed_results:
        print("failures:", file=out)
        for result in summary.failed_results:
            print(f"  {result.tile.filename}: {result.error}", file=out)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
