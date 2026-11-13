#!/usr/bin/env python3
"""Pack Architecture: all luci-app-gotify .ipk (gzip OpenWrt layout)."""
from __future__ import annotations

import argparse
import gzip
import io
import pathlib
import sys
import tarfile

# Same directory import for po2lmo
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from po2lmo import build_lmo  # noqa: E402


def lf_bytes(path: pathlib.Path) -> bytes:
    data = path.read_bytes()
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def add_file(tar: tarfile.TarFile, arcname: str, data: bytes, mode: int) -> None:
    info = tarfile.TarInfo(name=arcname)
    info.size = len(data)
    info.mode = mode
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    tar.addfile(info, io.BytesIO(data))


def add_dir(tar: tarfile.TarFile, arcname: str, mode: int = 0o755) -> None:
    info = tarfile.TarInfo(name=arcname.rstrip("/") + "/")
    info.type = tarfile.DIRTYPE
    info.mode = mode
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    tar.addfile(info)


def gz_tar(members: list[tuple[str, bytes, int]] | None = None, dirs: list[str] | None = None) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.GNU_FORMAT) as tar:
        for directory in dirs or []:
            add_dir(tar, directory)
        for name, data, mode in members or []:
            add_file(tar, name, data, mode)
    return gzip.compress(buf.getvalue(), mtime=0)


def ensure_parents(dirs: set[str], path: str) -> None:
    parts = path.split("/")
    for i in range(1, len(parts)):
        dirs.add("/".join(parts[:i]))


def add_tree(
    dirs: set[str],
    members: list[tuple[str, bytes, int]],
    base: pathlib.Path,
    dest_prefix: str,
) -> None:
    if not base.is_dir():
        return
    for path in sorted(base.rglob("*")):
        rel = path.relative_to(base).as_posix()
        arc = f"{dest_prefix}/{rel}" if dest_prefix else rel
        arc = arc.lstrip("/")
        if path.is_dir():
            dirs.add(arc)
            ensure_parents(dirs, arc)
            continue
        if not path.is_file():
            continue
        ensure_parents(dirs, arc)
        parent = str(pathlib.PurePosixPath(arc).parent)
        if parent != ".":
            dirs.add(parent)
        mode = 0o644
        if "libexec/rpcd" in arc or path.name.endswith(".sh"):
            mode = 0o755
        data = lf_bytes(path)
        members.append((arc, data, mode))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=pathlib.Path, required=True, help="luci-app-gotify directory")
    parser.add_argument("--version", required=True)
    parser.add_argument("--release", default="1")
    parser.add_argument(
        "--license",
        type=pathlib.Path,
        required=True,
        help="packaging-repo LICENSE shipped under /usr/share/licenses/luci-app-gotify/",
    )
    parser.add_argument("--out", type=pathlib.Path, required=True)
    args = parser.parse_args()

    app = args.app
    if not app.is_dir():
        raise SystemExit(f"missing app dir: {app}")

    license_text = lf_bytes(args.license)
    if b"MIT License" not in license_text:
        raise SystemExit(f"LICENSE does not look like MIT: {args.license}")

    dirs: set[str] = set()
    members: list[tuple[str, bytes, int]] = []

    # LuCI convention: htdocs → /www, root → /
    add_tree(dirs, members, app / "htdocs", "www")
    add_tree(dirs, members, app / "root", "")

    po_root = app / "po"
    if po_root.is_dir():
        add_tree(dirs, members, po_root, "usr/share/luci-app-gotify/po")

    # Compile zh_Hans → gotify.zh-cn.lmo into the same package (no separate i18n ipk).
    zh_po = app / "po" / "zh_Hans" / "gotify.po"
    if zh_po.is_file():
        lmo = build_lmo(zh_po.read_text(encoding="utf-8"))
        if not lmo:
            raise SystemExit(f"po2lmo produced empty output from {zh_po}")
        lmo_path = "usr/lib/lua/luci/i18n/gotify.zh-cn.lmo"
        ensure_parents(dirs, lmo_path)
        dirs.add("usr/lib/lua/luci/i18n")
        members.append((lmo_path, lmo, 0o644))
        print(f"Included {lmo_path} ({len(lmo)} bytes)")
    else:
        raise SystemExit(f"missing Chinese catalog: {zh_po}")

    license_arc = "usr/share/licenses/luci-app-gotify/LICENSE"
    ensure_parents(dirs, license_arc)
    dirs.add("usr/share/licenses/luci-app-gotify")
    members.append((license_arc, license_text, 0o644))

    if not members:
        raise SystemExit(f"no installable files under {app}")

    dir_list = sorted(dirs, key=lambda d: (d.count("/"), d))
    installed = max(1, sum(len(d) for _, d, _ in members) // 1024)

    control = "\n".join(
        [
            "Package: luci-app-gotify",
            f"Version: {args.version}-{args.release}",
            "Depends: gotify",
            "Source: https://github.com/seak/gotify-openwrt",
            "License: MIT",
            "Section: luci",
            "Architecture: all",
            f"Installed-Size: {installed}",
            "Description: LuCI support for Gotify (server.env, service, optional WAN firewall)",
            "",
        ]
    ).encode()

    postinst = (
        b"#!/bin/sh\n"
        b'[ -n "${IPKG_INSTROOT}" ] && exit 0\n'
        b"chmod 0755 /usr/libexec/rpcd/luci.gotify 2>/dev/null || true\n"
        b"[ -x /etc/init.d/rpcd ] && /etc/init.d/rpcd reload 2>/dev/null || true\n"
        b"exit 0\n"
    )

    control_tar = gz_tar(
        members=[
            ("control", control, 0o644),
            ("postinst", postinst, 0o755),
        ]
    )
    data_tar = gz_tar(members=members, dirs=dir_list)

    outer = gz_tar(
        members=[
            ("./debian-binary", b"2.0\n", 0o644),
            ("./control.tar.gz", control_tar, 0o644),
            ("./data.tar.gz", data_tar, 0o644),
        ]
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(outer)
    print(f"Wrote {args.out} ({len(outer)} bytes)")


if __name__ == "__main__":
    main()
