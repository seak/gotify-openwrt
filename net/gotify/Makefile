include $(TOPDIR)/rules.mk

# Feed definition only.
#
# OpenWrt 24.10's packages feed ships Go 1.23. Gotify v3.1.1 requires
# Go >= 1.25 (toolchain go1.26.0) and CGO for mattn/go-sqlite3, so this
# Makefile cannot build the package on 24.10. Produce the .ipk with the
# Docker image in scripts/ (Go 1.26, musl static):
#
#   scripts/build-ipk.sh
#
# github.com/gotify/server/v3's main package installs a binary named "v3".
# Install that file as /usr/bin/gotify. Do not ship a v2 binary.

PKG_NAME:=gotify
PKG_VERSION:=$(shell tr -d ' \t\r\n' < $(CURDIR)/../../VERSION 2>/dev/null || echo 3.1.1)
PKG_RELEASE:=2

PKG_SOURCE_PROTO:=git
PKG_SOURCE_URL:=https://github.com/gotify/server.git
PKG_SOURCE_VERSION:=e6361caa512547052b1013dbf4544e6d7ff32604
PKG_MIRROR_HASH:=skip

PKG_MAINTAINER:=Gotify OpenWrt Packaging
PKG_LICENSE:=MIT
PKG_LICENSE_FILES:=LICENSE

PKG_BUILD_DEPENDS:=golang/host
PKG_BUILD_PARALLEL:=1
PKG_BUILD_FLAGS:=no-mips16

GO_PKG:=github.com/gotify/server/v3
GO_PKG_BUILD_PKG:=$(GO_PKG)

GO_PKG_LDFLAGS_X:= \
	main.Version=$(PKG_VERSION) \
	main.Commit=$(PKG_SOURCE_VERSION) \
	main.BuildDate=$(shell date -u +%Y-%m-%dT%H:%M:%SZ) \
	main.Mode=prod

include $(INCLUDE_DIR)/package.mk
include $(TOPDIR)/feeds/packages/lang/golang/golang-package.mk

define Package/gotify
  SECTION:=net
  CATEGORY:=Network
  SUBMENU:=Web Servers/Proxies
  TITLE:=Gotify push notification server
  URL:=https://gotify.net/
  DEPENDS:=$(GO_ARCH_DEPENDS) +ca-bundle
  CONFLICTS:=gotify-zh
endef

define Package/gotify/description
  Gotify is a self-hosted push notification server (English Web UI).
  Chinese UI package is gotify-zh. On OpenWrt 24.10 use scripts/build-ipk.sh.
endef

define Package/gotify/conffiles
/etc/gotify/server.env
endef

define Build/Prepare
	$(Build/Prepare/Default)
	if [ ! -f "$(PKG_BUILD_DIR)/ui/build/index.html" ]; then \
		echo "ERROR: ui/build is missing. Use scripts/build-ipk.sh (Go 1.26 + musl)." >&2; \
		exit 1; \
	fi
endef

define Package/gotify/install
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) $(GO_PKG_BUILD_BIN_DIR)/v3 $(1)/usr/bin/gotify

	$(INSTALL_DIR) $(1)/etc/gotify
	$(INSTALL_CONF) ./files/server.env $(1)/etc/gotify/server.env

	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./files/gotify.init $(1)/etc/init.d/gotify

	$(INSTALL_DIR) $(1)/etc/gotify/data/images
	$(INSTALL_DIR) $(1)/etc/gotify/data/plugins
endef

$(eval $(call GoBinPackage,gotify))
$(eval $(call BuildPackage,gotify))
