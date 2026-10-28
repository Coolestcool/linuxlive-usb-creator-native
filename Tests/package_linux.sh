#!/bin/sh
set -eu
base=/out/package/debian
app="$base/opt/linuxlive-usb-creator"
mkdir -p "$app" "$base/usr/bin" "$base/usr/share/applications" "$base/usr/share/pixmaps" "$base/DEBIAN" /out/releases
cp -a '/out/package/dist/LinuxLive USB Creator/.' "$app/"
cat > "$base/usr/bin/linuxlive-usb-creator" <<'WRAPPER'
#!/bin/sh
exec '/opt/linuxlive-usb-creator/LinuxLive USB Creator' "$@"
WRAPPER
chmod 755 "$base/usr/bin/linuxlive-usb-creator"
cp /src/Resources/img/logo.jpg "$base/usr/share/pixmaps/linuxlive-usb-creator.jpg"
cat > "$base/usr/share/applications/linuxlive-usb-creator.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=LinuxLive USB Creator
Comment=Create a LinuxLive USB with persistence
Exec=linuxlive-usb-creator
Icon=/usr/share/pixmaps/linuxlive-usb-creator.jpg
Terminal=false
Categories=System;Utility;
DESKTOP
cat > "$base/DEBIAN/control" <<'CONTROL'
Package: linuxlive-usb-creator
Version: 1.0.0~preview3
Architecture: amd64
Maintainer: LinuxLive USB Creator native port
Section: utils
Priority: optional
Depends: ca-certificates, libc6 (>= 2.35), libstdc++6, libegl1, libopengl0, libgl1, libxkbcommon0, libxkbcommon-x11-0, libxcb-cursor0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-render-util0, libxcb-xinerama0, libxcb-randr0, libdbus-1-3, libfontconfig1, libfreetype6, libglib2.0-0, libx11-xcb1, pkexec, fdisk, dosfstools, util-linux
Recommends: qemu-system-x86
Description: Native macOS/Linux adaptation of LinuxLive USB Creator 2.9.4
 Original artwork, distribution presets and GPL v3 AutoIt sources are retained.
 This preview includes native FAT32 creation and Linux persistence.
CONTROL
size=$(du -sk "$base/opt" "$base/usr" | awk '{s+=$1} END {print s}')
printf 'Installed-Size: %s\n' "$size" >> "$base/DEBIAN/control"
dpkg-deb --root-owner-group --build "$base" /out/releases/linuxlive-usb-creator_1.0.0-preview3_amd64.deb
tar -C /out/package/dist -czf /out/releases/linuxlive-usb-creator-1.0.0-preview3-linux-x86_64.tar.gz 'LinuxLive USB Creator'
