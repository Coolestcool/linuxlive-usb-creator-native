# SPDX-License-Identifier: GPL-3.0-only
# Native Mac adapters for LiLis_heart.au3, External_Tools.au3 and Disks.au3.
from pathlib import Path
import hashlib
import json
import os
import shutil
import stat
import struct
import sys
import re
import tempfile
import time
from core import ROOT, SUPPORT, run, tool, hashes, recognize, disk_info, validate_disk, exclusive_device
from boot import create_persistence, prepare_boot, install_syslinux

MB = 1024 * 1024


def emit(fraction, message, **values):
    print(json.dumps(dict(event="progress", fraction=max(0, min(1, fraction)), message=message, **values)), flush=True)


def regular_file(path):
    p = Path(path)
    if p.is_symlink() or not p.is_file() or str(p.resolve()).startswith("/dev/"):
        raise ValueError("Choose a regular image file, not a device or symbolic link.")
    return p.resolve()


def archive_entries(path):
    output = run([tool("7z"), "l", "-slt", "--", path]).decode("utf-8", "replace")
    if "----------" not in output: raise ValueError("The image's file list could not be read.")
    entries = []
    for block in output.split("----------", 1)[1].split("\n\n"):
        fields = dict(line.split(" = ", 1) for line in block.splitlines() if " = " in line)
        name = fields.get("Path")
        if name is None: continue
        name = name.replace("\\", "/");relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or any(ord(c) < 32 for c in name) or ":" in name:
            raise ValueError("The archive contains an unsafe path: " + name[:100])
        if fields.get("Symbolic Link") or fields.get("Hard Link") or "l" in fields.get("Attributes", "").split(" ")[-1][:1]:
            raise ValueError("Symbolic links in source archives are not supported.")
        size = int(fields.get("Size", "0") or 0)
        if size < 0 or size > 128 * 1024 ** 3: raise ValueError("Invalid archive entry size")
        entries.append(dict(path=name, size=size, directory=fields.get("Folder") == "+" or fields.get("Attributes", "").startswith("D")))
    if not entries or len(entries) > 500000: raise ValueError("The archive has no usable files or too many entries.")
    return entries


def hybrid_image(path):
    with Path(path).open("rb") as image:header=image.read(512)
    return header[510:512]==b"\x55\xaa" and any(header[450+n*16] and struct.unpack_from("<I",header,458+n*16)[0] for n in range(4))


def inspect_source(path, config, progress=emit):
    p = Path(path).resolve(strict=True)
    if p.is_dir():
        files = [f for f in p.rglob("*") if f.is_file() and not f.is_symlink()]
        return dict(path=str(p), name=p.name, bytes=sum(f.stat().st_size for f in files), mode="folder", hashes={}, release=recognize(p, config=config), files=len(files))
    regular_file(p)
    mode = "img" if p.suffix.lower() in (".img", ".raw", ".bin") and config.get("Advanced", {}).get("force_iso_mode") != "yes" else "iso"
    digest = {} if config.get("Advanced", {}).get("skip_md5") == "yes" else hashes(p, progress)
    release = recognize(p, digest.get("md5"), config)
    if config.get("Advanced", {}).get("skip_recognition") == "yes": release = dict(id="default", name="Default mode", supported_features="")
    if release.get("sha256") and digest.get("sha256"):
        if release["sha256"]!=digest["sha256"]:raise ValueError("This image does not match the official SHA256 checksum. Use a verified download or the correct preset.")
        release["recognition"]="SHA256 verified"
    raw_reason=""
    if release.get("install_method")=="raw" or (release.get("id")=="default" and hybrid_image(p)):
        if not hybrid_image(p):raise ValueError("This ISO does not contain the expected hybrid USB layout.")
        mode="img";raw_reason="Direct image copy · no added persistence"
    entries = [] if mode == "img" else archive_entries(p)
    if entries and any(entry["size"]>=4*1024**3 for entry in entries):
        if not hybrid_image(p):raise ValueError("This ISO exceeds FAT32's file limit and is not a hybrid USB image.")
        mode="img";raw_reason="Direct image copy · no added persistence"
    return dict(path=str(p), name=p.name, bytes=p.stat().st_size, install_bytes=sum(e["size"] for e in entries) or p.stat().st_size, mode=mode, hashes=digest, release=release, files=len(entries), raw_reason=raw_reason)


def copy_tree(source, target):
    source, target = Path(source), Path(target)
    target.mkdir(parents=True, exist_ok=True)
    for path in source.rglob("*"):
        if path.is_symlink(): raise ValueError("Symbolic links are excluded from the USB payload.")
        dest = target / path.relative_to(source)
        if dest.is_symlink() or any(p.is_symlink() for p in dest.parents if p != target.parent):
            raise ValueError("A destination path is a symbolic link.")
        if path.is_dir(): dest.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)


def check_tree(root):
    root = Path(root)
    files = []
    for path in root.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()): raise ValueError("Only regular files and directories can be installed.")
        if path.is_file():
            if path.stat().st_size >= 4 * 1024 ** 3: raise ValueError("A source file exceeds FAT32's 4 GiB file limit: " + path.name)
            files.append(path)
    return files


def prepare(plan, progress=emit):
    job = Path(plan["job"]).resolve()
    if not job.is_dir() or job.is_symlink(): raise ValueError("Invalid job directory")
    source = plan["source"];path = Path(source["path"]).resolve(strict=True)
    if source["mode"] == "img":
        regular_file(path)
        digest = hashes(path)["sha256"]
        if source.get("hashes", {}).get("sha256", digest) != digest: raise ValueError("The source changed after it was selected.")
        source.setdefault("hashes", {})["sha256"] = digest
        plan["prepared"] = True;save_plan(plan);return plan
    staging = job / "payload"
    if staging.exists(): shutil.rmtree(staging)
    staging.mkdir()
    progress(0.02, "Uncompressing or copying source files")
    if source["mode"] == "folder": copy_tree(path, staging)
    else:
        regular_file(path);archive_entries(path)
        if source.get("hashes", {}).get("sha256") and hashes(path)["sha256"] != source["hashes"]["sha256"]: raise ValueError("The selected source changed.")
        run([tool("7z"), "x", "-y", "-o" + str(staging), "--", path])
        # ZIP downloads sometimes contain a single ISO rather than an ISO's files.
        nested = [p for p in staging.iterdir() if p.is_file() and p.suffix.lower() in (".iso", ".img")]
        if len(nested) == 1 and len(list(staging.iterdir())) == 1:
            inner = job / nested[0].name;shutil.move(str(nested[0]), inner);archive_entries(inner)
            run([tool("7z"), "x", "-y", "-o" + str(staging), "--", inner])
    shutil.rmtree(staging / "[BOOT]", ignore_errors=True)
    files = check_tree(staging)
    config = plan.get("settings", {});advanced = config.get("Advanced", {})
    size = int(plan.get("persistence_mb", 0)) if advanced.get("skip_persistence") != "yes" else 0
    persistence = create_persistence(staging, size, source["release"], job, progress)
    if persistence and persistence.get("partition"):plan["persistence_partition"] = str(job / "persistence.fs")
    boot = prepare_boot(staging, source["release"], size > 0, "English" if advanced.get("skip_keyboard_detection") == "yes" else config.get("General", {}).get("force_lang", "English"), advanced.get("skip_boot_text") == "yes", advanced.get("skip_moving_renaming") == "yes")
    if not boot["bios"] and not boot["efi"] and advanced.get("skip_bootsector") != "yes":
        raise ValueError("This source has no recognized BIOS menu or EFI loader. Choose the correct distribution preset.")
    metadata = staging / ".lili";metadata.mkdir(exist_ok=True)
    (metadata / "creation.json").write_text(json.dumps({"release": source["release"], "persistence_mb": size, "boot": boot, "source_sha256": source.get("hashes", {}).get("sha256"), "created": time.time()}, indent=2))
    if plan.get("virtualization") and advanced.get("skip_vbox_setup") != "yes":
        launcher = staging / "LinuxLive on Mac.command"
        launcher.write_text('#!/bin/sh\nexec /usr/bin/open -a "LinuxLive USB Creator" --args --launch-volume "$(dirname "$0")"\n')
        launcher.chmod(0o755)
        linux_launcher = staging / "LinuxLive on Linux.sh"
        linux_launcher.write_text('#!/bin/sh\nexec linuxlive-usb-creator --launch-volume "$(dirname "$0")"\n')
        linux_launcher.chmod(0o755)
    installed = metadata / "installed-files.json";installed.write_text("[]")
    installed.write_text(json.dumps([p.relative_to(staging).as_posix() for p in check_tree(staging)], indent=2))
    plan.update(prepared=True, payload=str(staging), payload_bytes=sum(p.stat().st_size for p in check_tree(staging)), boot=boot)
    save_plan(plan);progress(1, "Source prepared")
    return plan


def save_plan(plan):
    path = Path(plan["job"]) / "plan.json"
    path.write_text(json.dumps(plan, indent=2));path.chmod(0o600)


def write_mbr(path, sectors, bootcode, persistence_sectors=0):
    if sectors < 65536 or sectors > 0xffffffff: raise ValueError("The FAT32 layout supports disks from 32 MiB to 2 TiB.")
    mbr = bytearray(512);code = Path(bootcode).read_bytes()
    if len(code) > 440: raise ValueError("Invalid MBR boot code length")
    mbr[:len(code)] = code
    fat_sectors = sectors - 2048 - persistence_sectors
    if fat_sectors < 65536:raise ValueError("Not enough space for FAT32 plus the requested persistence partition.")
    mbr[446:462] = struct.pack("<B3sB3sII", 0x80, b"\xfe\xff\xff", 0x0c, b"\xfe\xff\xff", 2048, fat_sectors)
    if persistence_sectors:
        mbr[462:478] = struct.pack("<B3sB3sII", 0, b"\xfe\xff\xff", 0x83, b"\xfe\xff\xff", sectors - persistence_sectors, persistence_sectors)
    mbr[510:512] = b"\x55\xaa"
    with Path(path).open("r+b") as out: out.write(mbr)


def make_image(plan, progress=emit):
    if not plan.get("prepared"): plan = prepare(plan, progress)
    output = Path(plan["output"])
    if not output.is_absolute() or str(output).startswith("/dev/") or output.is_symlink() or output.exists(): raise ValueError("Choose a new image file; existing files and devices are excluded.")
    if plan["source"]["mode"] == "img":
        shutil.copyfile(regular_file(plan["source"]["path"]), output);return {"path": str(output), "sha256": hashes(output)["sha256"]}
    size_mb = max(128, int(plan.get("image_size_mb", (plan["payload_bytes"] // MB) * 1.15 + 128 + (plan.get("persistence_mb", 0) if plan.get("persistence_partition") else 0))))
    sectors = size_mb * 2048
    with output.open("xb") as out: out.truncate(size_mb * MB)
    persistence_bytes = Path(plan["persistence_partition"]).stat().st_size if plan.get("persistence_partition") else 0
    write_mbr(output, sectors, ROOT / "NativeTools/mbr.bin", persistence_bytes // 512)
    volume = str(output) + "@@1048576"
    run([tool("mformat"), "-i", volume, "-F", "-v", "LILILIVE", "-H", "2048", "-T", str(sectors - 2048 - persistence_bytes // 512), "::"])
    advanced = plan.get("settings", {}).get("Advanced", {})
    children = sorted(Path(plan["payload"]).iterdir()) if advanced.get("skip_copy") != "yes" else []
    for n, path in enumerate(children):
        run([tool("mcopy"), "-i", volume, "-s", "-o", path, "::/"])
        progress((n + 1) / max(1, len(children)), "Copying " + path.name)
    if plan.get("settings", {}).get("Advanced", {}).get("skip_bootsector") != "yes": install_syslinux(output, plan["boot"], 1048576)
    if plan.get("hide_files") and advanced.get("skip_hiding") != "yes":
        for path in children:
            if path.name != "LinuxLive on Mac.command": run([tool("mattrib"), "-i", volume, "+h", "+s", "::/" + path.name])
    if persistence_bytes:copy_at(plan["persistence_partition"], output, sectors * 512 - persistence_bytes)
    return {"path": str(output), "bytes": output.stat().st_size, "sha256": hashes(output)["sha256"], "persistence_mb": plan.get("persistence_mb", 0), "boot": plan["boot"]}


def copy_at(source, target, offset):
    with open(source, "rb", buffering=0) as incoming, open(target, "r+b", buffering=0) as output:
        output.seek(offset)
        for block in iter(lambda: incoming.read(4 * MB), b""):
            view = memoryview(block)
            while view:
                count = output.write(view)
                if not count:raise ValueError("Persistence write stopped unexpectedly")
                view = view[count:]
        os.fsync(output.fileno())
    verify_bytes(source, target, Path(source).stat().st_size, lambda *_:None, offset)


def verify_bytes(source, target, count, progress=emit, offset=0):
    left, right = hashlib.sha256(), hashlib.sha256();done = 0
    with open(source, "rb", buffering=0) as a, open(target, "rb", buffering=0) as b:
        b.seek(offset)
        while done < count:
            block = a.read(min(4 * MB, count - done));copied = b.read(len(block))
            if not block or copied != block: raise ValueError("Verification failed at byte " + str(done))
            left.update(block);right.update(copied);done += len(block)
            progress(done / max(count, 1), "Verifying written data")
    return left.hexdigest()


def smart_clean(volume):
    root = Path(volume).resolve()
    manifest = root / ".lili/installed-files.json"
    if not manifest.exists(): return
    paths = json.loads(manifest.read_text())
    for name in paths:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts: raise ValueError("Invalid previous installation manifest")
        p = root / relative
        if any(parent.is_symlink() for parent in [p, *p.parents] if parent != root.parent): raise ValueError("Symbolic link in previous installation")
        if p.is_file(): p.unlink()


def unmount(identifier, info):
    if sys.platform == "darwin":
        run(["/usr/sbin/diskutil", "unmountDisk", identifier])
    else:
        from linux_disks import inventory, flattened
        for disk in inventory():
            if disk["name"] == identifier:
                for part in reversed(list(flattened(disk.get("children", [])))):
                    if part.get("mountpoint"): run(["/usr/bin/umount", "--", part["path"]])


def partition(identifier):
    if sys.platform == "darwin":
        listing = __import__("plistlib").loads(run(["/usr/sbin/diskutil", "list", "-plist", identifier]))
        parts = listing["AllDisksAndPartitions"][0].get("Partitions", [])
        return next((disk_info(p["DeviceIdentifier"]) for p in parts if disk_info(p["DeviceIdentifier"]).get("FilesystemType") == "msdos"), None)
    from linux_disks import inventory, flattened, normalized
    for disk in inventory():
        if disk["name"] == identifier:
            return next((normalized(p, disk) for p in flattened(disk.get("children", [])) if p.get("fstype") in ("vfat", "fat", "fat32")), None)


def clean_fat(volume):
    try: old = json.loads(run([tool("mtype"), "-i", volume, "::/.lili/installed-files.json"]))
    except ValueError: return
    if not isinstance(old, list) or len(old) > 500000: raise ValueError("Invalid previous installation manifest")
    for name in old:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or not name or any(ord(c) < 32 for c in name): raise ValueError("Invalid previous installation path")
        try: run([tool("mdel"), "-i", volume, "::/" + name])
        except ValueError: pass


def verify_fat(source, volume, relative):
    process = __import__("subprocess").Popen([tool("mtype"), "-i", volume, "::/" + relative], stdout=__import__("subprocess").PIPE, stderr=__import__("subprocess").DEVNULL, env=dict(os.environ, MTOOLS_SKIP_CHECK="1"))
    valid = True
    with Path(source).open("rb") as src:
        while True:
            a, b = src.read(4 * MB), process.stdout.read(4 * MB)
            if a != b: valid = False
            if not a and not b: break
    process.stdout.close()
    code = process.wait()
    if code or not valid: raise ValueError("Verification failed for " + relative)


@exclusive_device
def install(plan, progress=emit):
    if os.geteuid() != 0: raise ValueError("Administrator authorization is required to write the USB.")
    if not plan.get("prepared"): raise ValueError("Prepare the source before authorizing a disk write.")
    identifier = plan["disk"]["id"]
    info = disk_info(identifier);validate_disk(info, plan["disk"]["identity"])
    source = plan["source"]
    device = ("/dev/r" if sys.platform == "darwin" else "/dev/") + identifier
    if plan.get("persistence_partition") and not plan.get("format"):
        raise ValueError("Modern Debian persistence needs a separate Linux partition. Enable FAT32 format for this installation.")
    unmount(identifier, info)
    validate_disk(disk_info(identifier), plan["disk"]["identity"])
    if source["mode"] == "img":
        image = regular_file(source["path"]);count = image.stat().st_size
        if hashes(image)["sha256"] != source.get("hashes", {}).get("sha256"):
            raise ValueError("The source image changed after preparation. Select it again.")
        if count % 512: raise ValueError("A raw image must contain complete 512-byte sectors.")
        if count > info["TotalSize"]: raise ValueError("The source image is larger than the USB disk.")
        with image.open("rb", buffering=0) as incoming, open(device, "r+b", buffering=0) as out:
            done = 0
            while True:
                block = incoming.read(4 * MB)
                if not block: break
                view = memoryview(block)
                while view:
                    n = out.write(view)
                    if not n: raise ValueError("USB write stopped unexpectedly")
                    view = view[n:]
                done += len(block);progress(done / count, "Writing image to USB")
            os.fsync(out.fileno())
        digest = verify_bytes(image, device, count, progress)
        if sys.platform == "darwin": run(["/usr/sbin/diskutil", "eject", identifier])
        return {"status": "verified", "sha256": digest}
    advanced = plan.get("settings", {}).get("Advanced", {})
    separate = plan.get("persistence_partition")
    if separate:
        sectors = info["TotalSize"] // 512
        persistence_bytes = Path(separate).stat().st_size
        write_mbr(device, sectors, ROOT / "NativeTools/mbr.bin", persistence_bytes // 512)
        target = device + "@@1048576"
        run([tool("mformat"), "-i", target, "-F", "-v", "LILILIVE", "-H", "2048", "-T", str(sectors - 2048 - persistence_bytes // 512), "::"])
        copy_at(separate, device, sectors * 512 - persistence_bytes)
    elif plan.get("format"):
        progress(0, "Formatting FAT32")
        if sys.platform == "darwin":
            run(["/usr/sbin/diskutil", "eraseDisk", "MS-DOS", "LILILIVE", "MBRFormat", identifier]);unmount(identifier, info)
        else:
            run(["/usr/sbin/sfdisk", "--wipe", "always", "/dev/" + identifier], input=b"label: dos\nunit: sectors\n\nstart=2048, type=c, bootable\n")
            first = identifier + ("p1" if identifier[-1].isdigit() else "1")
            for _ in range(30):
                if Path("/dev/" + first).exists(): break
                time.sleep(0.1)
            run(["/usr/sbin/mkfs.vfat", "-F", "32", "-n", "LILILIVE", "/dev/" + first])
        validate_disk(disk_info(identifier), plan["disk"]["identity"])
    volume = None if separate else partition(identifier)
    if not separate and not volume: raise ValueError("The USB needs a FAT/FAT32 volume. Enable the FAT32 format option.")
    # The BIOS MBR adapter must not replace a protective GPT MBR.
    with open(device, "rb", buffering=0) as check: mbr = check.read(512)
    if any(mbr[446 + n * 16 + 4] == 0xee for n in range(4)) and plan["boot"]["bios"] and advanced.get("skip_bootsector") != "yes":
        raise ValueError("For BIOS + EFI creation on a GPT device, enable FAT32 format to use the original MBR layout.")
    target = device + "@@1048576" if separate else "/dev/" + volume["DeviceIdentifier"]
    if not separate and plan.get("format") and advanced.get("force_3rdparty_format") == "yes":
        run([tool("mformat"), "-i", target, "-F", "-v", "LILILIVE", "::"])
    if advanced.get("skip_cleaning") != "yes": clean_fat(target)
    if advanced.get("skip_copy") != "yes":
        files = check_tree(plan["payload"])
        listing = run([tool("mdir"), "-i", target, "::/"]).decode("utf-8", "replace")
        free = re.search(r"([0-9 ,]+) bytes free", listing)
        if free and int(re.sub(r"[^0-9]", "", free[1])) < sum(p.stat().st_size for p in files): raise ValueError("Not enough free space on the selected USB.")
        for n, path in enumerate(sorted(Path(plan["payload"]).iterdir())):
            run([tool("mcopy"), "-i", target, "-s", "-o", path, "::/"]);progress(n / max(1, len(files)), "Copying " + path.name)
        for n, path in enumerate(files):
            relative = path.relative_to(plan["payload"]).as_posix();verify_fat(path, target, relative);progress((n + 1) / max(1, len(files)), "Verifying " + relative)
    if plan.get("hide_files") and advanced.get("skip_hiding") != "yes":
        for path in Path(plan["payload"]).iterdir():
            if path.suffix != ".command": run([tool("mattrib"), "-i", target, "+h", "+s", "::/" + path.name])
    if advanced.get("skip_bootsector") != "yes" and plan["boot"]["bios"]:
        validate_disk(disk_info(identifier), plan["disk"]["identity"])
        install_syslinux(device if separate else target, plan["boot"], 1048576 if separate else 0)
        code = (ROOT / "NativeTools/mbr.bin").read_bytes()
        if len(code) > 440: raise ValueError("Invalid MBR code")
        with open(device, "r+b", buffering=0) as out:
            sector = bytearray(out.read(512))
            if len(sector) != 512:raise ValueError("Could not read the complete MBR sector")
            sector[:len(code)] = code;out.seek(0);out.write(sector);os.fsync(out.fileno())
    progress(1, "Your LinuxLive key is ready")
    return {"status": "verified", "disk": identifier, "persistence_mb": plan.get("persistence_mb", 0), "boot": plan["boot"]}
