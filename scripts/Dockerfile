# One image builds both OpenWrt 24.10 packages:
#   x86_64 and aarch64_cortex-a53 (Raspberry Pi 3 / bcm2710)
# Go is pinned to 1.26.0, matching gotify-server v3.1.1's toolchain line.
# musl-tools provides musl-gcc; musl.cc provides the x86_64 and aarch64 cross compilers.
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    GO_VERSION=1.26.0 \
    NODE_VERSION=24.22.3 \
    PATH=/usr/local/go/bin:/opt/x86_64-linux-musl-cross/bin:/opt/aarch64-linux-musl-cross/bin:/usr/local/bin:${PATH} \
    GOPROXY=https://goproxy.cn,https://proxy.golang.org,direct \
    GOSUMDB=sum.golang.org \
    GOTOOLCHAIN=local

RUN apt-get update && apt-get install -y --no-install-recommends \
        bash \
        binutils \
        ca-certificates \
        curl \
        file \
        gcc \
        git \
        musl-tools \
        python3 \
        tar \
        xz-utils \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fL --retry 5 --retry-delay 2 -o /tmp/go.tgz "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" \
        || curl -fL --retry 5 --retry-delay 2 -o /tmp/go.tgz "https://mirrors.aliyun.com/golang/go${GO_VERSION}.linux-amd64.tar.gz" \
        || curl -fL --retry 5 --retry-delay 2 -o /tmp/go.tgz "https://mirrors.ustc.edu.cn/golang/go${GO_VERSION}.linux-amd64.tar.gz" \
        || curl -fL --retry 5 --retry-delay 2 -o /tmp/go.tgz "https://cdn.npmmirror.com/binaries/go/go${GO_VERSION}.linux-amd64.tar.gz" \
    && rm -rf /usr/local/go \
    && tar -C /usr/local -xzf /tmp/go.tgz \
    && rm /tmp/go.tgz \
    && go version | grep -q "go${GO_VERSION} "

RUN curl -fL --retry 5 --retry-delay 2 -o /tmp/node.tar.xz "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
        || curl -fL --retry 5 --retry-delay 2 -o /tmp/node.tar.xz "https://mirrors.aliyun.com/nodejs-release/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
        || curl -fL --retry 5 --retry-delay 2 -o /tmp/node.tar.xz "https://npmmirror.com/mirrors/node/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
    && tar -C /usr/local --strip-components=1 -xJf /tmp/node.tar.xz \
    && rm /tmp/node.tar.xz \
    && npm install -g yarn@1.22.22 \
    && node -v && yarn --version | grep -q '^1\.'

# musl.cc is a single host and often stalls. The GitHub release is the same tarball.
RUN set -eux; \
    fetch() { \
      curl -fL --retry 2 --retry-delay 2 --connect-timeout 20 \
        --speed-limit 10000 --speed-time 30 -o "$2" "$1"; \
    }; \
    fetch "https://github.com/musl-cc/musl.cc/releases/download/v0.0.1/x86_64-linux-musl-cross.tgz" /tmp/x86_64-musl.tgz \
      || fetch "https://github.com/libviprs/libviprs-dep/releases/download/musl-cross-mirror/x86_64-linux-musl-cross.tgz" /tmp/x86_64-musl.tgz \
      || fetch "https://musl.cc/x86_64-linux-musl-cross.tgz" /tmp/x86_64-musl.tgz; \
    tar -C /opt -xzf /tmp/x86_64-musl.tgz; \
    rm /tmp/x86_64-musl.tgz; \
    fetch "https://github.com/musl-cc/musl.cc/releases/download/v0.0.1/aarch64-linux-musl-cross.tgz" /tmp/aarch64-musl.tgz \
      || fetch "https://github.com/libviprs/libviprs-dep/releases/download/musl-cross-mirror/aarch64-linux-musl-cross.tgz" /tmp/aarch64-musl.tgz \
      || fetch "https://musl.cc/aarch64-linux-musl-cross.tgz" /tmp/aarch64-musl.tgz; \
    tar -C /opt -xzf /tmp/aarch64-musl.tgz; \
    rm /tmp/aarch64-musl.tgz; \
    x86_64-linux-musl-gcc --version; \
    aarch64-linux-musl-gcc --version; \
    musl-gcc --version

# Strip CR from the mounted build script and run it. The packaging repo is
# mounted at /src and the gotify-server checkout at /gotify-server.
RUN printf '%s\n' \
    '#!/bin/bash' \
    'set -euo pipefail' \
    'tr -d "\r" < /src/scripts/build-ipk.sh > /tmp/build-ipk.sh' \
    'chmod 0755 /tmp/build-ipk.sh' \
    'export GOTIFY_OPENWRT_ROOT=/src' \
    'exec /bin/bash /tmp/build-ipk.sh "$@"' \
    > /usr/local/bin/gotify-openwrt-entrypoint.sh \
    && chmod 0755 /usr/local/bin/gotify-openwrt-entrypoint.sh

WORKDIR /src
ENTRYPOINT ["/usr/local/bin/gotify-openwrt-entrypoint.sh"]
