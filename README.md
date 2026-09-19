# CMO Tacview Texture Tiles

[English](#english) · [中文](#chinese)

Download **Command: Modern Operations** Sentinel-2 terrain textures for **Tacview**, by theater, bounding box, or named 1° tile.

The official host no longer offers a directory listing. The old “download everything” spider in this repo therefore cannot work — and Warfare Sims asks players **not** to batch-grab the entire planet. This tool builds SRTM-style names (`N25E121.webp`) from the region you actually play and fetches only those files.

<a id="chinese"></a>

## 中文

### 这是什么

把 CMO 同款 Sentinel-2 地形贴图装进 Tacview，让 3D 回放里的地面和游戏里一致。官方说明：

- 贴图格式是 **WebP**，需要 **Tacview 1.8.3+**
- 文件名是西南角的 1° 格网，例如 `N25E121.webp` 覆盖 25–26°N、121–122°E
- 放到 `[CMO]\Resources\Tacview\Data\Terrain\Textures\` 或 `%ProgramData%\Tacview\Data\Terrain\Textures\`
- **仅限配合 CMO 使用**
- **只下你需要的战区**，不要整包硬抢带宽

`https://warfaresims.slitherine.com/Tacview_Textures/` 已关闭目录索引，必须按文件名直链下载，例如：

`https://warfaresims.slitherine.com/Tacview_Textures/N07W070.webp`

### 安装

```bash
git clone https://github.com/Andyccr/CMO-Tacview-texturetiles.git
cd CMO-Tacview-texturetiles
python -m pip install -e ".[dev]"
```

或只装运行依赖：

```bash
python -m pip install -r requirements.txt
```

### 用法

```bash
# 内置战区
python -m cmo_tacview_tiles theaters

# 先看会下哪些瓦片
python -m cmo_tacview_tiles list --theater taiwan
python -m cmo_tacview_tiles list --theater taiwan --pad 1 --map

# 按战区下载（推荐）
python -m cmo_tacview_tiles download --theater taiwan -o ./tacview_textures

# 覆盖情况（本地文件 + 目录缓存）
python -m cmo_tacview_tiles status --theater taiwan -o ./tacview_textures --map
python -m cmo_tacview_tiles verify -o ./tacview_textures

# 只补缺（跳过已有文件和已知 404）
python -m cmo_tacview_tiles sync --theater taiwan -o ./tacview_textures

# 环境自检 / 清理中断残留
python -m cmo_tacview_tiles doctor
python -m cmo_tacview_tiles clean -o ./tacview_textures

# 按战区下载（推荐）
python -m cmo_tacview_tiles download --theater taiwan -o ./tacview_textures

# 按经纬框：南,西,北,东
python -m cmo_tacview_tiles download --bbox 24,54,28,59 -o ./tacview_textures

# 指定瓦片
python -m cmo_tacview_tiles download --tiles N25E121,N25E122

# 探测某个文件是否还在服务器上
python -m cmo_tacview_tiles probe N25E121 N07W070

# 安装到 Tacview 目录（Windows 会自动探测；其它系统请给 --target）
python -m cmo_tacview_tiles install --source ./tacview_textures --target "D:/Tacview/Data/Terrain/Textures"
```

CMO 里看光标经纬度，取场景西南–东北两个角，填进 `--bbox` 即可。缺省一次最多 400 张，可用 `--max-tiles` 调整；默认 4 个并发，避免打满官方带宽。

已下载且大小一致的文件会跳过，中断的 `.part` 会断点续传。404 是正常现象（海上或未发布的格子），会记成 `missing` 而不是失败，并写入输出目录里的 `.cmo_tiles_catalog.json`，下次不再重复探测。`--pad 1` 会多下一圈相邻格子。`--trust-local` 对已有文件跳过 HEAD。`sync` 只抓本地还没有、且目录里没记过 404 的格子。

可选配置文件 `.cmo-tacview-tiles.ini`（或 `~/.config/cmo-tacview-tiles/config.ini`）：

```ini
[defaults]
output = ./tacview_textures
workers = 4
theater = taiwan
delay = 0.2
```

### 内置战区

`taiwan` `korea` `japan-south` `hokkaido` `scs-north` `spratly` `philippines` `malacca` `guam` `hormuz` `persian-gulf` `red-sea` `levant` `black-sea` `ukraine` `baltic` `giuk` `iceland` `norway` `uk-north` `gibraltar` `med-central` `falklands` `hawaii` `california` `caribbean` `india-west` `india-east` `okinawa` `aden` `suwalki`

完整表：`python -m cmo_tacview_tiles theaters`

<a id="english"></a>

## English

### Why v2

The v1 script (`multithreading.py`) scraped the Apache index of
`https://warfaresims.slitherine.com/Tacview_Textures/` and downloaded every
WebP it saw. That index is now **disabled** (403). Official docs say you must
request tiles by name, and they still ask players not to vacuum the whole set.

This release:

- Generates SRTM 1° names from a theater preset, bounding box, or explicit list
- Downloads concurrently with a small default worker count
- Skips complete files, resumes `.part` files, retries transient HTTP errors
- Treats 404 as “tile not published”, not as a hard failure, and caches that in `.cmo_tiles_catalog.json`
- `status` / `verify` / ASCII `--map` / GeoJSON for coverage
- `sync` downloads only gaps; `doctor` checks the host; `clean` drops `.part` files
- Optional INI config for default theater/output/workers (`--config` / `--no-config`)
- `--pad` expands a theater by neighbouring 1° cells
- `--delay` spaces HTTP starts so a run stays polite
- Refuses oversized jobs (`--max-tiles`, default 400)
- Copies tiles into Tacview/CMO folders (`install`)

### Install

```bash
python -m pip install -e .
cmo-tacview-tiles theaters
```

Without installing:

```bash
python -m cmo_tacview_tiles download --theater hormuz -o ./tacview_textures
python -m cmo_tacview_tiles sync --theater hormuz -o ./tacview_textures
python -m cmo_tacview_tiles doctor
```

`multithreading.py` is kept as a thin wrapper around the same CLI so old
command names still work. Running it with no arguments prints the migration
note instead of downloading the world.

### Tile names

Tacview uses the south-west corner of each 1° cell:

| File | Covers |
| --- | --- |
| `N25E121.webp` | 25–26°N, 121–122°E (Taipei area) |
| `N07W070.webp` | 7–8°N, 70–71°W |
| `S51W060.webp` | 51–52°S, 60–61°W |

Longitude may wrap the antimeridian: `--bbox -2,179,1,-179`.

### Install destinations

After download:

1. Copy `*.webp` into one of:
   - `%ProgramData%\Tacview\Data\Terrain\Textures\`
   - `%APPDATA%\Tacview\Data\Terrain\Textures\`
   - `[CMO]\Resources\Tacview\Data\Terrain\Textures\`
2. Tacview → Options → Terrain Display Mode → Custom Textures
3. Restart Tacview

`cmo-tacview-tiles install --list-targets` shows folders detected on this machine.

### Development

```bash
python -m pip install -e ".[dev]"
pytest -q
```

Textures themselves are **not** in this repository. They are hosted by Warfare
Sims / Slitherine and licensed **only for use with CMO**. This repository is
just the downloader (MIT).

### Changelog

**2.1.0**

- Sidecar catalog remembers unpublished (404) tiles so later runs do not re-probe them
- `status`, `verify`, `list --check`, ASCII `--map`, and GeoJSON coverage
- `sync`, `doctor`, `clean`, INI config, `--delay`
- `--pad`, `--trust-local`, `--retry-failed`, `--refresh-missing`
- Concurrent `probe` with the same theater/bbox selectors as download
- Extra theaters: `okinawa`, `aden`, `suwalki`

**2.0.0**

- Replace directory scraping with coordinate-based tile selection
- Add theater presets, bbox, resume, skip, retries, install helper
- Add CLI (`python -m cmo_tacview_tiles`), tests, and packaging
- Remove leftover `convert.py` / empty `doc.md`
