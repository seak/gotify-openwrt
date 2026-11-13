# 设计说明

[English](DESIGN.md) | [简体中文](DESIGN.zh-CN.md)

说明本打包方案为何如此设计，以及在真实路由器上遇到的坑。构建/安装见 [README.zh-CN.md](../README.zh-CN.md)。发行说明见 [CHANGELOG.md](../CHANGELOG.md)。

目标：OpenWrt **24.10**，`x86/64`（`x86_64`）与 `bcm27xx/bcm2710`（树莓派 3，`aarch64_cortex-a53`）。在 24.10 上，Pi 3 为 **64 位 aarch64**，不是 armv7。上游讨论：[gotify/server#861](https://github.com/gotify/server/issues/861)。

## 为何不用官方二进制 / SDK 里的 Go

| 约束 | 说明 |
|------|------|
| libc | 官方 `gotify-linux-*` 构建通常是 **glibc** 动态链接；OpenWrt 默认 **musl**。常见现象：`not found`、`fcntl64: symbol not found`。 |
| CGO | 默认数据库驱动为 `mattn/go-sqlite3`；`CGO_ENABLED=0` 启动会 panic。 |
| Feed Go | 24.10 `packages` 中的 golang 约 **1.23**；官方 v3.1.1 需要 **Go ≥ 1.25**，因此 SDK 的 `golang-package.mk` 无法编译该源码树。 |

做法：**在主机用 Go 1.26 + musl 交叉编译出静态二进制 → 打成 gzip 格式的 OpenWrt `.ipk`**。主机可选 [`scripts/Dockerfile`](../scripts/Dockerfile) 镜像，或对齐的 WSL/本机工具链（[`scripts/setup-wsl-toolchain.sh`](../scripts/setup-wsl-toolchain.sh)）。`net/gotify/Makefile` 仅作 feed 元数据；主路径不用 SDK 编译 Go。路由器侧用法（`opkg install`、`/etc/init.d/gotify`）与完整 SDK 软件包一致。

**不修改 Gotify 应用代码。** 配置基于环境变量（`godotenv`）；本软件包提供 `/etc/gotify/server.env`，而非旧的 YAML `config.yml`。

## 关键决策

### 交叉编译

- `CGO_ENABLED=1`，`CC` 指向对应的 musl 交叉编译器
- `-linkmode external -extldflags=-static`
- 先执行 `yarn build`，确保存在可供 `//go:embed` 使用的 `ui/build/*`

### 版本

- 仅使用本仓库的 `VERSION` 文件（可用环境变量覆盖）；缺少版本则构建失败——不会生成 `0.0.0-unknown`
- 软件包名：`gotify_${VERSION}-${PKG_RELEASE}_${PKG_ARCH}.ipk` 或 `gotify-zh_…`（当前 `PKG_RELEASE=1`）
- 注入：`main.Version` / `Commit` / `BuildDate` / `Mode=prod`
- 在原生构建上用 `gotify version` 校验，或在交叉构建上检查嵌入字符串（不要依赖 Go 1.26 的 `go version -m` 列出 `-X`）

### 打包署名（所有语言包）

[`scripts/apply-ui-branding.py`](../scripts/apply-ui-branding.py) 作用于**构建时的源码副本**：

- 内页顶栏：在上游 `@version` 后增加更淡的 `seak/gotify-openwrt`（不替代 Gotify 品牌）

链接到 [seak/gotify-openwrt](https://github.com/seak/gotify-openwrt)。在中文替换之后执行，故 `gotify-zh` 仍保留英文署名。

### 中文 Web UI（`LOCALE=zh` → `gotify-zh`）

上游 UI 无 i18n，文案硬编码为英文。本仓库通过 [`scripts/apply-ui-zh.py`](../scripts/apply-ui-zh.py) 按 [`patches/ui-zh/replacements.json`](../patches/ui-zh/replacements.json) 在**构建时的源码副本**上替换，再经 `yarn build` 嵌入 UI。**不会**改动 `gotify-server` 工作树。

- 软件包 `gotify-zh` 与 `gotify` 相互 `Conflicts`；`gotify-zh` 同时 `Provides: gotify`
- 安装路径与英文包相同；数据可在切换语言包时保留
- 无运行时语言切换

升级上游 tag 时：

1. 更新本仓库的 `VERSION` 并检出对应 tag  
2. `git -C ../gotify-server diff vOLD..vNEW -- ui/src`  
3. 刷新 `apply-ui-zh.py` 中的 `replacements.json` / `SPECIALS`  
4. 使用 `LOCALE=zh` 构建并冒烟测试（登录、消息、应用、客户端、用户、设置）  
5. 更新 `CHANGELOG.md`

### 数据目录（不要依赖 `/var`）

在 OpenWrt 上，**`/var` → `/tmp`（tmpfs）**。写在 `/var/lib/gotify` 下的路径实际落在 `/tmp`，重启后丢失。

| 用途 | 路径 |
|------|------|
| 配置 | `/etc/gotify/server.env` |
| 数据库 / 图片 / 插件 | `/etc/gotify/data/`（overlay，持久） |
| 监听 | **8080**（避开占用 80 的 LuCI/`uhttpd`） |

`gotify.init` 通过 procd 环境变量强制数据相关设置（进程环境优先于 `server.env`）：

- `GOTIFY_DATABASE_CONNECTION=/etc/gotify/data/gotify.db`
- `GOTIFY_UPLOADEDIMAGESDIR=/etc/gotify/data/images`
- `GOTIFY_PLUGINSDIR=/etc/gotify/data/plugins`

`postinst` 会把 `server.env` 中的 `/var/lib/gotify` 与 `/tmp/lib/gotify` 改写为 `/etc/gotify/data`，在可能时迁移已有数据库文件，然后 enable/start。

### 换行与 `.ipk` 格式

- Windows 检出可能导致 init 为 CRLF，从而破坏 ash/procd → `.gitattributes` 强制 LF；打包前剥离 `\r`；init/postinst 权限 0755
- OpenWrt 24.x 期望 **gzip tar**（`debian-binary` + `control.tar.gz` + `data.tar.gz`），而非经典 `ar`；`ar` 包会被拒绝为 *Malformed package file*

## 现象 → 处理

| 现象 | 原因 | 处理 |
|------|------|------|
| 官方 amd64 二进制无法运行 | glibc 与 musl | 使用 musl 静态自建软件包 |
| `/etc/init.d/gotify` 行为异常 | CRLF | LF，打包时剥离 `\r` |
| 数据落在 `/tmp/lib/gotify` | `/var`→`/tmp` + 旧配置 | `/etc/gotify/data` + 强制环境变量 + postinst |
| 软件包名 / `gotify version` 为 unknown | 无 VERSION 或缺少 `-X` | 要求 `VERSION` + 构建自检 |
| SDK golang 构建失败 | feed 中 Go 过旧 | 用外部 Go 构建二进制，只打包 ipk |

## LuCI 应用（`luci-app-gotify`）

可选 LuCI 包位于本仓库 `luci-app-gotify/`。**不**引入 Gotify UCI：配置仍在 `/etc/gotify/server.env`。rpcd 插件 `luci.gotify` 读写端口、监听地址、日志级别、是否开放注册；启停/开机自启调用 `/etc/init.d/gotify`。数据路径仍由主包 init 强制。

WAN 访问**默认关闭**。在 LuCI 中开启时，会创建或更新名为 `gotify` 的 firewall UCI 规则（WAN TCP 放行当前端口）。主包 `gotify` / `gotify-zh` 仍不附带防火墙规则。

不在 LuCI 内管理消息/应用/客户端——使用配置端口上的 Gotify Web UI。翻译：`scripts/po2lmo.py` 将 `po/zh_Hans` 编译为同一 `luci-app-gotify` 包内的 `/usr/lib/lua/luci/i18n/gotify.zh-cn.lmo`（不另打语言包）。LuCI 语言为简体中文时显示中文，英文为默认 msgid。`.po` 源文件仍放在 `/usr/share/luci-app-gotify/po/`。

## 许可证（上游）

打包须遵守 [gotify/server LICENSE](https://github.com/gotify/server/blob/master/LICENSE)：

- **MIT**：Gotify 代码（及 `.ipk` 中再分发的实质性部分）须保留版权与许可声明；元数据为 `License: MIT` / `PKG_LICENSE:=MIT`；`pack-ipk.py` 将上游 `LICENSE` 安装到 `/usr/share/licenses/<package>/LICENSE`。
- **CC BY 4.0**：Gotify Logo（随上游 UI 资源嵌入）；若在上游 UI 之外再使用或修改 Logo，须按协议署名。
- 本仓库打包内容为 MIT（[`LICENSE`](../LICENSE)）；`luci-app-gotify` 将该文件装到 `/usr/share/licenses/luci-app-gotify/LICENSE`。
- 顶栏打包署名不替代 Gotify 品牌，也不表示获得官方背书。

面向用户的摘要见 [README.zh-CN.md § 许可证](../README.zh-CN.md#许可证)。

## 明确不在范围内

- 不修改上游应用代码（UI 补丁仅作用于构建副本：中文文案 + 打包署名）  
- 无 Gotify 应用内语言切换 / 完整 i18n 框架  
- 本阶段无 Gotify UCI（`/etc/config/gotify`）  
- 不打包官方插件 `.so`（与 musl/本工具链 ABI 不兼容）  
- 主包不自动添加 WAN 防火墙（仅可通过 `luci-app-gotify` 可选开启）  

