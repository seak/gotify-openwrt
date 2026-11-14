include $(TOPDIR)/rules.mk

# Chinese Web UI variant of net/gotify.
# Shares procd files with ../gotify/files. Build with:
#
#   LOCALE=zh scripts/build-ipk.sh
#
# Conflicts with Package/gotify (same /usr/bin/gotify paths).

PKG_NAME:=gotify-zh
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

GOTIFY_FILES:=$(CURDIR)/../gotify/files

define Package/gotify-zh
  SECTION:=net
  CATEGORY:=Network
  SUBMENU:=Web Servers/Proxies
  TITLE:=Gotify push notification server (Chinese UI)
  URL:=https://gotify.net/
  DEPENDS:=$(GO_ARCH_DEPENDS) +ca-bundle
  CONFLICTS:=gotify
  PROVIDES:=gotify
endef

define Package/gotify-zh/description
  Gotify with a Chinese Web UI (build-time string replacements).
  On OpenWrt 24.10 build with LOCALE=zh scripts/build-ipk.sh.
endef

define Package/gotify-zh/conffiles
/etc/gotify/server.env
endef

define Build/Prepare
	$(Build/Prepare/Default)
	if [ ! -f "$(PKG_BUILD_DIR)/ui/build/index.html" ]; then \
		echo "ERROR: ui/build is missing. Use LOCALE=zh scripts/build-ipk.sh." >&2; \
		exit 1; \
	fi
endef

define Package/gotify-zh/install
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) $(GO_PKG_BUILD_BIN_DIR)/v3 $(1)/usr/bin/gotify

	$(INSTALL_DIR) $(1)/etc/gotify
	$(INSTALL_CONF) $(GOTIFY_FILES)/server.env $(1)/etc/gotify/server.env

	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) $(GOTIFY_FILES)/gotify.init $(1)/etc/init.d/gotify

	$(INSTALL_DIR) $(1)/etc/gotify/data/images
	$(INSTALL_DIR) $(1)/etc/gotify/data/plugins
endef

$(eval $(call GoBinPackage,gotify-zh))
$(eval $(call BuildPackage,gotify-zh))
