# Gotify OpenWrt packages

[English](README.md) | [简体中文](README.zh-CN.md)

Standalone packaging for [Gotify](https://gotify.net/) on OpenWrt. Builds a **musl-static** binary from official [gotify/server](https://github.com/gotify/server) and packs **OpenWrt 24.10 `.ipk`** (opkg) and **OpenWrt 25.12 `.apk`** (apk). Upstream application code is not modified.

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

| OpenWrt | Package manager | Artifact | Output dir |
|---------|-----------------|----------|------------|
| **24.10** | opkg | `.ipk` | `bin/packages/24.10/` |
| **25.12** | apk | `.apk` | `bin/packages/25.12/` |

Pick by **your OpenWrt release**: use `.ipk` on 24.10 and `.apk` on 25.12. Do not rename formats. Filenames do **not** embed `24.10`/`25.12` (extension + directory are enough); official feed-style per-release filenames are unnecessary for this out-of-tree musl package.

| `TARGET` | OpenWrt arch | Typical boards |
|----------|--------------|----------------|
| `x86_64` | `x86_64` | x86/64 appliances, VMs |
| `bcm2710` | `aarch64_cortex-a53` | Raspberry Pi 3 (64-bit) |

LuCI: `Architecture: all` under `24.10/all/`; `arch: noarch` under `25.12/noarch/`.

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
| `PKG_FORMAT` | `all` (default → 24.10 `.ipk` + 25.12 `.apk`), `ipk`, or `apk` |
| `GOTIFY_SRC` | Source path (Docker default `/gotify-server`; native default `../gotify-server`) |

Artifacts: `build/` (binaries) and `bin/packages/<openwrt>/<arch>/<pkg>/`. `GOPROXY` prefers `goproxy.cn` by default. [`scripts/verify-ipk.py`](scripts/verify-ipk.py) / [`scripts/verify-apk.py`](scripts/verify-apk.py) check layout, LF, modes, and version. Each run also packs `luci-app-gotify`. Host **apk-tools with `mkpkg`** is required when `PKG_FORMAT` includes `apk`.

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

Toolchain must match [`scripts/Dockerfile`](scripts/Dockerfile): Go **1.26**, Node + Yarn **1.x**, `x86_64-linux-musl-gcc` (and `aarch64-linux-musl-gcc` for `bcm2710` / `all`), plus host **apk-tools** with `mkpkg` for `.apk`. One-shot installer (user prefix `~/.local`, no sudo for Go/Node/musl cross). For apk-tools build deps: `sudo apt install meson ninja-build pkg-config libssl-dev zlib1g-dev`.

```bash
./scripts/setup-wsl-toolchain.sh
# then in a new shell, or: . ~/.local/gotify-openwrt-env.sh
TARGET=x86_64 LOCALE=en ./scripts/build-packages.sh
```

If downloads stall, extract the same archives as in the Dockerfile into `~/.local/opt/` (Go/Node tarball layout) and musl `*-linux-musl-cross/` trees, then re-run the script (it skips components that are already present).

## Install

From a [release](https://github.com/seak/gotify-openwrt/releases) or local `bin/packages/<openwrt>/`, pick the artifact for **your OpenWrt version and arch** (`<ver>` from [`VERSION`](VERSION) + `PKG_RELEASE`).

### OpenWrt 24.10 (opkg / `.ipk`)

```sh
scp gotify_<ver>_x86_64.ipk root@router:/tmp/
opkg update
opkg install /tmp/gotify_<ver>_x86_64.ipk

# Optional LuCI (Architecture: all; Depends: gotify — also satisfied by gotify-zh).
scp luci-app-gotify_<ver>_all.ipk root@router:/tmp/
opkg install /tmp/luci-app-gotify_<ver>_all.ipk
```

### OpenWrt 25.12 (apk / `.apk`)

Packages are unsigned; use `--allow-untrusted`. Do not rename a `.ipk` to `.apk`.

```sh
scp gotify_<ver>-rN_x86_64.apk root@router:/tmp/
apk update
apk add --allow-untrusted /tmp/gotify_<ver>-rN_x86_64.apk

scp luci-app-gotify_<ver>-rN_noarch.apk root@router:/tmp/
apk add --allow-untrusted /tmp/luci-app-gotify_<ver>-rN_noarch.apk
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
scripts/                # Dockerfile, WSL setup, build, pack ipk/apk, verify, branding
```

`bin/` (including `bin/packages/24.10/` and `25.12/`), `build/`, and `graphify-out/` are not committed. Scripts, `net/gotify/files`, and `luci-app-gotify` are forced to LF.

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
