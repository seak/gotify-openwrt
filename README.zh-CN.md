# Gotify OpenWrt 软件包

[English](README.md) | [简体中文](README.zh-CN.md)

面向 [OpenWrt](https://openwrt.org/) 的独立 [Gotify](https://gotify.net/) 打包。基于官方 [gotify/server](https://github.com/gotify/server) 构建 **musl 静态**二进制，并打成 `.ipk`。不修改上游应用代码。

设计说明与设备上的注意事项：[docs/DESIGN.zh-CN.md](docs/DESIGN.zh-CN.md)。

## 为什么需要这个仓库

| 约束 | 说明 |
|------|------|
| libc | 官方发布二进制多为 glibc 动态链接；OpenWrt 使用 musl。 |
| CGO | 默认 SQLite 驱动为 `mattn/go-sqlite3`；`CGO_ENABLED=0` 启动会 panic。 |
| Go 版本 | 当前上游需要 Go ≥ 1.25；OpenWrt 24.10 源码树中的 Go 过旧，无法在树内编译。 |

因此本仓库在 OpenWrt SDK **之外**用 Go 1.26 + musl 交叉编译器构建（Docker 镜像，或对齐的 WSL/本机工具链）。[`net/gotify/Makefile`](net/gotify/Makefile) 仅作 feed 元数据。

软件包版本钉在 [`VERSION`](VERSION)；当前发行见 [CHANGELOG](CHANGELOG.md) / [Releases](https://github.com/seak/gotify-openwrt/releases)。

### 支持的目标

| 维度 | 当前 |
|------|------|
| OpenWrt | **24.10**（已验证；其它发行版未保证） |
| 架构 | 见下表 |

| `TARGET` | OpenWrt 架构 | 典型设备 |
|----------|--------------|----------|
| `x86_64` | `x86_64` | x86/64 软路由、虚拟机 |
| `bcm2710` | `aarch64_cortex-a53` | 树莓派 3（64 位） |

后续可能增加更多 OpenWrt 发行版 / 架构。

### UI 语言

上游 Gotify 无 i18n；本仓库提供独立软件包（安装路径相同，彼此 **Conflicts**）。`/etc/gotify/data` 下的数据可在切换语言包时保留。产物命名见 [CHANGELOG](CHANGELOG.md)。

| `LOCALE` | 软件包 | UI |
|----------|--------|-----|
| `en`（默认） | `gotify` | 英文（上游） |
| `zh` | `gotify-zh` | 中文（[`patches/ui-zh`](patches/ui-zh)） |

源码默认使用同级目录 `../gotify-server` 的对应 tag。版本仅来自 [`VERSION`](VERSION)，通过 `-X main.Version` 注入（缺失或为 `unknown` 时构建失败）。

## 构建

前置：同级目录 `../gotify-server` 检出为 tag `v$(cat VERSION)`（HEAD 必须等于该 tag）。路由器运行时**不需要** Docker 或 Go 工具链。

| 环境变量 | 含义 |
|----------|------|
| `TARGET` | `x86_64`、`bcm2710` 或 `all` |
| `LOCALE` | `en`（默认 → 软件包 `gotify`）或 `zh`（→ `gotify-zh`） |
| `GOTIFY_SRC` | 源码路径（Docker 默认 `/gotify-server`；本机默认 `../gotify-server`） |

产物：`build/`（二进制）与 `bin/packages/<arch>/<pkg>/`（`.ipk`）。`GOPROXY` 默认优先 `goproxy.cn`。[`scripts/verify-ipk.py`](scripts/verify-ipk.py) 会检查软件包布局、LF、权限与版本。每次构建还会打包 `luci-app-gotify`（`Architecture: all`）。

### Docker（可复现）

主机需要 Docker（Windows：Docker Desktop + WSL2，且引擎已运行）。不使用主机上的 Go/Node。

```powershell
docker build -t gotify-openwrt-builder -f scripts/Dockerfile scripts

docker run --rm `
  -v "${PWD}:/src" `
  -v "${PWD}\..\gotify-server:/gotify-server:ro" `
  -e TARGET=x86_64 `
  gotify-openwrt-builder
```

### WSL / 本机（无 Docker）

工具链须与 [`scripts/Dockerfile`](scripts/Dockerfile) 对齐：Go **1.26**、Node + Yarn **1.x**、`x86_64-linux-musl-gcc`（编 `bcm2710` / `all` 时还需 `aarch64-linux-musl-gcc`）。一键安装（装到 `~/.local`，Go/Node/musl 交叉编译器无需 sudo）：

```bash
./scripts/setup-wsl-toolchain.sh
# 新开 shell，或: . ~/.local/gotify-openwrt-env.sh
TARGET=x86_64 LOCALE=en ./scripts/build-ipk.sh
```

若下载卡住，可按 Dockerfile 中的文件名自行解压到 `~/.local/opt/`（Go/Node 目录布局与 musl 的 `*-linux-musl-cross/`），再重跑脚本（已存在的组件会跳过）。

## 安装

按架构从 [release](https://github.com/seak/gotify-openwrt/releases) 或本地 `bin/packages/` 选取 `.ipk`（文件名中的 `<ver>` 来自 [`VERSION`](VERSION) + `PKG_RELEASE`），然后：

```sh
scp gotify_<ver>_x86_64.ipk root@router:/tmp/
opkg update
opkg install /tmp/gotify_<ver>_x86_64.ipk

# 可选 LuCI 管理（Architecture: all；Depends: gotify，gotify-zh 的 Provides 亦可满足）。
# 同一 ipk 已内嵌中文 LuCI 文案（gotify.zh-cn.lmo）；将 LuCI 语言设为简体中文即可。
scp luci-app-gotify_<ver>_all.ipk root@router:/tmp/
opkg install /tmp/luci-app-gotify_<ver>_all.ipk
```

| 路径 | 作用 |
|------|------|
| `/usr/bin/gotify` | musl 静态二进制（内嵌 Web UI） |
| `/etc/gotify/server.env` | 配置（conffile） |
| `/etc/gotify/data/` | 数据库、图片、插件（overlay；重启后保留） |
| `/etc/init.d/gotify` | procd 服务 |
| LuCI → 服务 → Gotify | 可选：编辑 `server.env`、启停、WAN 防火墙开关 |

Web UI：`http://<路由器IP>:8080`。默认账号 `admin` / `admin`——首次登录后请修改。仅依赖 `ca-bundle`。

在 OpenWrt 上，`/var` → `/tmp`（tmpfs），因此数据不能放在 `/var` 下。本软件包通过 procd 环境变量强制使用 `/etc/gotify/data`，并在 `postinst` 中迁移旧的 `/var|/tmp` 路径。主包不添加防火墙规则；`luci-app-gotify` 可按需开启 WAN 规则。官方插件 `.so` 与本构建 ABI 不兼容。

## 目录结构

```text
LICENSE                 # 本仓库打包内容的 MIT 许可
VERSION                 # 上游版本钉扎
CHANGELOG.md            # 软件包产物与打包变更
docs/DESIGN.md          # 设计说明（英文）
docs/DESIGN.zh-CN.md    # 设计说明（简体中文）
net/gotify/             # 软件包 feed + procd 文件
net/gotify-zh/          # 中文 UI 变体（共享 files/）
luci-app-gotify/        # 可选 LuCI 应用（编辑 server.env，无 Gotify UCI）
patches/ui-zh/          # UI 文案替换（仅作用于构建副本）
scripts/                # Dockerfile、WSL 工具链、构建、打包、校验、署名
```

`bin/`、`build/` 与 `graphify-out/` 不纳入版本控制。脚本、`net/gotify/files` 与 `luci-app-gotify` 强制使用 LF 换行。

## 许可证

本仓库仅对 [gotify/server](https://github.com/gotify/server) 做 OpenWrt 打包。再分发的二进制与内嵌 Web UI 须遵守上游协议，见官方 [LICENSE](https://github.com/gotify/server/blob/master/LICENSE)：

| 组成部分 | 协议 | 要求 |
|----------|------|------|
| Gotify 服务端（代码、UI 文案等） | [MIT](https://opensource.org/licenses/MIT) | 在所有副本或实质性部分中保留版权声明与许可声明。Copyright (c) 2018 [jmattheis](https://github.com/jmattheis)。 |
| Gotify Logo | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | 若再使用或修改 Logo，须适当署名、附上协议链接，并注明是否修改。 |
| 本仓库打包内容 | [MIT](LICENSE) | 根目录 [`LICENSE`](LICENSE) 覆盖脚本、`net/gotify*` 与 `luci-app-gotify`。 |

`.ipk` 元数据声明 `License: MIT`。主包将上游 Gotify 许可全文装到 `/usr/share/licenses/gotify/LICENSE` 或 `/usr/share/licenses/gotify-zh/LICENSE`；`luci-app-gotify` 将本仓库 [`LICENSE`](LICENSE) 装到 `/usr/share/licenses/luci-app-gotify/LICENSE`。本项目与 Gotify 作者无隶属或背书关系。
