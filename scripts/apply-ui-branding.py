#!/usr/bin/env python3
"""Add discreet OpenWrt packager credit on header (build copy only)."""
from __future__ import annotations

import pathlib
import sys

REPO_URL = "https://github.com/seak/gotify-openwrt"
HEADER_REL = pathlib.Path("ui/src/layout/Header.tsx")

# After upstream @version link; smaller/muted so it does not compete with Gotify.
HEADER_NEEDLE = (
    "                        <Typography variant=\"button\" color=\"inherit\">\n"
    "                            @{version}\n"
    "                        </Typography>\n"
    "                    </a>\n"
    "                </div>\n"
)
HEADER_INSERT = (
    "                        <Typography variant=\"button\" color=\"inherit\">\n"
    "                            @{version}\n"
    "                        </Typography>\n"
    "                    </a>\n"
    "                    <a\n"
    f"                        href=\"{REPO_URL}\"\n"
    "                        target=\"_blank\"\n"
    "                        rel=\"noopener noreferrer\"\n"
    "                        className={classes.link}\n"
    "                        style={{marginLeft: 10, opacity: 0.55}}>\n"
    "                        <Typography variant=\"caption\" color=\"inherit\">\n"
    "                            seak/gotify-openwrt\n"
    "                        </Typography>\n"
    "                    </a>\n"
    "                </div>\n"
)


def patch_file(
    root: pathlib.Path,
    rel: pathlib.Path,
    *,
    already: str,
    replacements: list[tuple[str, str]],
) -> None:
    path = root / rel
    if not path.is_file():
        raise SystemExit(f"ERROR: missing {path}")
    text = path.read_text(encoding="utf-8")
    if already in text:
        print(f"branding: already present in {rel.as_posix()}")
        return
    for needle, insert in replacements:
        if needle not in text:
            raise SystemExit(f"ERROR: anchor not found in {rel.as_posix()}")
        text = text.replace(needle, insert, 1)
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"branding: {rel.as_posix()}")


def apply(root: pathlib.Path) -> None:
    patch_file(
        root,
        HEADER_REL,
        already=REPO_URL,
        replacements=[(HEADER_NEEDLE, HEADER_INSERT)],
    )


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} <gotify-server-workdir>")
    apply(pathlib.Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    main()
