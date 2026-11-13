#!/usr/bin/env python3
"""Pack a gzip OpenWrt .ipk. postinst and init are mode 0755."""
from __future__ import annotations

import argparse
import gzip
import io
import pathlib
import tarfile


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", type=pathlib.Path, required=True)
    parser.add_argument("--bin", type=pathlib.Path, required=True)
    parser.add_argument("--arch", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--release", default="1")
    parser.add_argument(
        "--package",
        default="gotify",
        choices=("gotify", "gotify-zh"),
        help="opkg package name (gotify-zh is Chinese Web UI)",
    )
    parser.add_argument(
        "--license",
        type=pathlib.Path,
        required=True,
        help="upstream LICENSE text shipped under /usr/share/licenses/<package>/",
    )
    parser.add_argument("--out", type=pathlib.Path, required=True)
    args = parser.parse_args()

    binary = args.bin.read_bytes()
    if not binary:
        raise SystemExit(f"empty binary: {args.bin}")
    license_text = lf_bytes(args.license)
    if b"MIT License" not in license_text:
        raise SystemExit(f"LICENSE does not look like MIT: {args.license}")
    server_env = lf_bytes(args.files / "server.env")
    init = lf_bytes(args.files / "gotify.init")
    postinst = lf_bytes(args.files / "postinst")

    installed = max(
        1,
        (len(binary) + len(server_env) + len(init) + len(license_text)) // 1024,
    )
    license_arc = f"usr/share/licenses/{args.package}/LICENSE"
    if args.package == "gotify-zh":
        conflicts = "gotify"
        provides = "gotify"
        description = (
            f"Gotify push notification server with Chinese Web UI "
            f"(musl/static for OpenWrt {args.arch})"
        )
    else:
        conflicts = "gotify-zh"
        provides = ""
        description = f"Gotify push notification server (musl/static for OpenWrt {args.arch})"

    control_lines = [
        f"Package: {args.package}",
        f"Version: {args.version}-{args.release}",
        "Depends: ca-bundle",
        f"Conflicts: {conflicts}",
        "Source: https://github.com/gotify/server",
        "License: MIT",
        "Section: net",
        f"Architecture: {args.arch}",
        f"Installed-Size: {installed}",
        f"Description: {description}",
    ]
    if provides:
        # Insert after Conflicts
        idx = control_lines.index(f"Conflicts: {conflicts}")
        control_lines.insert(idx + 1, f"Provides: {provides}")
    control = ("\n".join(control_lines) + "\n").encode()
    conffiles = b"/etc/gotify/server.env\n"

    control_tar = gz_tar(
        members=[
            ("control", control, 0o644),
            ("conffiles", conffiles, 0o644),
            ("postinst", postinst, 0o755),
        ]
    )
    data_tar = gz_tar(
        members=[
            ("usr/bin/gotify", binary, 0o755),
            ("etc/gotify/server.env", server_env, 0o644),
            ("etc/init.d/gotify", init, 0o755),
            (license_arc, license_text, 0o644),
        ],
        dirs=[
            "usr",
            "usr/bin",
            "usr/share",
            "usr/share/licenses",
            f"usr/share/licenses/{args.package}",
            "etc",
            "etc/gotify",
            "etc/gotify/data",
            "etc/gotify/data/images",
            "etc/gotify/data/plugins",
            "etc/init.d",
        ],
    )

    # OpenWrt 24.x wants a gzip-compressed tar of these three members, not an ar archive.
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
