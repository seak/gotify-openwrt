#!/usr/bin/env bash
# Build musl-static Gotify binaries from a gotify-server checkout and pack OpenWrt packages.
#
# TARGET=x86_64    OpenWrt x86/64                 PKG_ARCH=x86_64
# TARGET=bcm2710   Raspberry Pi 3 bcm27xx/bcm2710 PKG_ARCH=aarch64_cortex-a53
# TARGET=all       both of the above
#
# LOCALE=en        English Web UI → package gotify (default)
# LOCALE=zh        Chinese Web UI → package gotify-zh (Conflicts with gotify)
#
# PKG_FORMAT=all   pack OpenWrt 24.10 .ipk and 25.12 .apk (default)
# PKG_FORMAT=ipk   only 24.10 .ipk (opkg)
# PKG_FORMAT=apk   only 25.12 .apk (apk mkpkg)
#
# Outputs:
#   bin/packages/24.10/<arch|all>/<pkg>/*.ipk
#   bin/packages/25.12/<arch|noarch>/<pkg>/*.apk
#
# The packaging repo is this tree. Source defaults to ../gotify-server and must be tag v${VERSION}.
# Inside the Docker image the repo is mounted at /src and the source at /gotify-server.
set -euo pipefail

export LC_ALL=C

if [ -n "${GOTIFY_OPENWRT_ROOT:-}" ]; then
	REPO_ROOT="$(cd "${GOTIFY_OPENWRT_ROOT}" && pwd)"
else
	REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
SCRIPT_DIR="${REPO_ROOT}/scripts"

log() { printf '+ %s\n' "$*"; }

need_cmd() {
	command -v "$1" >/dev/null 2>&1 || {
		echo "ERROR: required command not found: $1" >&2
		exit 1
	}
}

need_cmd git
need_cmd go
need_cmd python3
need_cmd tar
need_cmd file

TARGET="${TARGET:-x86_64}"
LOCALE="${LOCALE:-en}"
case "${LOCALE}" in
	en)
		PKG_NAME=gotify
		;;
	zh)
		PKG_NAME=gotify-zh
		;;
	*)
		echo "ERROR: LOCALE must be en or zh, got ${LOCALE}" >&2
		exit 1
		;;
esac
PKG_FORMAT="${PKG_FORMAT:-all}"
case "${PKG_FORMAT}" in
	all|ipk|apk) ;;
	*)
		echo "ERROR: PKG_FORMAT must be all, ipk, or apk, got ${PKG_FORMAT}" >&2
		exit 1
		;;
esac
want_ipk=0
want_apk=0
case "${PKG_FORMAT}" in
	all)
		want_ipk=1
		want_apk=1
		;;
	ipk) want_ipk=1 ;;
	apk) want_apk=1 ;;
esac
PKG_RELEASE="${PKG_RELEASE:-1}"
case "${PKG_RELEASE}" in
	''|*[!0-9]*)
		echo "ERROR: PKG_RELEASE must be numeric, got ${PKG_RELEASE}" >&2
		exit 1
		;;
esac

if [ -z "${VERSION:-}" ]; then
	if [ ! -f "${REPO_ROOT}/VERSION" ]; then
		echo "ERROR: ${REPO_ROOT}/VERSION is missing and VERSION is not set" >&2
		exit 1
	fi
	VERSION="$(tr -d ' \t\r\n' <"${REPO_ROOT}/VERSION")"
fi
VERSION="${VERSION#v}"
if [ -z "${VERSION}" ] || [ "${VERSION}" = "unknown" ] || [ "${VERSION}" = "0.0.0" ]; then
	echo "ERROR: refusing VERSION=${VERSION:-<empty>}" >&2
	exit 1
fi
case "${VERSION}" in
	*[!A-Za-z0-9._+~-]*)
		echo "ERROR: invalid VERSION=${VERSION}" >&2
		exit 1
		;;
esac

GOTIFY_SRC="${GOTIFY_SRC:-${REPO_ROOT}/../gotify-server}"
if [ ! -d "${GOTIFY_SRC}" ]; then
	echo "ERROR: GOTIFY_SRC not found: ${GOTIFY_SRC}" >&2
	exit 1
fi
GOTIFY_SRC="$(cd "${GOTIFY_SRC}" && pwd)"

if ! git -C "${GOTIFY_SRC}" rev-parse --verify --quiet "refs/tags/v${VERSION}" >/dev/null; then
	echo "ERROR: tag v${VERSION} not found in ${GOTIFY_SRC}" >&2
	exit 1
fi
COMMIT="$(git -C "${GOTIFY_SRC}" rev-parse "v${VERSION}^{commit}")"
HEAD_COMMIT="$(git -C "${GOTIFY_SRC}" rev-parse HEAD)"
if [ "${HEAD_COMMIT}" != "${COMMIT}" ]; then
	echo "ERROR: ${GOTIFY_SRC} HEAD ${HEAD_COMMIT} is not v${VERSION} (${COMMIT})" >&2
	exit 1
fi

log "version=${VERSION} release=${PKG_RELEASE} commit=${COMMIT} locale=${LOCALE} package=${PKG_NAME} format=${PKG_FORMAT}"
log "source=${GOTIFY_SRC}"

if [ "${want_apk}" = "1" ]; then
	APK_BIN="${APK_BIN:-apk}"
	if ! command -v "${APK_BIN}" >/dev/null 2>&1; then
		echo "ERROR: apk-tools not found (set APK_BIN or install host apk with mkpkg)" >&2
		exit 1
	fi
	export APK_BIN
	# -Dhelp=disabled builds reject --help; probe mkpkg by invoking it bare.
	_apk_mkpkg_out="$("${APK_BIN}" mkpkg 2>&1 || true)"
	if ! printf '%s' "${_apk_mkpkg_out}" | grep -q "required info field"; then
		echo "ERROR: ${APK_BIN} has no mkpkg applet (need host apk-tools with -Dminimal=false)" >&2
		exit 1
	fi
	unset _apk_mkpkg_out
fi

go_ver="$(go env GOVERSION 2>/dev/null || go version)"
case "${go_ver}" in
	*go1.26*) ;;
	*)
		echo "ERROR: need Go 1.26, got ${go_ver}" >&2
		exit 1
		;;
esac

WORK_SRC="$(mktemp -d)"
trap 'rm -rf "${WORK_SRC}"' EXIT
log "Archiving v${VERSION} into ${WORK_SRC}"
git -C "${GOTIFY_SRC}" archive --format=tar "v${VERSION}" | tar -C "${WORK_SRC}" -xf -

mod="$(awk '$1=="module"{print $2; exit}' "${WORK_SRC}/go.mod")"
if [ "${mod}" != "github.com/gotify/server/v3" ]; then
	echo "ERROR: go.mod module is ${mod}, want github.com/gotify/server/v3" >&2
	exit 1
fi

if [ "${LOCALE}" = "zh" ]; then
	log "Applying Chinese UI replacements"
	python3 "${SCRIPT_DIR}/apply-ui-zh.py" "${WORK_SRC}"
fi

# After zh so credit stays English on gotify-zh.
log "Applying OpenWrt packager credit (header)"
python3 "${SCRIPT_DIR}/apply-ui-branding.py" "${WORK_SRC}"

if [ "${SKIP_UI:-0}" = "1" ]; then
	log "Skipping UI build (SKIP_UI=1)"
else
	need_cmd node
	need_cmd yarn
	yarn_ver="$(yarn --version)"
	case "${yarn_ver}" in
		1.*) ;;
		*)
			echo "ERROR: ui/yarn.lock is Yarn 1, got yarn ${yarn_ver}" >&2
			exit 1
			;;
	esac
	log "Building UI (yarn ${yarn_ver}, locale=${LOCALE})"
	(
		cd "${WORK_SRC}/ui"
		export CI=true
		export PUPPETEER_SKIP_DOWNLOAD=1
		export PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=1
		yarn install --frozen-lockfile --network-timeout 600000
		yarn build
	)
fi
if [ ! -f "${WORK_SRC}/ui/build/index.html" ]; then
	echo "ERROR: ui/build/index.html missing" >&2
	exit 1
fi

build_arch() {
	local target="$1"
	local goarch pkg_arch triple expect bin_out musl_cc cxx build_ts ldflags
	local info path_mod main_mod file_out ver_out ipk_dir ipk_path bytes

	case "${target}" in
		x86_64|amd64)
			goarch=amd64
			pkg_arch=x86_64
			triple=x86_64-linux-musl
			expect=x86-64
			bin_out="${REPO_ROOT}/build/linux-amd64-musl/${PKG_NAME}"
			;;
		bcm2710|arm64|aarch64)
			goarch=arm64
			pkg_arch=aarch64_cortex-a53
			triple=aarch64-linux-musl
			expect=aarch64
			bin_out="${REPO_ROOT}/build/linux-arm64-musl/${PKG_NAME}"
			;;
		*)
			echo "ERROR: unknown TARGET=${target} (use x86_64, bcm2710, or all)" >&2
			exit 1
			;;
	esac

	if [ -n "${MUSL_CC:-}" ] && [ "${TARGET}" != "all" ]; then
		musl_cc="${MUSL_CC}"
	elif command -v "${triple}-gcc" >/dev/null 2>&1; then
		musl_cc="${triple}-gcc"
	elif [ "${goarch}" = "amd64" ] && command -v musl-gcc >/dev/null 2>&1; then
		musl_cc=musl-gcc
	else
		echo "ERROR: musl C compiler not found (${triple}-gcc)" >&2
		exit 1
	fi
	cxx="${musl_cc}"
	if command -v "${triple}-g++" >/dev/null 2>&1; then
		cxx="${triple}-g++"
	fi

	mkdir -p "$(dirname "${bin_out}")"
	build_ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
	# -X main.Version is the only version the binary reports. A missing value stays "unknown".
	ldflags="-s -w -linkmode external -extldflags=-static"
	ldflags="${ldflags} -X main.Version=${VERSION}"
	ldflags="${ldflags} -X main.Commit=${COMMIT}"
	ldflags="${ldflags} -X main.BuildDate=${build_ts}"
	ldflags="${ldflags} -X main.Mode=prod"

	log "Building ${pkg_arch} GOARCH=${goarch} CC=${musl_cc}"
	(
		cd "${WORK_SRC}"
		export CGO_ENABLED=1
		export CC="${musl_cc}"
		export CXX="${cxx}"
		export GOOS=linux
		export GOARCH="${goarch}"
		export GOPROXY="${GOPROXY:-https://goproxy.cn,https://proxy.golang.org,direct}"
		export GOSUMDB="${GOSUMDB:-sum.golang.org}"
		export GOTOOLCHAIN="${GOTOOLCHAIN:-local}"
		unset PKG_CONFIG || true
		go build -trimpath -mod=readonly -buildvcs=false -a \
			-ldflags "${ldflags}" \
			-o "${bin_out}" \
			.
	)
	chmod 0755 "${bin_out}"

	bytes="$(wc -c <"${bin_out}" | tr -d ' ')"
	if [ "${bytes}" -lt 5000000 ]; then
		echo "ERROR: ${bin_out} is only ${bytes} bytes; UI embed or link failed" >&2
		exit 1
	fi

	file_out="$(file -b "${bin_out}")"
	log "${file_out}"
	if ! printf '%s\n' "${file_out}" | grep -q "${expect}"; then
		echo "ERROR: binary arch mismatch; expected ${expect}" >&2
		exit 1
	fi
	if printf '%s\n' "${file_out}" | grep -q "dynamically linked"; then
		echo "ERROR: ${bin_out} is dynamically linked" >&2
		exit 1
	fi
	if ! printf '%s\n' "${file_out}" | grep -Eq "statically linked|static-pie"; then
		echo "ERROR: ${bin_out} is not statically linked" >&2
		exit 1
	fi

	info="$(go version -m "${bin_out}")"
	printf '%s\n' "${info}"
	path_mod="$(printf '%s\n' "${info}" | awk '$1=="path"{print $2; exit}')"
	main_mod="$(printf '%s\n' "${info}" | awk '$1=="mod"{print $2; exit}')"
	if [ "${path_mod}" != "github.com/gotify/server/v3" ] || [ "${main_mod}" != "github.com/gotify/server/v3" ]; then
		echo "ERROR: module is path=${path_mod:-<missing>} mod=${main_mod:-<missing>}" >&2
		exit 1
	fi
	if printf '%s\n' "${info}" | grep -q "github.com/gotify/server/v2"; then
		echo "ERROR: v2 module is present in ${bin_out}" >&2
		exit 1
	fi
	# Go 1.26 + -trimpath may omit -X settings from `go version -m`.
	# The string the process reports is what matters for the WebUI and CLI.
	if [ "$(go env GOHOSTARCH)" = "${goarch}" ]; then
		log "Running ${bin_out} version"
		if ! ver_out="$("${bin_out}" version)"; then
			echo "ERROR: ${bin_out} version failed" >&2
			exit 1
		fi
		printf '%s\n' "${ver_out}"
		if ! printf '%s\n' "${ver_out}" | grep -q "^Version: ${VERSION}$"; then
			echo "ERROR: gotify version did not report ${VERSION}" >&2
			exit 1
		fi
		if ! printf '%s\n' "${ver_out}" | grep -q "^Commit: ${COMMIT}$"; then
			echo "ERROR: gotify version did not report Commit: ${COMMIT}" >&2
			exit 1
		fi
	else
		need_cmd strings
		log "Cross-check embedded Version=${VERSION} with strings"
		if ! strings "${bin_out}" | grep -F -x "${VERSION}" >/dev/null; then
			echo "ERROR: binary does not contain Version string ${VERSION}" >&2
			exit 1
		fi
		if ! strings "${bin_out}" | grep -F -x "${COMMIT}" >/dev/null; then
			echo "ERROR: binary does not contain Commit string ${COMMIT}" >&2
			exit 1
		fi
	fi

	if [ ! -f "${WORK_SRC}/LICENSE" ]; then
		echo "ERROR: missing upstream LICENSE at ${WORK_SRC}/LICENSE" >&2
		exit 1
	fi

	if [ "${want_ipk}" = "1" ]; then
		ipk_dir="${REPO_ROOT}/bin/packages/24.10/${pkg_arch}/${PKG_NAME}"
		ipk_path="${ipk_dir}/${PKG_NAME}_${VERSION}-${PKG_RELEASE}_${pkg_arch}.ipk"
		python3 "${SCRIPT_DIR}/pack-ipk.py" \
			--files "${REPO_ROOT}/net/gotify/files" \
			--bin "${bin_out}" \
			--arch "${pkg_arch}" \
			--version "${VERSION}" \
			--release "${PKG_RELEASE}" \
			--package "${PKG_NAME}" \
			--license "${WORK_SRC}/LICENSE" \
			--out "${ipk_path}"
		python3 "${SCRIPT_DIR}/verify-ipk.py" \
			--package "${PKG_NAME}" \
			--version "${VERSION}-${PKG_RELEASE}" \
			"${ipk_path}"
		log "Done ${ipk_path}"
	fi

	if [ "${want_apk}" = "1" ]; then
		apk_dir="${REPO_ROOT}/bin/packages/25.12/${pkg_arch}/${PKG_NAME}"
		apk_path="${apk_dir}/${PKG_NAME}_${VERSION}-r${PKG_RELEASE}_${pkg_arch}.apk"
		bash "${SCRIPT_DIR}/pack-apk.sh" "${PKG_NAME}" \
			--arch "${pkg_arch}" \
			--version "${VERSION}" \
			--release "${PKG_RELEASE}" \
			--bin "${bin_out}" \
			--license "${WORK_SRC}/LICENSE" \
			--out "${apk_path}"
		python3 "${SCRIPT_DIR}/verify-apk.py" \
			--package "${PKG_NAME}" \
			--version "${VERSION}-r${PKG_RELEASE}" \
			--arch "${pkg_arch}" \
			"${apk_path}"
		log "Done ${apk_path}"
	fi
}

pack_luci_app() {
	local ipk_dir ipk_path apk_dir apk_path

	if [ "${want_ipk}" = "1" ]; then
		ipk_dir="${REPO_ROOT}/bin/packages/24.10/all/luci-app-gotify"
		ipk_path="${ipk_dir}/luci-app-gotify_${VERSION}-${PKG_RELEASE}_all.ipk"
		log "Packing luci-app-gotify .ipk (Architecture: all, OpenWrt 24.10)"
		python3 "${SCRIPT_DIR}/pack-luci-ipk.py" \
			--app "${REPO_ROOT}/luci-app-gotify" \
			--version "${VERSION}" \
			--release "${PKG_RELEASE}" \
			--license "${REPO_ROOT}/LICENSE" \
			--out "${ipk_path}"
		python3 "${SCRIPT_DIR}/verify-ipk.py" \
			--package luci-app-gotify \
			--version "${VERSION}-${PKG_RELEASE}" \
			"${ipk_path}"
		log "Done ${ipk_path}"
	fi

	if [ "${want_apk}" = "1" ]; then
		apk_dir="${REPO_ROOT}/bin/packages/25.12/noarch/luci-app-gotify"
		apk_path="${apk_dir}/luci-app-gotify_${VERSION}-r${PKG_RELEASE}_noarch.apk"
		log "Packing luci-app-gotify .apk (arch: noarch, OpenWrt 25.12)"
		bash "${SCRIPT_DIR}/pack-apk.sh" luci-app-gotify \
			--version "${VERSION}" \
			--release "${PKG_RELEASE}" \
			--out "${apk_path}"
		python3 "${SCRIPT_DIR}/verify-apk.py" \
			--package luci-app-gotify \
			--version "${VERSION}-r${PKG_RELEASE}" \
			--arch noarch \
			"${apk_path}"
		log "Done ${apk_path}"
	fi
}

case "${TARGET}" in
	all)
		build_arch x86_64
		build_arch bcm2710
		;;
	*)
		build_arch "${TARGET}"
		;;
esac

pack_luci_app
