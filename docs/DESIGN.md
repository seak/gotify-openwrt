# Design

[English](DESIGN.md) | [简体中文](DESIGN.zh-CN.md)

Why this packaging works the way it does, and pitfalls seen on real routers. Build/install: [README.md](../README.md). Releases: [CHANGELOG.md](../CHANGELOG.md).

Targets: OpenWrt **24.10**, `x86/64` (`x86_64`) and `bcm27xx/bcm2710` (Raspberry Pi 3, `aarch64_cortex-a53`). On 24.10, Pi 3 is **64-bit aarch64**, not armv7. Upstream discussion: [gotify/server#861](https://github.com/gotify/server/issues/861).

## Why not official binaries / SDK Go

| Constraint | Detail |
|------------|--------|
| libc | Official `gotify-linux-*` builds are usually **glibc**-dynamic; OpenWrt defaults to **musl**. Typical symptoms: `not found`, `fcntl64: symbol not found`. |
| CGO | Default DB driver is `mattn/go-sqlite3`; `CGO_ENABLED=0` panics at startup. |
| Feed Go | 24.10 `packages` golang is about **1.23**; official v3.1.1 needs **Go ≥ 1.25**, so SDK `golang-package.mk` cannot build this tree. |

Approach: **host Go 1.26 + musl cross-compile a static binary → pack a gzip OpenWrt `.ipk`**. Host options: the [`scripts/Dockerfile`](../scripts/Dockerfile) image, or a matching WSL/native toolchain ([`scripts/setup-wsl-toolchain.sh`](../scripts/setup-wsl-toolchain.sh)). `net/gotify/Makefile` is feed metadata only; the main path does not compile Go with the SDK. Router-side usage (`opkg install`, `/etc/init.d/gotify`) matches a full SDK package.

**Gotify application code is not modified.** Config is env-based (`godotenv`); the package ships `/etc/gotify/server.env`, not the old YAML `config.yml`.

## Key decisions

### Cross-compile

- `CGO_ENABLED=1`, `CC` set to the matching musl cross compiler
- `-linkmode external -extldflags=-static`
- Run `yarn build` first so `ui/build/*` exists for `//go:embed`

### Version

- Only this repo’s `VERSION` file (optional env override); missing version fails the build—no `0.0.0-unknown`
- Package name: `gotify_${VERSION}-${PKG_RELEASE}_${PKG_ARCH}.ipk` or `gotify-zh_…` (currently `PKG_RELEASE=2`)
- Injected: `main.Version` / `Commit` / `BuildDate` / `Mode=prod`
- Verify with `gotify version` on native builds, or embedded strings on cross builds (do not rely on Go 1.26 `go version -m` listing `-X`)

### Packager credit (all locales)

[`scripts/apply-ui-branding.py`](../scripts/apply-ui-branding.py) on the **build-time source copy**:

- Header (inner pages): muted `seak/gotify-openwrt` caption after upstream `@version` (lower opacity, does not replace Gotify branding)

Links to [seak/gotify-openwrt](https://github.com/seak/gotify-openwrt). Applied after the Chinese pass so the credit stays English on `gotify-zh`.

### Chinese Web UI (`LOCALE=zh` → `gotify-zh`)

Upstream UI has no i18n; strings are hard-coded English. This repo applies [`patches/ui-zh/replacements.json`](../patches/ui-zh/replacements.json) via [`scripts/apply-ui-zh.py`](../scripts/apply-ui-zh.py) on a **build-time source copy**, then `yarn build` embeds the UI. The `gotify-server` working tree is **not** changed.

- Package `gotify-zh` mutually `Conflicts` with `gotify`; `gotify-zh` also `Provides: gotify`
- Same install paths as the English package; data can survive a switch
- No runtime language switcher

When bumping the upstream tag:

1. Update this repo’s `VERSION` and check out the matching tag  
2. `git -C ../gotify-server diff vOLD..vNEW -- ui/src`  
3. Refresh `replacements.json` / `SPECIALS` in `apply-ui-zh.py`  
4. Build with `LOCALE=zh` and smoke-test (login, messages, apps, clients, users, settings)  
5. Update `CHANGELOG.md`

### Data directory (do not rely on `/var`)

On OpenWrt, **`/var` → `/tmp` (tmpfs)**. Paths under `/var/lib/gotify` actually land in `/tmp` and are lost on reboot.

| Use | Path |
|-----|------|
| Config | `/etc/gotify/server.env` |
| DB / images / plugins | `/etc/gotify/data/` (overlay, persistent) |
| Listen | **8080** (avoids LuCI/`uhttpd` on 80) |

`gotify.init` forces data-related settings through procd environment (process env wins over `server.env`):

- `GOTIFY_DATABASE_CONNECTION=/etc/gotify/data/gotify.db`
- `GOTIFY_UPLOADEDIMAGESDIR=/etc/gotify/data/images`
- `GOTIFY_PLUGINSDIR=/etc/gotify/data/plugins`

`postinst` rewrites `/var/lib/gotify` and `/tmp/lib/gotify` in `server.env` to `/etc/gotify/data`, migrates existing DB files when possible, then enable/start.

### Line endings and `.ipk` format

- Windows checkouts can make init CRLF and break ash/procd → `.gitattributes` forces LF; strip `\r` before packing; init/postinst mode 0755
- OpenWrt 24.x expects a **gzip tar** (`debian-binary` + `control.tar.gz` + `data.tar.gz`), not classic `ar`; `ar` packages are rejected as *Malformed package file*

## Symptom → fix

| Symptom | Cause | Fix |
|---------|-------|-----|
| Official amd64 binary will not run | glibc vs musl | musl-static self-built package |
| `/etc/init.d/gotify` misbehaves | CRLF | LF + strip `\r` when packing |
| Data under `/tmp/lib/gotify` | `/var`→`/tmp` + old config | `/etc/gotify/data` + forced env + postinst |
| Package name / `gotify version` is unknown | no VERSION or `-X` missing | require `VERSION` + build self-check |
| SDK golang build fails | feed Go too old | build binary with external Go; only pack the ipk |

## LuCI app (`luci-app-gotify`)

Optional LuCI package in this repo (`luci-app-gotify/`). It does **not** introduce Gotify UCI: settings still live in `/etc/gotify/server.env`. The app’s rpcd plugin (`luci.gotify`) reads/writes port, listen address, log level, and registration; start/stop/enable/disable call `/etc/init.d/gotify`. Data paths stay forced by the main package init.

WAN access is **off by default**. Enabling it in LuCI creates or updates a firewall UCI rule named `gotify` (WAN TCP accept on the configured port). The main `gotify` / `gotify-zh` packages still do not ship firewall rules.

No Gotify message/app/client management in LuCI—use the Gotify Web UI on the configured port. Translations: `po/zh_Hans` is compiled by `scripts/po2lmo.py` into `/usr/lib/lua/luci/i18n/gotify.zh-cn.lmo` inside the same `luci-app-gotify` ipk (no separate language package). LuCI language Simplified Chinese then shows Chinese strings; English remains the default msgid fallback. Raw `.po` sources are also shipped under `/usr/share/luci-app-gotify/po/`.

## License (upstream)

Packaging must follow [gotify/server LICENSE](https://github.com/gotify/server/blob/master/LICENSE):

- **MIT** for Gotify code (and the substantial portions redistributed in the `.ipk`): retain copyright and permission notices. Declared as `License: MIT` / `PKG_LICENSE:=MIT`; `pack-ipk.py` installs upstream `LICENSE` to `/usr/share/licenses/<package>/LICENSE`.
- **CC BY 4.0** for the Gotify logo (embedded via upstream UI assets): attribution if the logo is reused or modified outside the upstream UI.
- This repo’s packaging is MIT ([`LICENSE`](../LICENSE)); `luci-app-gotify` ships that file under `/usr/share/licenses/luci-app-gotify/LICENSE`.
- Packager credit in the header does not replace Gotify branding or imply endorsement.

User-facing summary: [README.md § License](../README.md#license).

## Explicitly out of scope

- No upstream application code changes (UI patches only on the build copy: zh strings + packager credit)  
- No in-package language switcher / full i18n framework for Gotify itself  
- No Gotify UCI (`/etc/config/gotify`) in this phase  
- No official plugin `.so` packaging (ABI incompatible with musl/this toolchain)  
- No automatic WAN firewall from the main package (optional only via `luci-app-gotify`)  

