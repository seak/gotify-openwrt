#!/usr/bin/env bash
# Install a Docker-free WSL toolchain matching scripts/Dockerfile.
# Tools go under $HOME/.local (no sudo required for Go/Node/musl cross).
# Optional: sudo apt install musl-tools (provides musl-gcc); not required if
# x86_64-linux-musl-gcc is on PATH.
set -euo pipefail

export LC_ALL=C

GO_VERSION="${GO_VERSION:-1.26.0}"
NODE_VERSION="${NODE_VERSION:-24.22.3}"
YARN_VERSION="${YARN_VERSION:-1.22.22}"
PREFIX="${PREFIX:-${HOME}/.local}"
OPT_ROOT="${OPT_ROOT:-${HOME}/.local/opt}"
INSTALL_AARCH64="${INSTALL_AARCH64:-1}"

log() { printf '+ %s\n' "$*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

need_host_cmd() {
	command -v "$1" >/dev/null 2>&1 || die "required host command not found: $1"
}

need_host_cmd curl
need_host_cmd tar
need_host_cmd xz
need_host_cmd git
need_host_cmd python3
need_host_cmd file
need_host_cmd gcc
# build-ipk.sh uses `strings` when cross-checking embedded Version/Commit.
need_host_cmd strings

mkdir -p "${PREFIX}/bin" "${OPT_ROOT}"
export PATH="${PREFIX}/bin:${OPT_ROOT}/x86_64-linux-musl-cross/bin:${OPT_ROOT}/aarch64-linux-musl-cross/bin:${PATH}"

fetch() {
	local url="$1" out="$2"
	log "Fetching ${url}"
	# -C - resumes partial downloads (musl.cc / GitHub can be very slow).
	curl -fL -C - --retry 10 --retry-delay 5 --connect-timeout 30 \
		-o "${out}" "${url}"
}

install_go() {
	local tgz="/tmp/go${GO_VERSION}.linux-amd64.tar.gz"
	local dest="${OPT_ROOT}/go"
	if [ -x "${dest}/bin/go" ] && "${dest}/bin/go" version 2>/dev/null | grep -q "go${GO_VERSION}"; then
		log "Go ${GO_VERSION} already installed at ${dest}"
	else
		fetch "https://mirrors.aliyun.com/golang/go${GO_VERSION}.linux-amd64.tar.gz" "${tgz}" \
			|| fetch "https://cdn.npmmirror.com/binaries/go/go${GO_VERSION}.linux-amd64.tar.gz" "${tgz}" \
			|| fetch "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" "${tgz}"
		rm -rf "${dest}"
		mkdir -p "${OPT_ROOT}"
		tar -C "${OPT_ROOT}" -xzf "${tgz}"
		# tarball extracts as "go/"; rename for clarity if needed — keep as go/
		rm -f "${tgz}"
		"${dest}/bin/go" version | grep -q "go${GO_VERSION}" || die "Go install failed"
		log "Installed Go ${GO_VERSION}"
	fi
	ln -sfn "${dest}/bin/go" "${PREFIX}/bin/go"
	ln -sfn "${dest}/bin/gofmt" "${PREFIX}/bin/gofmt"
}

install_node_yarn() {
	local txz="/tmp/node-v${NODE_VERSION}-linux-x64.tar.xz"
	local dest="${OPT_ROOT}/node-v${NODE_VERSION}-linux-x64"
	if [ -x "${dest}/bin/node" ] && "${dest}/bin/node" -v 2>/dev/null | grep -q "v${NODE_VERSION}"; then
		log "Node ${NODE_VERSION} already installed at ${dest}"
	else
		fetch "https://npmmirror.com/mirrors/node/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" "${txz}" \
			|| fetch "https://mirrors.aliyun.com/nodejs-release/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" "${txz}" \
			|| fetch "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" "${txz}"
		rm -rf "${dest}"
		tar -C "${OPT_ROOT}" -xJf "${txz}"
		rm -f "${txz}"
		"${dest}/bin/node" -v | grep -q "v${NODE_VERSION}" || die "Node install failed"
		log "Installed Node ${NODE_VERSION}"
	fi
	ln -sfn "${dest}/bin/node" "${PREFIX}/bin/node"
	ln -sfn "${dest}/bin/npm" "${PREFIX}/bin/npm"
	ln -sfn "${dest}/bin/npx" "${PREFIX}/bin/npx"
	# yarn 1 via npm (user prefix)
	export npm_config_prefix="${PREFIX}"
	if command -v yarn >/dev/null 2>&1 && yarn --version 2>/dev/null | grep -q '^1\.'; then
		log "Yarn $(yarn --version) already present"
	else
		log "Installing yarn@${YARN_VERSION}"
		npm install -g "yarn@${YARN_VERSION}"
	fi
	yarn --version | grep -q '^1\.' || die "need Yarn 1.x"
}

install_musl_cross() {
	local name="$1"
	# Prefer GH CDN mirrors; musl.cc is a single host and often stalls.
	local url_mirror="https://github.com/libviprs/libviprs-dep/releases/download/musl-cross-mirror/${name}.tgz"
	local url_gh="https://github.com/musl-cc/musl.cc/releases/download/v0.0.1/${name}.tgz"
	local url_musl="https://musl.cc/${name}.tgz"
	local tgz="/tmp/${name}.tgz"
	local dest="${OPT_ROOT}/${name}"
	local gcc_bin="${dest}/bin/${name%-cross}-gcc"

	if [ -x "${gcc_bin}" ]; then
		log "${name} already installed"
		return 0
	fi
	rm -f "${tgz}"
	fetch "${url_mirror}" "${tgz}" || fetch "${url_gh}" "${tgz}" || fetch "${url_musl}" "${tgz}"
	tar -C "${OPT_ROOT}" -xzf "${tgz}"
	rm -f "${tgz}"
	[ -x "${gcc_bin}" ] || die "${gcc_bin} missing after extract"
	log "Installed ${name}"
}

write_env_snippet() {
	local snippet="${PREFIX}/gotify-openwrt-env.sh"
	cat >"${snippet}" <<EOF
# gotify-openwrt WSL toolchain (no Docker)
export PATH="${PREFIX}/bin:${OPT_ROOT}/go/bin:${OPT_ROOT}/x86_64-linux-musl-cross/bin:${OPT_ROOT}/aarch64-linux-musl-cross/bin:\${PATH}"
export GOPROXY="\${GOPROXY:-https://goproxy.cn,https://proxy.golang.org,direct}"
export GOSUMDB="\${GOSUMDB:-sum.golang.org}"
export GOTOOLCHAIN="\${GOTOOLCHAIN:-local}"
EOF
	log "Wrote ${snippet}"
	local bashrc="${HOME}/.bashrc"
	local marker="# gotify-openwrt-toolchain"
	if [ -f "${bashrc}" ] && grep -qF "${marker}" "${bashrc}"; then
		log "~/.bashrc already sources toolchain env"
	else
		{
			echo ""
			echo "${marker}"
			echo "[ -f \"${snippet}\" ] && . \"${snippet}\""
		} >>"${bashrc}"
		log "Appended source line to ~/.bashrc"
	fi
}

verify() {
	log "=== verification ==="
	command -v go
	go version | grep -q 'go1.26' || die "need Go 1.26, got $(go version)"
	command -v node
	node -v
	command -v yarn
	yarn --version | grep -q '^1\.' || die "need Yarn 1.x"
	command -v x86_64-linux-musl-gcc
	x86_64-linux-musl-gcc --version | head -1
	if [ "${INSTALL_AARCH64}" = "1" ]; then
		command -v aarch64-linux-musl-gcc
		aarch64-linux-musl-gcc --version | head -1
	fi
	command -v python3
	command -v file
	command -v git
	if command -v musl-gcc >/dev/null 2>&1; then
		musl-gcc --version | head -1
	else
		log "musl-gcc not installed (optional; x86_64-linux-musl-gcc is enough)"
	fi
	log "OK — toolchain ready"
	log "New shells: source ~/.bashrc   or: . ${PREFIX}/gotify-openwrt-env.sh"
}

log "PREFIX=${PREFIX}"
log "OPT_ROOT=${OPT_ROOT}"
install_go
install_node_yarn
install_musl_cross x86_64-linux-musl-cross
if [ "${INSTALL_AARCH64}" = "1" ]; then
	install_musl_cross aarch64-linux-musl-cross
fi
write_env_snippet
# ensure current shell PATH for verify
# shellcheck disable=SC1090
. "${PREFIX}/gotify-openwrt-env.sh"
verify
