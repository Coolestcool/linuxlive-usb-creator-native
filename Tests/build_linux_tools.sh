#!/bin/sh
set -eu
mkdir -p /tmp/lili-native-build /out/linux-native/bin /out/linux-native/lib /out/linux-native/libexec
for archive in /src/NativeSources/mtools-*.tar.* /src/NativeSources/syslinux-*.tar.*; do tar -xf "$archive" -C /tmp/lili-native-build; done
cd /tmp/lili-native-build/mtools-4.0.49
./configure --prefix=/out/linux-native --disable-xdf --without-x
make -j2
make install
CC=cc LILI_NATIVE_BUILD=/tmp/lili-native-build LILI_NATIVE_OUTPUT=/out/linux-native/bin python3 /src/build_native.py
cp /usr/lib/p7zip/7z /usr/lib/p7zip/7z.so /out/linux-native/bin/
cp /usr/sbin/mke2fs /out/linux-native/libexec/
ldd /usr/sbin/mke2fs | awk '/=> \/.*lib(ext2fs|com_err|e2p|blkid|uuid|ss)\./ { print $3 }' | while read -r library; do cp -L "$library" /out/linux-native/lib/; done
cat > /out/linux-native/bin/mke2fs <<'WRAPPER'
#!/bin/sh
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
LD_LIBRARY_PATH="$root/lib" exec "$root/libexec/mke2fs" "$@"
WRAPPER
chmod +x /out/linux-native/bin/mke2fs
cp /tmp/lili-native-build/syslinux-6.03/bios/mbr/mbr.bin /out/linux-native/mbr.bin
python3 -m pip freeze > /out/requirements-linux-lock.txt
echo 'Linux native tools ready'
