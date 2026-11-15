#!/usr/bin/env bash
# Pack OpenWrt 25.12+ .apk via host apk-tools `apk mkpkg` (ADB format).
# Usage is driven by scripts/build-packages.sh; can also be called standalone.
set -euo pipefail

export LC_ALL=C

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

log() { printf '+ %s\n' "$*"; }

die() {
	echo "ERROR: $*" >&2
	exit 1
}

lf_copy() {
	local src="$1" dest="$2" mode="$3"
	mkdir -p "$(dirname "${dest}")"
	tr -d '\r' <"${src}" >"${dest}"
	chmod "${mode}" "${dest}"
}

# Host builds often use -Dhelp=disabled; --help then fails even when mkpkg exists.
apk_has_mkpkg() {
	local bin="$1" out
	out="$("${bin}" mkpkg 2>&1 || true)"
	printf '%s' "${out}" | grep -q "required info field"
}

need_apk_mkpkg() {
	local bin="${APK_BIN:-apk}"
	if ! command -v "${bin}" >/dev/null 2>&1; then
		die "apk-tools not found (set APK_BIN or install host apk with mkpkg)"
	fi
	if ! apk_has_mkpkg "${bin}"; then
		die "'${bin}' has no mkpkg applet (need host apk-tools built with -Dminimal=false)"
	fi
	APK_BIN="$(command -v "${bin}")"
}

wrap_post_upgrade() {
	local src="$1" dest="$2"
	{
		echo '#!/bin/sh'
		echo 'export PKG_UPGRADE=1'
		tail -n +2 "${src}"
	} >"${dest}"
	chmod 0755 "${dest}"
}

run_mkpkg() {
	if command -v fakeroot >/dev/null 2>&1; then
		fakeroot "${APK_BIN}" mkpkg "$@"
	else
		"${APK_BIN}" mkpkg "$@"
	fi
}

pack_gotify() {
	local package="$1" arch="$2" version="$3" release="$4" bin_path="$5" license="$6" out="$7"
	local files_dir apk_ver stage scripts_dir description
	local mkpkg_args=()

	files_dir="${REPO_ROOT}/net/gotify/files"
	apk_ver="${version}-r${release}"
	stage="$(mktemp -d)"
	scripts_dir="$(mktemp -d)"

	cleanup() {
		rm -rf "${stage}" "${scripts_dir}"
	}
	trap cleanup EXIT

	[ -f "${bin_path}" ] || die "missing binary: ${bin_path}"
	[ -f "${license}" ] || die "missing license: ${license}"

	mkdir -p \
		"${stage}/usr/bin" \
		"${stage}/etc/gotify/data/images" \
		"${stage}/etc/gotify/data/plugins" \
		"${stage}/etc/init.d" \
		"${stage}/usr/share/licenses/${package}" \
		"${stage}/lib/apk/packages"

	install -m 0755 "${bin_path}" "${stage}/usr/bin/gotify"
	lf_copy "${files_dir}/server.env" "${stage}/etc/gotify/server.env" 0644
	lf_copy "${files_dir}/gotify.init" "${stage}/etc/init.d/gotify" 0755
	lf_copy "${license}" "${stage}/usr/share/licenses/${package}/LICENSE" 0644

	printf '%s\n' '/etc/gotify/server.env' >"${stage}/lib/apk/packages/${package}.conffiles"

	lf_copy "${files_dir}/postinst" "${scripts_dir}/post-install" 0755
	wrap_post_upgrade "${scripts_dir}/post-install" "${scripts_dir}/post-upgrade"

	if [ "${package}" = "gotify-zh" ]; then
		description="Gotify push notification server with Chinese Web UI (musl/static for OpenWrt ${arch})"
		mkpkg_args+=(--info "provides:gotify=${apk_ver}")
	else
		description="Gotify push notification server (musl/static for OpenWrt ${arch})"
	fi

	mkdir -p "$(dirname "${out}")"

	log "apk mkpkg ${package} ${apk_ver} arch=${arch}"
	run_mkpkg \
		--info "name:${package}" \
		--info "version:${apk_ver}" \
		--info "description:${description}" \
		--info "arch:${arch}" \
		--info "license:MIT" \
		--info "origin:https://github.com/gotify/server" \
		--info "url:https://gotify.net/" \
		--info "maintainer:Gotify OpenWrt Packaging" \
		--info "depends:ca-bundle" \
		"${mkpkg_args[@]}" \
		--script "post-install:${scripts_dir}/post-install" \
		--script "post-upgrade:${scripts_dir}/post-upgrade" \
		--files "${stage}" \
		--output "${out}"

	trap - EXIT
	cleanup
	log "Wrote ${out}"
}

pack_luci() {
	local version="$1" release="$2" out="$3"
	local apk_ver stage scripts_dir

	apk_ver="${version}-r${release}"
	stage="$(mktemp -d)"
	scripts_dir="$(mktemp -d)"

	cleanup() {
		rm -rf "${stage}" "${scripts_dir}"
	}
	trap cleanup EXIT

	python3 "${SCRIPT_DIR}/stage-luci-root.py" \
		--app "${REPO_ROOT}/luci-app-gotify" \
		--license "${REPO_ROOT}/LICENSE" \
		--out "${stage}/root" \
		--scripts-out "${scripts_dir}"

	mkdir -p "$(dirname "${out}")"

	log "apk mkpkg luci-app-gotify ${apk_ver} arch=noarch"
	run_mkpkg \
		--info "name:luci-app-gotify" \
		--info "version:${apk_ver}" \
		--info "description:LuCI support for Gotify (server.env, service, optional WAN firewall)" \
		--info "arch:noarch" \
		--info "license:MIT" \
		--info "origin:https://github.com/seak/gotify-openwrt" \
		--info "url:https://github.com/seak/gotify-openwrt" \
		--info "maintainer:Gotify OpenWrt Packaging" \
		--info "depends:gotify" \
		--script "post-install:${scripts_dir}/post-install" \
		--script "post-upgrade:${scripts_dir}/post-upgrade" \
		--files "${stage}/root" \
		--output "${out}"

	trap - EXIT
	cleanup
	log "Wrote ${out}"
}

usage() {
	cat >&2 <<'EOF'
Usage:
  pack-apk.sh gotify|gotify-zh --arch ARCH --version VER --release N --bin PATH --license PATH --out PATH
  pack-apk.sh luci-app-gotify --version VER --release N --out PATH
EOF
	exit 2
}

need_apk_mkpkg

cmd="${1:-}"
shift || true
case "${cmd}" in
	gotify|gotify-zh)
		arch="" version="" release="1" bin_path="" license="" out=""
		while [ $# -gt 0 ]; do
			case "$1" in
				--arch) arch="$2"; shift 2 ;;
				--version) version="$2"; shift 2 ;;
				--release) release="$2"; shift 2 ;;
				--bin) bin_path="$2"; shift 2 ;;
				--license) license="$2"; shift 2 ;;
				--out) out="$2"; shift 2 ;;
				*) usage ;;
			esac
		done
		[ -n "${arch}" ] && [ -n "${version}" ] && [ -n "${bin_path}" ] && [ -n "${license}" ] && [ -n "${out}" ] || usage
		pack_gotify "${cmd}" "${arch}" "${version}" "${release}" "${bin_path}" "${license}" "${out}"
		;;
	luci-app-gotify)
		version="" release="1" out=""
		while [ $# -gt 0 ]; do
			case "$1" in
				--version) version="$2"; shift 2 ;;
				--release) release="$2"; shift 2 ;;
				--out) out="$2"; shift 2 ;;
				*) usage ;;
			esac
		done
		[ -n "${version}" ] && [ -n "${out}" ] || usage
		pack_luci "${version}" "${release}" "${out}"
		;;
	*)
		usage
		;;
esac
