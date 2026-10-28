#!/bin/sh
# File-only QEMU fixture. No physical device is exposed to this container.
set -eu
fixture=/out/boot-fixture
mkdir -p "$fixture/casper" /tmp/lili-init
cd /tmp/lili-init
gzip -dc /boot-test/initramfs.gz | busybox cpio -idmu >/dev/null 2>&1
7z x -y -o/tmp/lili-modules /boot-test/modloop-virt >/dev/null
cp -a /tmp/lili-modules/modules/. lib/modules/
rm -f bin/busybox
cp /bin/busybox bin/busybox
cat > init <<'INIT'
#!/bin/busybox sh
/bin/busybox mount -t devtmpfs devtmpfs /dev
exec >/dev/ttyS0 2>&1
/bin/busybox --install -s /bin
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
fail() { echo "LILI_BOOT_FAIL: $*"; sync; poweroff -f; }
modprobe virtio_blk || fail virtio
modprobe loop || fail loop
modprobe vfat || fail vfat
modprobe ext4 || fail ext4
sleep 2
mkdir -p /usb /persist
mount -t vfat /dev/vda1 /usb || fail fat
case " $(cat /proc/cmdline) " in *' persistent '*) ;; *) fail parameter ;; esac
mount -t ext4 -o loop /usb/casper-rw /persist || fail persistence
if test -f /persist/lili-reboot-proof; then
    test "$(cat /persist/lili-reboot-proof)" = 'written by first boot' || fail content
    echo LILI_SECOND_BOOT_PERSISTENCE_PASS
else
    echo 'written by first boot' > /persist/lili-reboot-proof
    echo LILI_FIRST_BOOT_WRITE_PASS
fi
sync
umount /persist
umount /usb
poweroff -f
INIT
chmod 755 init
find . -print | busybox cpio -o -H newc 2>/dev/null | gzip -1 > "$fixture/casper/initrd"
cp /boot-test/vmlinuz "$fixture/casper/vmlinuz"
