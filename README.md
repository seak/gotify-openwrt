# Gotify OpenWrt packages

[English](README.md) | [简体中文](README.zh-CN.md)

Standalone packaging for [Gotify](https://gotify.net/) on OpenWrt. Builds a **musl-static** binary from official [gotify/server](https://github.com/gotify/server) and packs `.ipk` files. Upstream application code is not modified.

OpenWrt pitfalls and maintainer gotchas: [docs/PITFALLS.md](docs/PITFALLS.md).

## Why this repo

| Constraint | Detail |
|------------|--------|
| libc | Official release binaries are typically glibc-dynamic; OpenWrt uses musl. |
| CGO | Default SQLite driver is `mattn/go-sqlite3`; `CGO_ENABLED=0` panics at startup. |
| Go version | Current upstream needs Go ≥ 1.25; OpenWrt 24.10 feed Go is too old to build it in-tree. |

So packages are built **outside** the OpenWrt SDK with Go 1.26 + musl cross compilers (Docker image, or a matching WSL/native toolchain). [`net/gotify/Makefile`](net/gotify/Makefile) is feed metadata only.

Package version is pinned in [`VERSION`](VERSION); see [CHANGELOG](CHANGELOG.md) / [Releases](https://github.com/seak/gotify-openwrt/releases) for the current release.

### Supported targets

| Dimension | Current |
|-----------|---------|
| OpenWrt | **24.10** (verified; other releases not guaranteed) |
| Arch | see table below |

| `TARGET` | OpenWrt arch | Typical boards |
|----------|--------------|----------------|
| `x86_64` | `x86_64` | x86/64 appliances, VMs |
| `bcm2710` | `aarch64_cortex-a53` | Raspberry Pi 3 (64-bit) |

More OpenWrt releases / arches may be added later.

### UI languages

Upstream Gotify has no i18n; this repo ships separate packages (same paths, **Conflicts** each other). Data under `/etc/gotify/data` can survive a switch. Artifact names: [CHANGELOG](CHANGELOG.md).

| `LOCALE` | Package | UI |
|----------|---------|-----|
| `en` (default) | `gotify` | English (upstream) |
| `zh` | `gotify-zh` | Chinese ([`patches/ui-zh`](patches/ui-zh)) |

Both packages add a muted `seak/gotify-openwrt` caption in the Web UI header (build-time branding; does not replace Gotify). `gotify-zh` mutually `Conflicts` with `gotify` and `Provides: gotify`. No runtime language switcher.

Source defaults to sibling `../gotify-server` at the matching tag. Version comes only from [`VERSION`](VERSION) and is injected with `-X main.Version` (missing / `unknown` fails the build).

## Build

Prerequisite: sibling checkout `../gotify-server` at tag `v$(cat VERSION)` (HEAD must match that tag). The router does **not** need Docker or a Go toolchain at runtime.

| Env | Meaning |
|-----|---------|
| `TARGET` | `x86_64`, `bcm2710`, or `all` |
| `LOCALE` | `en` (default → package `gotify`) or `zh` (→ `gotify-zh`) |
| `GOTIFY_SRC` | Source path (Docker default `/gotify-server`; native default `../gotify-server`) |

Artifacts: `build/` (binaries) and `bin/packages/<arch>/<pkg>/` (`.ipk`). `GOPROXY` prefers `goproxy.cn` by default. [`scripts/verify-ipk.py`](scripts/verify-ipk.py) checks package layout, LF, modes, and version. Each run also packs `luci-app-gotify` (`Architecture: all`).

### Docker (reproducible)

Needs Docker on the host (Windows: Docker Desktop + WSL2, engine running). Host Go/Node are unused.

```powershell
docker build -t gotify-openwrt-builder -f scripts/Dockerfile scripts

docker run --rm `
  -v "${PWD}:/src" `
  -v "${PWD}\..\gotify-server:/gotify-server:ro" `
  -e TARGET=x86_64 `
  gotify-openwrt-builder
```

### WSL / native (no Docker)

Toolchain must match [`scripts/Dockerfile`](scripts/Dockerfile): Go **1.26**, Node + Yarn **1.x**, `x86_64-linux-musl-gcc` (and `aarch64-linux-musl-gcc` for `bcm2710` / `all`). One-shot installer (user prefix `~/.local`, no sudo for Go/Node/musl cross):

```bash
./scripts/setup-wsl-toolchain.sh
# then in a new shell, or: . ~/.local/gotify-openwrt-env.sh
TARGET=x86_64 LOCALE=en ./scripts/build-ipk.sh
```

If downloads stall, extract the same archives as in the Dockerfile into `~/.local/opt/` (Go/Node tarball layout) and musl `*-linux-musl-cross/` trees, then re-run the script (it skips components that are already present).

## Install

Pick the `.ipk` for your arch from a [release](https://github.com/seak/gotify-openwrt/releases) or local `bin/packages/` (filename uses `<ver>` from [`VERSION`](VERSION) + `PKG_RELEASE`), then:

```sh
scp gotify_<ver>_x86_64.ipk root@router:/tmp/
opkg update
opkg install /tmp/gotify_<ver>_x86_64.ipk

# Optional LuCI management (Architecture: all; Depends: gotify — also satisfied by gotify-zh).
# Same ipk includes Chinese LuCI strings (gotify.zh-cn.lmo); set LuCI language to 简体中文.
scp luci-app-gotify_<ver>_all.ipk root@router:/tmp/
opkg install /tmp/luci-app-gotify_<ver>_all.ipk
```

| Path | Role |
|------|------|
| `/usr/bin/gotify` | musl-static binary (embeds Web UI) |
| `/etc/gotify/server.env` | config (conffile; env-based, not YAML `config.yml`) |
| `/etc/gotify/data/` | DB, images, plugins (overlay; survives reboot) |
| `/etc/init.d/gotify` | procd service |
| LuCI → Services → Gotify | optional: edit `server.env`, service control, WAN firewall toggle |

Web UI: `http://<router-ip>:8080` (port **8080** avoids LuCI/`uhttpd` on 80). Default `admin` / `admin`—change on first login. Depends only on `ca-bundle`.

On OpenWrt, `/var` → `/tmp` (tmpfs), so data must not live under `/var`. The init script forces `GOTIFY_DATABASE_CONNECTION`, `GOTIFY_UPLOADEDIMAGESDIR`, and `GOTIFY_PLUGINSDIR` under `/etc/gotify/data` (process env wins over `server.env`); `postinst` migrates old `/var|/tmp` paths. See [docs/PITFALLS.md](docs/PITFALLS.md) if data still lands under `/tmp`.

`luci-app-gotify` does **not** introduce Gotify UCI (`/etc/config/gotify`); it reads/writes `server.env` via rpcd and optionally creates a firewall UCI rule named `gotify` for WAN access (off by default). No Gotify message/app/client management in LuCI—use the Web UI.

## Layout

```text
LICENSE                 # MIT for packaging in this repo
VERSION                 # upstream version pin
CHANGELOG.md            # package artifacts and packaging changes
docs/PITFALLS.md        # OpenWrt traps / maintainer gotchas (English)
docs/PITFALLS.zh-CN.md  # same (简体中文)
net/gotify/             # package feed + procd files
net/gotify-zh/          # Chinese UI variant (shares files/)
luci-app-gotify/        # optional LuCI app (server.env editor, no Gotify UCI)
patches/ui-zh/          # UI string replacements (build copy only)
scripts/                # Dockerfile, WSL setup, build, pack, verify, branding
```

`bin/`, `build/`, and `graphify-out/` are not committed. Scripts, `net/gotify/files`, and `luci-app-gotify` are forced to LF.

## Out of scope

- No upstream application code changes (UI patches only on the build copy: zh strings + packager credit)
- No in-package language switcher / full i18n for Gotify itself
- No Gotify UCI (`/etc/config/gotify`) in this phase
- No official plugin `.so` packaging (ABI incompatible with musl/this toolchain)
- No automatic WAN firewall from the main package (optional only via `luci-app-gotify`)

## License

This repository only packages [gotify/server](https://github.com/gotify/server). Upstream license terms apply to the redistributed binary and embedded Web UI; see the official [LICENSE](https://github.com/gotify/server/blob/master/LICENSE):

| Component | License | Requirement |
|-----------|---------|-------------|
| Gotify server (code, UI strings, etc.) | [MIT](https://opensource.org/licenses/MIT) | Keep the copyright notice and permission notice in all copies or substantial portions. Copyright (c) 2018 [jmattheis](https://github.com/jmattheis). |
| Gotify logo | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | If you reuse or modify the logo, give appropriate credit, link the license, and note any changes. |
| Packaging in this repo | [MIT](LICENSE) | Root [`LICENSE`](LICENSE) covers scripts, `net/gotify*`, and `luci-app-gotify`. |

`.ipk` metadata declares `License: MIT`. Main packages ship upstream Gotify license text at `/usr/share/licenses/gotify/LICENSE` or `/usr/share/licenses/gotify-zh/LICENSE`; `luci-app-gotify` ships this repo’s [`LICENSE`](LICENSE) under `/usr/share/licenses/luci-app-gotify/LICENSE`. This project is not affiliated with or endorsed by the Gotify authors.
