# Build container producing a 32-bit Windows DLL for BWAPI 4.4.0.
# MSVC runs under Wine: BWAPI exposes MSVC-mangled C++ classes with virtual
# methods, so MinGW/gcc would produce an ABI-incompatible binary.

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Wine from WineHQ: the Ubuntu 22.04 package (6.0) is too old for recent MSVC.
RUN dpkg --add-architecture i386 && apt-get update && apt-get install -y --no-install-recommends \
        wget gnupg ca-certificates \
    && mkdir -pm755 /etc/apt/keyrings \
    && wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key \
    && wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/jammy/winehq-jammy.sources \
    && apt-get update \
    && apt-get install -y --install-recommends winehq-stable \
    && apt-get install -y --no-install-recommends \
        python3 python3-pip msitools git curl p7zip-full make \
    && rm -rf /var/lib/apt/lists/*

ENV WINEPREFIX=/root/.wine
ENV WINEDEBUG=-all

# Initialise the prefix once, explicitly, rather than letting install.sh do it.
RUN wineboot --init && wineserver -w

# BWAPI first: it is small and fails fast, unlike the multi-GB MSVC download.
# The release ships headers and BWAPILIB *sources* -- there is no import library.
ARG BWAPI_URL=https://github.com/bwapi/bwapi/releases/download/v4.4.0/BWAPI.7z
RUN mkdir -p /opt/bwapi && cd /opt/bwapi \
    && curl -fsSL -o bwapi.7z "${BWAPI_URL}" \
    && 7z x -y bwapi.7z > /dev/null \
    && rm bwapi.7z \
    && test -f Release_Binary/include/BWAPI.h

ENV BWAPI_ROOT=/opt/bwapi/Release_Binary

# msvc-wine fetches the official MSVC build tools and wraps cl.exe / link.exe.
RUN git clone --depth 1 https://github.com/mstorsjo/msvc-wine.git /opt/msvc-wine \
    && cd /opt/msvc-wine \
    && python3 vsdownload.py --accept-license --dest /opt/msvc \
    && ./install.sh /opt/msvc \
    && rm -rf /opt/msvc-wine

ENV WINEPREFIX=/root/.wine
ENV WINEDEBUG=-all
# x86 wrappers: BWAPI and StarCraft 1.16.1 are both 32-bit.
ENV PATH="/opt/msvc/bin/x86:${PATH}"

WORKDIR /src
CMD ["make"]
