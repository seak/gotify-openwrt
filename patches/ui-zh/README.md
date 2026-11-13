# Chinese UI patch / 中文 UI 补丁（v3.1.1）

With `LOCALE=zh`, [`scripts/apply-ui-zh.py`](../../scripts/apply-ui-zh.py) applies [`replacements.json`](replacements.json) on a **temporary copy** of the upstream tree. The `gotify-server` working tree is not modified.

构建时设置 `LOCALE=zh`，[`scripts/apply-ui-zh.py`](../../scripts/apply-ui-zh.py) 会按 [`replacements.json`](replacements.json) 在上游源码的**临时副本**上替换 Web UI 文案，不修改 `gotify-server` 工作树。

## When bumping upstream / 升级上游版本时

1. Update this repo’s `VERSION` and check out the matching official tag.  
   更新本仓 `VERSION`，并检出对应官方 tag。
2. Review English UI diffs: `git -C ../gotify-server diff vOLD..vNEW -- ui/src`.  
   查看英文 UI 新增/变更（同上命令）。
3. Refresh `replacements.json` and `SPECIALS` in `apply-ui-zh.py`.  
   同步更新 `replacements.json` 与 `apply-ui-zh.py` 中的 `SPECIALS`。
4. Smoke-build with `LOCALE=zh TARGET=x86_64` (login, messages, apps, clients, users, settings).  
   用 `LOCALE=zh TARGET=x86_64` 冒烟构建（登录、消息、应用、客户端、用户、设置）。
