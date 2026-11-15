#!/usr/bin/env python3
"""Stage luci-app-gotify install tree for apk mkpkg --files."""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from po2lmo import build_lmo  # noqa: E402


def lf_bytes(path: pathlib.Path) -> bytes:
    data = path.read_bytes()
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def write_file(dest: pathlib.Path, data: bytes, mode: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    dest.chmod(mode)


def stage_tree(base: pathlib.Path, dest_root: pathlib.Path, dest_prefix: str) -> None:
    if not base.is_dir():
        return
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(base).as_posix()
        arc = f"{dest_prefix}/{rel}" if dest_prefix else rel
        arc = arc.lstrip("/")
        mode = 0o755 if ("libexec/rpcd" in arc or path.name.endswith(".sh")) else 0o644
        write_file(dest_root / arc, lf_bytes(path), mode)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=pathlib.Path, required=True)
    parser.add_argument(
        "--license",
        type=pathlib.Path,
        required=True,
        help="packaging-repo LICENSE under /usr/share/licenses/luci-app-gotify/",
    )
    parser.add_argument("--out", type=pathlib.Path, required=True, help="stage root directory")
    parser.add_argument(
        "--scripts-out",
        type=pathlib.Path,
        required=True,
        help="directory for maintainer scripts (post-install)",
    )
    args = parser.parse_args()

    app = args.app
    if not app.is_dir():
        raise SystemExit(f"missing app dir: {app}")

    license_text = lf_bytes(args.license)
    if b"MIT License" not in license_text:
        raise SystemExit(f"LICENSE does not look like MIT: {args.license}")

    stage = args.out
    if stage.exists():
        raise SystemExit(f"stage dir already exists: {stage}")
    stage.mkdir(parents=True)

    stage_tree(app / "htdocs", stage, "www")
    stage_tree(app / "root", stage, "")
    po_root = app / "po"
    if po_root.is_dir():
        stage_tree(po_root, stage, "usr/share/luci-app-gotify/po")

    zh_po = app / "po" / "zh_Hans" / "gotify.po"
    if not zh_po.is_file():
        raise SystemExit(f"missing Chinese catalog: {zh_po}")
    lmo = build_lmo(zh_po.read_text(encoding="utf-8"))
    if not lmo:
        raise SystemExit(f"po2lmo produced empty output from {zh_po}")
    write_file(stage / "usr/lib/lua/luci/i18n/gotify.zh-cn.lmo", lmo, 0o644)
    print(f"Included usr/lib/lua/luci/i18n/gotify.zh-cn.lmo ({len(lmo)} bytes)")

    write_file(stage / "usr/share/licenses/luci-app-gotify/LICENSE", license_text, 0o644)

    args.scripts_out.mkdir(parents=True, exist_ok=True)
    post_install = (
        b"#!/bin/sh\n"
        b'[ -n "${IPKG_INSTROOT}" ] && exit 0\n'
        b"chmod 0755 /usr/libexec/rpcd/luci.gotify 2>/dev/null || true\n"
        b"[ -x /etc/init.d/rpcd ] && /etc/init.d/rpcd reload 2>/dev/null || true\n"
        b"exit 0\n"
    )
    write_file(args.scripts_out / "post-install", post_install, 0o755)
    post_upgrade = b"#!/bin/sh\nexport PKG_UPGRADE=1\n" + post_install.split(b"\n", 1)[1]
    write_file(args.scripts_out / "post-upgrade", post_upgrade, 0o755)
    print(f"Staged luci-app-gotify under {stage}")


if __name__ == "__main__":
    main()
