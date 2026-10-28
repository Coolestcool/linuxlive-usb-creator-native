FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 libpython3.10 python3-venv python3-pip build-essential ca-certificates \
    mtools dosfstools e2fsprogs p7zip-full util-linux fdisk \
    qemu-system-x86 busybox-static xvfb xauth xz-utils \
    libegl1 libopengl0 libgl1 libxkbcommon0 libxkbcommon-x11-0 \
    libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
    libxcb-render-util0 libxcb-xinerama0 libxcb-randr0 libdbus-1-3 \
    libfontconfig1 libfreetype6 libglib2.0-0 libnss3 libx11-xcb1 \
    fonts-liberation && rm -rf /var/lib/apt/lists/*
RUN python3 -m pip install --no-cache-dir PySide6-Essentials==6.8.3 pyinstaller==6.22.3
ENV QT_QPA_PLATFORM=offscreen
WORKDIR /src
