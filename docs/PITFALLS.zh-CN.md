# 常见陷阱

[English](PITFALLS.md) | [简体中文](PITFALLS.zh-CN.md)

OpenWrt 上易踩的坑与维护时容易遗漏的注意点。构建/安装见 [README.zh-CN.md](../README.zh-CN.md)。发行说明见 [CHANGELOG.md](../CHANGELOG.md)。

## 现象 → 处理

| 现象 | 原因 | 处理 |
|------|------|------|
| 官方 amd64 二进制无法运行 | glibc 与 musl | 使用 musl 静态自建软件包 |
| `/etc/init.d/gotify` 行为异常 | CRLF | LF，打包时剥离 `\r` |
| 数据落在 `/tmp/lib/gotify` | `/var`→`/tmp` + 旧配置 | `/etc/gotify/data` + 强制环境变量 + postinst |
| 软件包名 / `gotify version` 为 unknown | 无 VERSION 或缺少 `-X` | 要求 `VERSION` + 构建自检 |
| SDK golang 构建失败 | feed 中 Go 过旧 | 用外部 Go 构建二进制，只打包软件包 |
| `opkg install` 报 *Malformed package file* | 经典 `ar` 格式 `.ipk` | OpenWrt 24.x 需要 gzip tar（`debian-binary` + `control.tar.gz` + `data.tar.gz`） |
| `apk add` 拒绝软件包 / 格式无效 | 把 `.ipk` 改后缀或手搓旧版 apk | 使用本仓 `apk mkpkg` 打出的 ADB `.apk`；禁止 `.ipk`→`.apk` 改名 |
| 构建机没有 `apk mkpkg` | 设备端 / minimal apk-tools | 安装带 `-Dminimal=false` 的 host apk-tools（Docker / `setup-wsl-toolchain.sh`） |
| 官方插件 `.so` 无法加载 | ABI / musl 不兼容 | 本软件包不在范围内 |

## 数据目录（`/var` 不持久）

在 OpenWrt 上，**`/var` → `/tmp`（tmpfs）**。写在 `/var/lib/gotify` 下的路径实际落在 `/tmp`，重启后丢失。

`gotify.init` 通过 procd 环境变量强制数据相关设置（进程环境优先于 `server.env`）：

- `GOTIFY_DATABASE_CONNECTION=/etc/gotify/data/gotify.db`
- `GOTIFY_UPLOADEDIMAGESDIR=/etc/gotify/data/images`
- `GOTIFY_PLUGINSDIR=/etc/gotify/data/plugins`

`postinst` 会把 `server.env` 中的 `/var/lib/gotify` 与 `/tmp/lib/gotify` 改写为 `/etc/gotify/data`，在可能时迁移已有数据库文件，然后 enable/start。

## 换行与软件包格式

- Windows 检出可能导致 init 为 CRLF，从而破坏 ash/procd → `.gitattributes` 强制 LF；打包前剥离 `\r`；init/postinst 权限 0755
- OpenWrt **24.10**（opkg）：拒绝经典 `ar` 包；须输出 **gzip tar** `.ipk`
- OpenWrt **25.12**（apk）：须用 host `apk mkpkg` 打 ADB `.apk`；`.ipk` 与 `.apk` 不可互换
- 产物在 `bin/packages/24.10/` 与 `bin/packages/25.12/`；文件名不嵌入发行版号（扩展名 + 目录对本仓出树包已够）

## 宣称支持更新的 OpenWrt 发行版

没有自动跨大版本保证。写入文档前：

1. 核对包管理器/格式、架构名、依赖名、procd/LuCI 路径与发行说明。
2. 在目标版本冒烟：安装、启动、Web UI、数据持久化、LuCI、中英包互斥、卸载再装。
3. 现有配方可用则放入对应发行版输出目录（或扩展文档矩阵）；失败则改配方，并保留旧目录给未升级用户。

## 版本注入校验

- 仅使用本仓库的 `VERSION` 文件（可用环境变量覆盖）；缺少版本则构建失败——不会生成 `0.0.0-unknown`
- 注入：`main.Version` / `Commit` / `BuildDate` / `Mode=prod`
- 在原生构建上用 `gotify version` 校验，或在交叉构建上检查嵌入字符串（**不要**依赖 Go 1.26 的 `go version -m` 列出 `-X`）

## 交叉编译必做项

跳过任一项都会导致二进制或内嵌 UI 异常：

- `CGO_ENABLED=1`，`CC` 指向对应的 musl 交叉编译器
- `-linkmode external -extldflags=-static`（默认数据库驱动为 `mattn/go-sqlite3`；`CGO_ENABLED=0` 启动会 panic）
- 先执行 `yarn build`，确保存在可供 `//go:embed` 使用的 `ui/build/*`

## 升级上游时的 `gotify-zh`

上游 UI 无 i18n；中文替换仅作用于**构建时的源码副本**。升级上游 tag 时：

1. 更新本仓库的 `VERSION` 并检出对应 tag  
2. `git -C ../gotify-server diff vOLD..vNEW -- ui/src`  
3. 刷新 `apply-ui-zh.py` 中的 `replacements.json` / `SPECIALS`  
4. 使用 `LOCALE=zh` 构建并冒烟测试（登录、消息、应用、客户端、用户、设置）  
5. 更新 `CHANGELOG.md`

打包署名（`apply-ui-branding.py`）在中文替换之后执行，故 `gotify-zh` 仍保留英文署名。
