#!/usr/bin/env python3
"""Verify a gotify OpenWrt .apk: apk verify + payload paths, LF, modes, version."""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def extract_payload(apk: Path, dest: Path) -> None:
    apk_bin = shutil.which("apk")
    if not apk_bin:
        raise SystemExit("FAIL: apk not found on PATH (needed to verify .apk)")
    proc = run([apk_bin, "extract", "--allow-untrusted", "--destination", str(dest), str(apk)])
    if proc.returncode != 0:
        proc2 = run([apk_bin, "extract", "--allow-untrusted", "-o", str(dest), str(apk)])
        if proc2.returncode != 0:
            raise SystemExit(
                f"FAIL: apk extract failed:\n{proc.stderr or proc.stdout}\n{proc2.stderr or proc2.stdout}"
            )


def verify_meta(apk: Path, package: str, version: str, arch: str) -> None:
    apk_bin = shutil.which("apk")
    if not apk_bin:
        raise SystemExit("FAIL: apk not found on PATH")

    proc = run([apk_bin, "verify", "--allow-untrusted", str(apk)])
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0 and "UNTRUSTED" not in out.upper() and "allow-untrusted" not in out.lower():
        if "error" in out.lower() or "invalid" in out.lower():
            raise SystemExit(f"FAIL: apk verify:\n{out}")

    dump = run([apk_bin, "adbdump", str(apk)])
    text = (dump.stdout or "") + (dump.stderr or "")
    if dump.returncode != 0 or not text.strip():
        info = run([apk_bin, "info", "--allow-untrusted", "--all", str(apk)])
        text = (info.stdout or "") + (info.stderr or "")
        if info.returncode != 0 and not text.strip():
            raise SystemExit(f"FAIL: cannot read apk metadata for {apk}")

    if not re.search(rf"(?:^|\s)name[=:\s]+{re.escape(package)}\b", text, re.I | re.M):
        if f"name:{package}" not in text and f'"{package}"' not in text and package not in text:
            raise SystemExit(f"FAIL: package name {package} not found in metadata")
    if version not in text:
        raise SystemExit(f"FAIL: version {version} not found in metadata")
    if arch == "noarch":
        if "noarch" not in text and "arch:noarch" not in text:
            if not re.search(r"arch\s*[=:]\s*noarch", text, re.I):
                raise SystemExit("FAIL: arch noarch not found in metadata")
    elif arch not in text:
        raise SystemExit(f"FAIL: arch {arch} not found in metadata")


def check_file(root: Path, rel: str, *, mode: int | None = None, require_lf: bool = False) -> bytes:
    path = root / rel
    if not path.is_file():
        raise SystemExit(f"FAIL: missing {rel}")
    data = path.read_bytes()
    if require_lf and b"\r" in data:
        raise SystemExit(f"FAIL: {rel} contains CR")
    if mode is not None:
        got = path.stat().st_mode & 0o777
        if got != mode:
            raise SystemExit(f"FAIL: {rel} mode {got:o}, want {mode:o}")
    return data


def verify_gotify(root: Path, package: str) -> None:
    check_file(root, "etc/init.d/gotify", mode=0o755, require_lf=True)
    check_file(root, "usr/bin/gotify", mode=0o755)
    check_file(root, "etc/gotify/server.env", require_lf=True)
    license_path = f"usr/share/licenses/{package}/LICENSE"
    lic = check_file(root, license_path)
    if b"MIT License" not in lic or b"jmattheis" not in lic:
        raise SystemExit(f"FAIL: {license_path} is not upstream Gotify MIT text")
    conf = root / f"lib/apk/packages/{package}.conffiles"
    if conf.is_file():
        text = conf.read_text(encoding="utf-8")
        if "/etc/gotify/server.env" not in text:
            raise SystemExit("FAIL: conffiles missing /etc/gotify/server.env")


def verify_luci(root: Path) -> None:
    required = (
        "usr/libexec/rpcd/luci.gotify",
        "usr/share/luci/menu.d/luci-app-gotify.json",
        "usr/share/rpcd/acl.d/luci-app-gotify.json",
        "www/luci-static/resources/view/gotify/main.js",
        "usr/lib/lua/luci/i18n/gotify.zh-cn.lmo",
        "usr/share/licenses/luci-app-gotify/LICENSE",
    )
    for rel in required:
        check_file(root, rel)
    check_file(root, "usr/libexec/rpcd/luci.gotify", mode=0o755, require_lf=True)
    check_file(root, "www/luci-static/resources/view/gotify/main.js", require_lf=True)
    lmo = check_file(root, "usr/lib/lua/luci/i18n/gotify.zh-cn.lmo")
    if len(lmo) < 8 or "端口".encode("utf-8") not in lmo:
        raise SystemExit("FAIL: gotify.zh-cn.lmo missing expected Chinese msgstr")
    lic = check_file(root, "usr/share/licenses/luci-app-gotify/LICENSE")
    if b"MIT License" not in lic:
        raise SystemExit("FAIL: luci-app-gotify LICENSE is not MIT text")
    if (root / "usr/bin/gotify").exists():
        raise SystemExit("FAIL: luci-app-gotify must not ship usr/bin/gotify")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("apk", type=Path)
    parser.add_argument(
        "--version",
        required=True,
        help="expected apk version (e.g. 3.1.1-r2)",
    )
    parser.add_argument(
        "--package",
        default="gotify",
        choices=("gotify", "gotify-zh", "luci-app-gotify"),
    )
    parser.add_argument(
        "--arch",
        required=True,
        help="expected arch (x86_64, aarch64_cortex-a53, or noarch)",
    )
    args = parser.parse_args()

    if not args.apk.is_file():
        raise SystemExit(f"FAIL: missing {args.apk}")
    if args.apk.suffix != ".apk":
        raise SystemExit(f"FAIL: expected .apk, got {args.apk}")

    verify_meta(args.apk, args.package, args.version, args.arch)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "root"
        root.mkdir()
        extract_payload(args.apk, root)
        candidates = [root]
        for child in root.rglob("usr/bin/gotify"):
            candidates.append(child.parents[2])
            break
        for child in root.rglob("usr/libexec/rpcd/luci.gotify"):
            candidates.append(child.parents[3])
            break
        payload = root
        for cand in candidates:
            if (cand / "usr").is_dir() or (cand / "www").is_dir() or (cand / "etc").is_dir():
                payload = cand
                break

        if args.package == "luci-app-gotify":
            verify_luci(payload)
        else:
            verify_gotify(payload, args.package)

    print(f"OK {args.apk} Package={args.package} Version={args.version} Arch={args.arch}")


if __name__ == "__main__":
    main()
