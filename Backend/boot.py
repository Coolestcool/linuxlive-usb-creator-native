# SPDX-License-Identifier: GPL-3.0-only
# Ported from LiLis_heart.au3 / Boot_Menus.au3 / Files.au3, LinuxLive USB Creator.
from pathlib import Path
import os
import re
import shutil
from core import ROOT, run, tool


def supported_features(release):
    return [s.strip() for s in release.get("supported_features", "").split(",") if s.strip()]


def persistence_spec(release):
    features = supported_features(release)
    for feature in features:
        if feature.startswith("custom-persistence:"):
            return {"file": feature.split(":", 1)[1], "label": "casper-rw", "parameter": "persistent", "config": False}
    if "debian-persistence" in features:
        version = re.search(r"\d+", release.get("distribution_version", ""))
        modern = version is None or int(version.group()) >= 7
        return {"file": "persistence" if modern else "live-rw", "label": "persistence" if modern else "live-rw", "parameter": "persistence" if modern else "persistent", "config": modern, "partition": modern}
    if "sidux-persistence" in features or "aptosid-persistence" in features:
        name = "sidux" if "sidux-persistence" in features else "aptosid"
        return {"file": name + "/" + name + "-rw", "label": "casper-rw", "parameter": "persistent", "config": False}
    if "fedora-persistence" in features or "mandriva-persistence" in features:
        return {"file": "LiveOS/overlay-LILILIVE", "label": "overlay", "parameter": "rd.live.overlay", "config": False}
    if any("persistence" in f for f in features):
        return {"file": "casper-rw", "label": "casper-rw", "parameter": "persistent", "config": False}
    return None


def create_persistence(staging, size_mb, release, temporary, progress=None):
    if size_mb <= 0: return None
    spec = persistence_spec(release)
    if not spec: raise ValueError("Persistence is not declared for this distribution. Choose a matching preset in Options.")
    relative = Path(spec["file"])
    if relative.is_absolute() or ".." in relative.parts: raise ValueError("Invalid persistence filename in the preset")
    if size_mb > 4095: raise ValueError("A persistence file on FAT32 is limited to 4095 MB.")
    path = Path(temporary) / "persistence.fs" if spec.get("partition") else Path(staging) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink(): raise ValueError("Persistence target cannot be a symbolic link")
    with path.open("wb") as out: out.truncate(int(size_mb) * 1024 * 1024)
    if "fedora-persistence" in supported_features(release) or "mandriva-persistence" in supported_features(release):
        # The original Fedora overlay is a zero-filled device-mapper snapshot, not ext2.
        return spec
    contents = Path(temporary) / "persistence-contents";contents.mkdir(exist_ok=True)
    if spec["config"]: (contents / "persistence.conf").write_text("/ union\n")
    if progress: progress(0, "Formatting Linux persistence")
    run([tool("mke2fs"), "-q", "-F", "-t", "ext2", "-E", "no_copy_xattrs", "-L", spec["label"], "-d", contents, path])
    return spec


def syslinux_version(staging, release):
    for feature in supported_features(release):
        if re.fullmatch(r"syslinux[3-6]", feature): return int(feature[-1])
    for p in Path(staging).rglob("isolinux.bin"):
        found = re.search(rb"ISOLINUX\s+([3-6])\.", p.read_bytes()[:65536])
        if found: return int(found[1])
    return 6


def rename_and_move(staging):
    root = Path(staging)
    candidates = [root / "isolinux", root / "boot/isolinux", root / "syslinux", root / "boot/syslinux"]
    for path in candidates:
        if not path.is_dir(): continue
        target = path.with_name("syslinux")
        if target != path and not target.exists(): path.rename(target)
        for cfg in target.rglob("*"):
            if cfg.is_file() and cfg.suffix.lower() in (".cfg", ".txt"):
                text = cfg.read_text(errors="replace").replace("isolinux/", "syslinux/")
                cfg.write_text(text)
        iso = target / "isolinux.cfg"
        if iso.exists(): shutil.copy2(iso, target / "syslinux.cfg")
        return target
    folder = root / "syslinux";folder.mkdir(exist_ok=True)
    return folder


def kernel_and_initrd(staging):
    root = Path(staging)
    kernels = [p for p in root.rglob("*") if p.is_file() and p.name.startswith(("vmlinuz", "linux", "bzImage")) and p.stat().st_size > 4096]
    initrds = [p for p in root.rglob("*") if p.is_file() and p.name.startswith(("initrd", "initramfs"))]
    if not kernels or not initrds: return None
    key = lambda p: (0 if p.parent.name in ("casper", "live", "isolinux", "syslinux") else 1, len(str(p)))
    return "/" + min(kernels, key=key).relative_to(root).as_posix(), "/" + min(initrds, key=key).relative_to(root).as_posix()


def prepare_boot(staging, release, persistence, language="English", skip_menu=False, skip_renaming=False):
    root = Path(staging)
    if skip_renaming:
        folder=next((root/p for p in ("syslinux","boot/syslinux","isolinux","boot/isolinux") if (root/p).is_dir()),root/"syslinux")
        folder.mkdir(exist_ok=True)
    else: folder = rename_and_move(root)
    version = syslinux_version(root, release)
    modules = ROOT / "Original/tools/syslinux-modules" / ("v" + str(version))
    for p in root.rglob("*.c32"):
        replacement = modules / p.name
        if replacement.exists(): shutil.copy2(replacement, p)
    for name in ("menu.c32", "vesamenu.c32", "libcom32.c32", "libutil.c32", "ldlinux.c32"):
        replacement = modules / name
        if replacement.exists(): shutil.copy2(replacement, folder / name)
    existing = folder / "syslinux.cfg"
    found = kernel_and_initrd(root)
    spec = persistence_spec(release) if persistence else None
    if not skip_menu and found and (spec or not existing.exists()):
        kernel, initrd = found
        distribution = release.get("distribution", "")
        base = "boot=casper" if distribution == "ubuntu" or (root / "casper").exists() else "boot=live config" if distribution == "debian" or (root / "live").exists() else ""
        base += " quiet"
        if language == "Spanish": base += " locale=es_ES.UTF-8 keyboard-layouts=es"
        text = "DEFAULT menu.c32\nPROMPT 0\nTIMEOUT 100\nMENU TITLE " + release.get("name", "LinuxLive") + "\n"
        if spec:
            extra = spec["parameter"]
            if extra == "rd.live.overlay": extra += "=LABEL=LILILIVE:/" + spec["file"]
            text += "LABEL persistent\n MENU LABEL Persistent mode\n KERNEL " + kernel + "\n APPEND initrd=" + initrd + " " + base + " " + extra + "\n"
        text += "LABEL live\n MENU LABEL Live mode\n KERNEL " + kernel + "\n APPEND initrd=" + initrd + " " + base + "\n"
        existing.write_text(text)
    # EFI files stay the distribution's own signed loader. Modify only external config text.
    if spec and not skip_menu:
        for cfg in list(root.rglob("grub.cfg")) + list(root.rglob("loopback.cfg")):
            lines = cfg.read_text(errors="replace").splitlines()
            for n, line in enumerate(lines):
                if re.match(r"\s*(linux|linuxefi)\s", line) and spec["parameter"] not in line and "install" not in line.lower():
                    lines[n] = line + " " + spec["parameter"]
            cfg.write_text("\n".join(lines) + "\n")
    return {"folder": folder.relative_to(root).as_posix(), "version": version, "bios": existing.exists(), "efi": (root / "EFI/BOOT").is_dir() or (root / "efi/boot").is_dir()}


def install_syslinux(image_or_device, boot, offset=0):
    if not boot["bios"]: return
    if boot["version"] == 3:
        args = [tool("syslinux3"), "-d", boot["folder"]]
        if offset: args += ["-o", str(offset)]
    else:
        args = [tool("syslinux" + str(boot["version"])), "--install", "--directory", boot["folder"]]
        if offset: args += ["--offset", str(offset)]
    args.append(str(image_or_device));run(args)
