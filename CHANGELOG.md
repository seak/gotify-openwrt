# Changelog

This repository records OpenWrt packaging changes only. Upstream Gotify release notes: [gotify/server releases](https://github.com/gotify/server/releases).

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning follows [Semantic Versioning](https://semver.org/) aligned with the upstream tag.

Artifacts (under `bin/packages/<openwrt>/`):

- OpenWrt **24.10**: `gotify[_-zh]_<upstream>-<PKG_RELEASE>_<arch>.ipk` (opkg)
- OpenWrt **25.12**: `gotify[_-zh]_<upstream>-r<PKG_RELEASE>_<arch>.apk` (apk); luci uses `noarch`

Each release entry must state **architecture**, **system**, and **version** (OpenWrt release, not the package tag) before the change list. Copy that block into the GitHub Release body. Package tag remains in the section heading (`<upstream>-<PKG_RELEASE>`).

## [3.1.1-2] - 2026-11-15

| | |
|--|--|
| **Architecture** | `x86_64`; `aarch64_cortex-a53` (`bcm2710`); luci `all` / `noarch` |
| **System** | OpenWrt |
| **Version** | **24.10** (`.ipk`, verified); **25.12** (`.apk`) |

Upstream unchanged: `gotify/server` `v3.1.1`. Packaging revision for LuCI and Chinese Web UI string fixes, plus OpenWrt 25.12 apk packaging.

### Changed

- `luci-app-gotify`: menu/title **Gotify Server**; merge service start/stop and boot enable/disable into single reverse-action buttons with current status; log level `info (default)`; allow new user registration label; bottom `/etc/gotify/server.env` editor with save (`set_env`).
- Chinese Web UI (`gotify-zh`): fix multiline “Update a Client” description; add missing strings (reachability / request / invalid number / Token); JSX multiline matching in `apply-ui-zh.py`.

### Added

- OpenWrt **25.12** `.apk` packaging (`PKG_FORMAT=all|ipk|apk`, default `all`) via host `apk mkpkg`.
- Output layout: `bin/packages/24.10/` (`.ipk`) and `bin/packages/25.12/` (`.apk`).
- `scripts/pack-apk.sh`, `stage-luci-root.py`, `verify-apk.py`; Docker/WSL install apk-tools **3.0.2** with `mkpkg`.
- Renamed `scripts/build-ipk.sh` → `scripts/build-packages.sh` (packs both formats; no compatibility symlink).

### Packages

**OpenWrt 24.10 (opkg / `.ipk`)**

| Package | Arch | Language | File |
|---------|------|----------|------|
| `gotify` | `x86_64` | en | `gotify_3.1.1-2_x86_64.ipk` |
| `gotify-zh` | `x86_64` | zh | `gotify-zh_3.1.1-2_x86_64.ipk` |
| `gotify` | `aarch64_cortex-a53` | en | `gotify_3.1.1-2_aarch64_cortex-a53.ipk` |
| `gotify-zh` | `aarch64_cortex-a53` | zh | `gotify-zh_3.1.1-2_aarch64_cortex-a53.ipk` |
| `luci-app-gotify` | `all` | en + zh-cn | `luci-app-gotify_3.1.1-2_all.ipk` |

**OpenWrt 25.12 (apk / `.apk`)** — install with `apk add --allow-untrusted`

| Package | Arch | Language | File |
|---------|------|----------|------|
| `gotify` | `x86_64` | en | `gotify_3.1.1-r2_x86_64.apk` |
| `gotify-zh` | `x86_64` | zh | `gotify-zh_3.1.1-r2_x86_64.apk` |
| `gotify` | `aarch64_cortex-a53` | en | `gotify_3.1.1-r2_aarch64_cortex-a53.apk` |
| `gotify-zh` | `aarch64_cortex-a53` | zh | `gotify-zh_3.1.1-r2_aarch64_cortex-a53.apk` |
| `luci-app-gotify` | `noarch` | en + zh-cn | `luci-app-gotify_3.1.1-r2_noarch.apk` |

## [3.1.1-1] - 2026-11-14

| | |
|--|--|
| **Architecture** | `x86_64`; `aarch64_cortex-a53` (`bcm2710`); `luci-app-gotify` is `all` |
| **System** | OpenWrt |
| **Version** | **24.10** (verified; other releases not guaranteed) |

Upstream: `gotify/server` `v3.1.1` (commit `e6361caa`). OpenWrt packages without changing application code.

### Added

- Repo layout: `net/gotify/`, `net/gotify-zh/`, `scripts/`, `patches/ui-zh/`; artifacts under `bin/packages/<arch>/<pkg>/`.
- Target matrix: `x86_64`, `aarch64_cortex-a53` (bcm2710) on OpenWrt 24.10.
- Locale variants: `LOCALE=en` → `gotify`; `LOCALE=zh` → `gotify-zh` (UI string replacements on a build copy; packages conflict).
- musl-static build: `CGO_ENABLED=1` + `mattn/go-sqlite3`; inject `main.Version` / `Commit` / `BuildDate` / `Mode=prod`; `PKG_RELEASE=1`; fail when version is missing.
- `scripts/build-ipk.sh`, `apply-ui-zh.py`, `pack-ipk.py`, `verify-ipk.py`, `Dockerfile`, `setup-wsl-toolchain.sh` (Docker-free host toolchain).
- Runtime: `/etc/gotify/data`, procd env overrides, `postinst` migration, port 8080, `ca-bundle`; scripts/files forced to LF.
- Optional `luci-app-gotify` (`Architecture: all`): LuCI Services page edits `/etc/gotify/server.env` via rpcd `luci.gotify` (no Gotify UCI), service control, optional WAN firewall rule; `scripts/pack-luci-ipk.py` / `po2lmo.py` embed `gotify.zh-cn.lmo` in the same ipk; `build-ipk.sh` packs it after the main packages.

### Packages

| Package | Arch | Language | File |
|---------|------|----------|------|
| `gotify` | `x86_64` | en | `bin/packages/x86_64/gotify/gotify_3.1.1-1_x86_64.ipk` |
| `gotify-zh` | `x86_64` | zh | `bin/packages/x86_64/gotify-zh/gotify-zh_3.1.1-1_x86_64.ipk` |
| `gotify` | `aarch64_cortex-a53` | en | `bin/packages/aarch64_cortex-a53/gotify/gotify_3.1.1-1_aarch64_cortex-a53.ipk` |
| `gotify-zh` | `aarch64_cortex-a53` | zh | `bin/packages/aarch64_cortex-a53/gotify-zh/gotify-zh_3.1.1-1_aarch64_cortex-a53.ipk` |
| `luci-app-gotify` | `all` | en + zh-cn | `bin/packages/all/luci-app-gotify/luci-app-gotify_3.1.1-1_all.ipk` |

[3.1.1-2]: https://github.com/seak/gotify-openwrt/releases/tag/3.1.1-2
[3.1.1-1]: https://github.com/gotify/server/releases/tag/v3.1.1
