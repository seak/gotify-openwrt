#!/usr/bin/env python3
"""Check a gotify OpenWrt .ipk: gzip magic, three members, LF, mode 0755, version."""
from __future__ import annotations

import argparse
import gzip
import io
import tarfile
from pathlib import Path

EXPECTED_MEMBERS = ("debian-binary", "control.tar.gz", "data.tar.gz")


def norm(name: str) -> str:
    if name.startswith("./"):
        return name[2:]
    return name.lstrip("/")


def read_member(tar: tarfile.TarFile, info: tarfile.TarInfo) -> bytes:
    extracted = tar.extractfile(info)
    if extracted is None:
        raise SystemExit(f"FAIL: cannot read {info.name}")
    return extracted.read()


def file_map(blob: bytes) -> dict[str, tuple[tarfile.TarInfo, bytes]]:
    found: dict[str, tuple[tarfile.TarInfo, bytes]] = {}
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:") as tar:
        for info in tar.getmembers():
            if not info.isreg():
                continue
            found[norm(info.name)] = (info, read_member(tar, info))
    return found


def verify_gotify(control_text: str, data_files: dict[str, tuple[tarfile.TarInfo, bytes]], package: str) -> int:
    if package == "gotify-zh":
        if "Conflicts: gotify" not in control_text:
            raise SystemExit("FAIL: gotify-zh control missing Conflicts: gotify")
        if "Provides: gotify" not in control_text:
            raise SystemExit("FAIL: gotify-zh control missing Provides: gotify")
    elif "Conflicts: gotify-zh" not in control_text:
        raise SystemExit("FAIL: gotify control missing Conflicts: gotify-zh")

    if "etc/init.d/gotify" not in data_files:
        raise SystemExit("FAIL: data archive is missing etc/init.d/gotify")
    init_info, init = data_files["etc/init.d/gotify"]
    init_mode = init_info.mode & 0o777
    if b"\r" in init:
        raise SystemExit("FAIL: init contains CR")
    if init_mode != 0o755:
        raise SystemExit(f"FAIL: init mode {init_mode:o}, want 755")

    license_path = f"usr/share/licenses/{package}/LICENSE"
    if license_path not in data_files:
        raise SystemExit(f"FAIL: data archive is missing {license_path}")
    license_text = data_files[license_path][1]
    if b"MIT License" not in license_text or b"jmattheis" not in license_text:
        raise SystemExit(f"FAIL: {license_path} is not upstream Gotify MIT text")
    return init_mode


def verify_luci(control_text: str, data_files: dict[str, tuple[tarfile.TarInfo, bytes]]) -> int:
    if "Architecture: all" not in control_text:
        raise SystemExit("FAIL: luci-app-gotify control missing Architecture: all")
    if "Depends: gotify" not in control_text:
        raise SystemExit("FAIL: luci-app-gotify control missing Depends: gotify")
    if "usr/bin/gotify" in data_files:
        raise SystemExit("FAIL: luci-app-gotify must not ship usr/bin/gotify")

    required = (
        "usr/libexec/rpcd/luci.gotify",
        "usr/share/luci/menu.d/luci-app-gotify.json",
        "usr/share/rpcd/acl.d/luci-app-gotify.json",
        "www/luci-static/resources/view/gotify/main.js",
        "usr/lib/lua/luci/i18n/gotify.zh-cn.lmo",
        "usr/share/licenses/luci-app-gotify/LICENSE",
    )
    for path in required:
        if path not in data_files:
            raise SystemExit(f"FAIL: data archive is missing {path}")

    luci_license = data_files["usr/share/licenses/luci-app-gotify/LICENSE"][1]
    if b"MIT License" not in luci_license:
        raise SystemExit("FAIL: luci-app-gotify LICENSE is not MIT text")

    rpc_info, rpc = data_files["usr/libexec/rpcd/luci.gotify"]
    rpc_mode = rpc_info.mode & 0o777
    if b"\r" in rpc:
        raise SystemExit("FAIL: luci.gotify contains CR")
    if rpc_mode != 0o755:
        raise SystemExit(f"FAIL: luci.gotify mode {rpc_mode:o}, want 755")

    js = data_files["www/luci-static/resources/view/gotify/main.js"][1]
    if b"\r" in js:
        raise SystemExit("FAIL: main.js contains CR")

    lmo = data_files["usr/lib/lua/luci/i18n/gotify.zh-cn.lmo"][1]
    if len(lmo) < 8:
        raise SystemExit("FAIL: gotify.zh-cn.lmo is too small")
    # Must contain a translated Chinese string from gotify.po
    if "端口".encode("utf-8") not in lmo:
        raise SystemExit("FAIL: gotify.zh-cn.lmo missing expected Chinese msgstr")
    return rpc_mode


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ipk", type=Path)
    parser.add_argument("--version", default="3.1.1-1", help="expected control Version field")
    parser.add_argument(
        "--package",
        default="gotify",
        choices=("gotify", "gotify-zh", "luci-app-gotify"),
        help="expected control Package field",
    )
    args = parser.parse_args()

    blob = args.ipk.read_bytes()
    if len(blob) < 2 or blob[:2] != b"\x1f\x8b":
        raise SystemExit(f"FAIL: {args.ipk} is not gzip (magic {blob[:2].hex() or 'empty'})")

    try:
        outer = gzip.decompress(blob)
    except OSError as exc:
        raise SystemExit(f"FAIL: gzip decompress: {exc}") from exc

    with tarfile.open(fileobj=io.BytesIO(outer), mode="r:") as tar:
        names = [norm(info.name) for info in tar.getmembers() if info.isreg()]
        files = {norm(info.name): read_member(tar, info) for info in tar.getmembers() if info.isreg()}
    if names != list(EXPECTED_MEMBERS):
        raise SystemExit(f"FAIL: members {names}, want {list(EXPECTED_MEMBERS)}")
    if files["debian-binary"] != b"2.0\n":
        raise SystemExit(f"FAIL: debian-binary is {files['debian-binary']!r}")

    control_files = file_map(gzip.decompress(files["control.tar.gz"]))
    if "control" not in control_files or "postinst" not in control_files:
        raise SystemExit(f"FAIL: control archive members {sorted(control_files)}")
    post_info, post = control_files["postinst"]
    control = control_files["control"][1]
    post_mode = post_info.mode & 0o777
    if b"\r" in post:
        raise SystemExit("FAIL: postinst contains CR")
    if post_mode != 0o755:
        raise SystemExit(f"FAIL: postinst mode {post_mode:o}, want 755")

    control_text = control.decode()
    package_lines = [line.strip() for line in control_text.splitlines() if line.startswith("Package:")]
    expected_pkg = f"Package: {args.package}"
    if package_lines != [expected_pkg]:
        raise SystemExit(f"FAIL: {package_lines}, want {expected_pkg}")

    version_lines = [line.strip() for line in control_text.splitlines() if line.startswith("Version:")]
    expected = f"Version: {args.version}"
    if version_lines != [expected]:
        raise SystemExit(f"FAIL: {version_lines}, want {expected}")

    data_files = file_map(gzip.decompress(files["data.tar.gz"]))
    if args.package == "luci-app-gotify":
        extra_mode = verify_luci(control_text, data_files)
        label = f"rpcd={extra_mode:o}"
    else:
        extra_mode = verify_gotify(control_text, data_files, args.package)
        label = f"init={extra_mode:o}"

    print(
        f"OK {args.ipk} Package={args.package} Version={args.version} "
        f"members={','.join(names)} {label} postinst={post_mode:o}"
    )


if __name__ == "__main__":
    main()
