#!/usr/bin/env python3
"""Apply Chinese UI string replacements to a gotify-server work tree (in place)."""
from __future__ import annotations

import json
import pathlib
import re
import sys

SKIP_DIRS = {"tests", "node_modules", "build"}

# Longer / more specific fragments first. Applied after JSON map.
SPECIALS: list[tuple[str, str]] = [
    (
        "Send a push message via {appName}. Leave the title empty to use the application\n"
        "                    name.",
        "通过 {appName} 发送推送消息。标题留空则使用应用名称。",
    ),
    (
        "'Regenerate token for ' +\n"
        "                        toRegenerateTokenApp.name +\n"
        "                        '? The current token will be invalidated.'",
        "'重新生成 ' +\n"
        "                        toRegenerateTokenApp.name +\n"
        "                        ' 的令牌？当前令牌将立即失效。'",
    ),
    ("'Delete image for ' + toDeleteImage.name + '?'", "'删除 ' + toDeleteImage.name + ' 的图标？'"),
    ("'Delete all messages?'", "'删除全部消息？'"),
    ("'Delete ' + toDeleteApp.name + '?'", "'删除 ' + toDeleteApp.name + '？'"),
    ("'Delete ' + toDeleteClient.name + '?'", "'删除 ' + toDeleteClient.name + '？'"),
    ("'Delete ' + deleteUser.name + '?'", "'删除 ' + deleteUser.name + '？'"),
    ("'Edit ' + name", "'编辑 ' + name"),
    ("Elevate Client: {clientName}", "提权客户端：{clientName}"),
    ("Login with {oidcIdpName}", "使用 {oidcIdpName} 登录"),
    ("Elevate via {oidcIdpName}", "通过 {oidcIdpName} 提权"),
    ("Waiting for {oidcIdpName} sign-in...", "等待 {oidcIdpName} 登录…"),
    ("Cancel {oidcIdpName} Login", "取消 {oidcIdpName} 登录"),
    ("title=\"Delete image\"", "title=\"删除图标\""),
    ("alt=\"app logo\"", "alt=\"应用图标\""),
    ("locale: 'en'", "locale: 'zh-CN'"),
    (
        "setError('Elevation failed. Check your password.');",
        "setError('提权失败，请检查密码。');",
    ),
    (
        "this.snack(`Plugin ${enabled ? 'enabled' : 'disabled'}`);",
        "this.snack(`插件已${enabled ? '启用' : '禁用'}`);",
    ),
    (
        "this.snack(`Deleted all messages from ${this.appStore.getByID(appId).name}`);",
        "this.snack(`已删除来自 ${this.appStore.getByID(appId).name} 的全部消息`);",
    ),
    (
        "this.snack(`Message sent to ${app.name}`);",
        "this.snack(`消息已发送至 ${app.name}`);",
    ),
    (
        "this.snack(`A client named '${name}' was created for your session.`);",
        "this.snack(`已为本次会话创建名为「${name}」的客户端。`);",
    ),
    (
        "this.snack(\n"
        "                    `Register failed: ${data?.error ?? 'unknown'}: ${data?.errorDescription ?? ''}`\n"
        "                );",
        "this.snack(\n"
        "                    `注册失败：${data?.error ?? '未知'}：${data?.errorDescription ?? ''}`\n"
        "                );",
    ),
    (
        "this.snack(`${config.get('oidcIdpName')} elevation was not completed.`);",
        "this.snack(`${config.get('oidcIdpName')} 提权未完成。`);",
    ),
    ("Custom Route Prefix:{' '}", "自定义路由前缀：{' '}"),
    ("Name: <span>", "名称：<span>"),
    ("Author: <span>", "作者：<span>"),
    ("Module Path: <span>", "模块路径：<span>"),
    ("Website: <span>", "网站：<span>"),
    ("License: <span>", "许可证：<span>"),
    ("Capabilities: <span>", "能力：<span>"),
]


def load_pairs(path: pathlib.Path) -> list[tuple[str, str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    pairs: list[tuple[str, str]] = []
    for item in raw:
        en, zh = item[0], item[1]
        if zh == "PLACEHOLDER_SKIP" or not en or en == zh:
            continue
        pairs.append((en, zh))
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


def apply_quoted(text: str, en: str, zh: str) -> str:
    if en not in text:
        return text
    for q in ("'", '"', "`"):
        text = text.replace(f"{q}{en}{q}", f"{q}{zh}{q}")
    return text


def apply_jsx_text(text: str, en: str, zh: str) -> str:
    # >Login<  /  >\n    Login\n<
    pattern = re.compile(
        r">(\s*)" + re.escape(en) + r"(\s*)<",
        re.MULTILINE,
    )
    return pattern.sub(lambda m: f">{m.group(1)}{zh}{m.group(2)}<", text)


def transform(text: str, pairs: list[tuple[str, str]]) -> str:
    for en, zh in SPECIALS:
        if en in text:
            text = text.replace(en, zh)
    for en, zh in pairs:
        text = apply_quoted(text, en, zh)
        text = apply_jsx_text(text, en, zh)
    return text


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} <gotify-server-workdir>")
    root = pathlib.Path(sys.argv[1]).resolve()
    ui_src = root / "ui" / "src"
    if not ui_src.is_dir():
        raise SystemExit(f"ERROR: missing {ui_src}")

    script_dir = pathlib.Path(__file__).resolve().parent
    pairs_path = script_dir.parent / "patches" / "ui-zh" / "replacements.json"
    pairs = load_pairs(pairs_path)

    changed = 0
    for path in sorted(ui_src.rglob("*")):
        if not path.is_file() or path.suffix not in {".ts", ".tsx"}:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        original = path.read_text(encoding="utf-8")
        updated = transform(original, pairs)
        if updated != original:
            path.write_text(updated, encoding="utf-8", newline="\n")
            changed += 1
            print(f"zh: {path.relative_to(root)}")
    print(f"Applied Chinese UI replacements to {changed} file(s)")


if __name__ == "__main__":
    main()
