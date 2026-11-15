# Pitfalls

[English](PITFALLS.md) | [简体中文](PITFALLS.zh-CN.md)

OpenWrt-specific traps and maintainer gotchas that are easy to miss. Build/install: [README.md](../README.md). Releases: [CHANGELOG.md](../CHANGELOG.md).

## Symptom → fix

| Symptom | Cause | Fix |
|---------|-------|-----|
| Official amd64 binary will not run | glibc vs musl | musl-static self-built package |
| `/etc/init.d/gotify` misbehaves | CRLF | LF + strip `\r` when packing |
| Data under `/tmp/lib/gotify` | `/var`→`/tmp` + old config | `/etc/gotify/data` + forced env + postinst |
| Package name / `gotify version` is unknown | no VERSION or `-X` missing | require `VERSION` + build self-check |
| SDK golang build fails | feed Go too old | build binary with external Go; only pack the ipk |
| `Malformed package file` on `opkg install` | classic `ar` `.ipk` | OpenWrt 24.x needs gzip tar (`debian-binary` + `control.tar.gz` + `data.tar.gz`) |
| Official plugin `.so` will not load | ABI / musl mismatch | out of scope for this package |

## Data directory (`/var` is not persistent)

On OpenWrt, **`/var` → `/tmp` (tmpfs)**. Paths under `/var/lib/gotify` land in `/tmp` and are lost on reboot.

`gotify.init` forces data-related settings through procd environment (process env wins over `server.env`):

- `GOTIFY_DATABASE_CONNECTION=/etc/gotify/data/gotify.db`
- `GOTIFY_UPLOADEDIMAGESDIR=/etc/gotify/data/images`
- `GOTIFY_PLUGINSDIR=/etc/gotify/data/plugins`

`postinst` rewrites `/var/lib/gotify` and `/tmp/lib/gotify` in `server.env` to `/etc/gotify/data`, migrates existing DB files when possible, then enable/start.

## Line endings and `.ipk` format

- Windows checkouts can make init CRLF and break ash/procd → `.gitattributes` forces LF; strip `\r` before packing; init/postinst mode 0755
- OpenWrt 24.x rejects classic `ar` packages as *Malformed package file*; packing must emit a **gzip tar** layout

## Version injection checks

- Only this repo’s `VERSION` file (optional env override); missing version fails the build—no `0.0.0-unknown`
- Injected: `main.Version` / `Commit` / `BuildDate` / `Mode=prod`
- Verify with `gotify version` on native builds, or embedded strings on cross builds (**do not** rely on Go 1.26 `go version -m` listing `-X`)

## Cross-compile musts

If these are skipped, the binary or embedded UI breaks:

- `CGO_ENABLED=1`, `CC` set to the matching musl cross compiler
- `-linkmode external -extldflags=-static` (default DB driver is `mattn/go-sqlite3`; `CGO_ENABLED=0` panics at startup)
- Run `yarn build` first so `ui/build/*` exists for `//go:embed`

## Bumping upstream for `gotify-zh`

Upstream UI has no i18n; zh strings are applied on a **build-time source copy** only. When bumping the upstream tag:

1. Update this repo’s `VERSION` and check out the matching tag  
2. `git -C ../gotify-server diff vOLD..vNEW -- ui/src`  
3. Refresh `replacements.json` / `SPECIALS` in `apply-ui-zh.py`  
4. Build with `LOCALE=zh` and smoke-test (login, messages, apps, clients, users, settings)  
5. Update `CHANGELOG.md`

Packager credit (`apply-ui-branding.py`) runs after the Chinese pass so the credit stays English on `gotify-zh`.
