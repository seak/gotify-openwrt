include $(TOPDIR)/rules.mk

LUCI_TITLE:=LuCI support for Gotify Server
LUCI_DESCRIPTION:=Manage Gotify Server settings (server.env), start/stop, and optional WAN firewall access.
LUCI_DEPENDS:=+gotify
LUCI_PKGARCH:=all

PKG_LICENSE:=MIT
PKG_MAINTAINER:=Gotify OpenWrt Packaging

include $(TOPDIR)/feeds/luci/luci.mk

# call BuildPackage - OpenWrt buildroot signature
