#!/usr/bin/env python3
"""Compile a gettext .po into LuCI .lmo (OpenWrt luci po2lmo-compatible)."""
from __future__ import annotations

import argparse
import re
import struct
from pathlib import Path


def sfh_hash(data: bytes, init: int | None = None) -> int:
    """Paul Hsieh SuperFastHash — matches luci-base sfh_hash(data, len, init)."""
    length = len(data)
    if length <= 0:
        return 0
    hash_ = length if init is None else init & 0xFFFFFFFF
    rem = length & 3
    nlen = length >> 2
    off = 0

    def get16(i: int) -> int:
        return data[i] | (data[i + 1] << 8)

    for _ in range(nlen):
        hash_ = (hash_ + get16(off)) & 0xFFFFFFFF
        tmp = ((get16(off + 2) << 11) ^ hash_) & 0xFFFFFFFF
        hash_ = ((hash_ << 16) ^ tmp) & 0xFFFFFFFF
        off += 4
        hash_ = (hash_ + (hash_ >> 11)) & 0xFFFFFFFF

    if rem == 3:
        hash_ = (hash_ + get16(off)) & 0xFFFFFFFF
        hash_ = (hash_ ^ ((hash_ << 16) & 0xFFFFFFFF)) & 0xFFFFFFFF
        # signed char for third byte
        b = data[off + 2]
        if b >= 128:
            b -= 256
        hash_ = (hash_ ^ ((b << 18) & 0xFFFFFFFF)) & 0xFFFFFFFF
        hash_ = (hash_ + (hash_ >> 11)) & 0xFFFFFFFF
    elif rem == 2:
        hash_ = (hash_ + get16(off)) & 0xFFFFFFFF
        hash_ = (hash_ ^ ((hash_ << 11) & 0xFFFFFFFF)) & 0xFFFFFFFF
        hash_ = (hash_ + (hash_ >> 17)) & 0xFFFFFFFF
    elif rem == 1:
        b = data[off]
        if b >= 128:
            b -= 256
        hash_ = (hash_ + (b & 0xFFFFFFFF)) & 0xFFFFFFFF
        hash_ = (hash_ ^ ((hash_ << 10) & 0xFFFFFFFF)) & 0xFFFFFFFF
        hash_ = (hash_ + (hash_ >> 1)) & 0xFFFFFFFF

    hash_ = (hash_ ^ ((hash_ << 3) & 0xFFFFFFFF)) & 0xFFFFFFFF
    hash_ = (hash_ + (hash_ >> 5)) & 0xFFFFFFFF
    hash_ = (hash_ ^ ((hash_ << 4) & 0xFFFFFFFF)) & 0xFFFFFFFF
    hash_ = (hash_ + (hash_ >> 17)) & 0xFFFFFFFF
    hash_ = (hash_ ^ ((hash_ << 25) & 0xFFFFFFFF)) & 0xFFFFFFFF
    hash_ = (hash_ + (hash_ >> 6)) & 0xFFFFFFFF
    return hash_


def _decode_po_string(parts: list[str]) -> str:
    """Join PO string fragments and unescape \\n \\t \\r \\" \\\\ only (keep UTF-8)."""
    raw = "".join(parts)
    out: list[str] = []
    i = 0
    while i < len(raw):
        if raw[i] == "\\" and i + 1 < len(raw):
            nxt = raw[i + 1]
            if nxt == "n":
                out.append("\n")
            elif nxt == "t":
                out.append("\t")
            elif nxt == "r":
                out.append("\r")
            elif nxt == '"':
                out.append('"')
            elif nxt == "\\":
                out.append("\\")
            else:
                out.append(nxt)
            i += 2
            continue
        out.append(raw[i])
        i += 1
    return "".join(out)


def parse_po(text: str) -> list[tuple[str | None, str, dict[int, str]]]:
    """Return list of (msgctxt, msgid, {plural_index: msgstr})."""
    entries: list[tuple[str | None, str, dict[int, str]]] = []
    ctxt: str | None = None
    msgid = ""
    msgstrs: dict[int, str] = {}
    mode: str | None = None
    plural_idx = 0
    acc: list[str] = []

    def flush_acc() -> str:
        nonlocal acc
        s = _decode_po_string(acc)
        acc = []
        return s

    def commit() -> None:
        nonlocal ctxt, msgid, msgstrs
        if msgid or msgstrs:
            entries.append((ctxt, msgid, dict(msgstrs)))
        ctxt = None
        msgid = ""
        msgstrs = {}

    str_re = re.compile(r'^"(.*)"\s*$')

    for line in text.splitlines():
        if line.startswith("#"):
            continue
        if line.startswith("msgctxt "):
            if msgid or msgstrs:
                if mode:
                    if mode == "ctxt":
                        ctxt = flush_acc()
                    elif mode == "id":
                        msgid = flush_acc()
                    elif mode == "str":
                        msgstrs[plural_idx] = flush_acc()
                commit()
            mode = "ctxt"
            acc = []
            m = str_re.match(line[8:].strip())
            if m:
                acc.append(m.group(1))
            continue
        if line.startswith("msgid_plural "):
            if mode == "id":
                msgid = flush_acc()
            mode = "id_plural"
            acc = []
            m = str_re.match(line[13:].strip())
            if m:
                acc.append(m.group(1))
            continue
        if line.startswith("msgid "):
            if msgid or msgstrs or ctxt is not None:
                if mode == "ctxt":
                    ctxt = flush_acc()
                elif mode == "id":
                    msgid = flush_acc()
                elif mode == "str":
                    msgstrs[plural_idx] = flush_acc()
                if msgid or msgstrs:
                    commit()
            mode = "id"
            acc = []
            m = str_re.match(line[6:].strip())
            if m:
                acc.append(m.group(1))
            continue
        if line.startswith("msgstr["):
            if mode == "id":
                msgid = flush_acc()
            elif mode == "id_plural":
                flush_acc()
            elif mode == "str":
                msgstrs[plural_idx] = flush_acc()
            bracket = line.split("]", 1)[0]
            plural_idx = int(bracket.split("[", 1)[1])
            mode = "str"
            acc = []
            rest = line.split("]", 1)[1].strip()
            m = str_re.match(rest)
            if m:
                acc.append(m.group(1))
            continue
        if line.startswith("msgstr "):
            if mode == "id":
                msgid = flush_acc()
            elif mode == "ctxt":
                ctxt = flush_acc()
            elif mode == "str":
                msgstrs[plural_idx] = flush_acc()
            plural_idx = 0
            mode = "str"
            acc = []
            m = str_re.match(line[7:].strip())
            if m:
                acc.append(m.group(1))
            continue
        m = str_re.match(line.strip())
        if m and mode:
            acc.append(m.group(1))

    if mode == "ctxt":
        ctxt = flush_acc()
    elif mode == "id":
        msgid = flush_acc()
    elif mode == "str":
        msgstrs[plural_idx] = flush_acc()
    if msgid or msgstrs:
        commit()
    return entries


def build_lmo(po_text: str) -> bytes:
    entries = parse_po(po_text)
    blob = bytearray()
    index: list[tuple[int, int, int, int]] = []  # key_id, val_id, offset, length

    def pad4(n: int) -> int:
        return (4 - (n % 4)) % 4

    for ctxt, msgid, msgstrs in entries:
        if not msgid and 0 in msgstrs:
            # header: extract Plural-Forms if present
            header = msgstrs[0]
            for part in header.split("\n"):
                if part.lower().startswith("plural-forms:"):
                    field = part.split(":", 1)[1].strip()
                    data = field.encode("utf-8")
                    offset = len(blob)
                    blob.extend(data)
                    blob.extend(b"\0" * pad4(len(data)))
                    index.append((0, 0, offset, len(data)))
            continue

        if not msgid or 0 not in msgstrs:
            continue

        has_plural = len(msgstrs) > 1 or any(i > 0 for i in msgstrs)
        for plural_num, val in sorted(msgstrs.items()):
            if not val:
                continue
            if has_plural:
                if ctxt:
                    key = f"{ctxt}\x01{msgid}\x02{plural_num}"
                else:
                    key = f"{msgid}\x02{plural_num}"
            elif ctxt:
                key = f"{ctxt}\x01{msgid}"
            else:
                key = msgid

            key_b = key.encode("utf-8")
            val_b = val.encode("utf-8")
            key_id = sfh_hash(key_b, len(key_b))
            val_id_hash = sfh_hash(val_b, len(val_b))
            # Skip identity translations (msgid == msgstr content hash).
            if key_id == val_id_hash:
                continue
            offset = len(blob)
            blob.extend(val_b)
            blob.extend(b"\0" * pad4(len(val_b)))
            # Modern luci po2lmo stores plural_num+1 in the val_id field.
            index.append((key_id, plural_num + 1, offset, len(val_b)))

    if not index:
        return b""

    index.sort(key=lambda e: e[0])
    idx_offset = len(blob)
    out = bytearray(blob)
    for key_id, val_id, offset, length in index:
        out.extend(struct.pack("!IIII", key_id, val_id, offset, length))
    out.extend(struct.pack("!I", idx_offset))
    return bytes(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("po", type=Path)
    parser.add_argument("lmo", type=Path)
    args = parser.parse_args()
    text = args.po.read_text(encoding="utf-8")
    data = build_lmo(text)
    if not data:
        raise SystemExit(f"no translations in {args.po}")
    args.lmo.parent.mkdir(parents=True, exist_ok=True)
    args.lmo.write_bytes(data)
    print(f"Wrote {args.lmo} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
