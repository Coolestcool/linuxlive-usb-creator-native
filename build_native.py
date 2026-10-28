#!/usr/bin/env python3
"""Build native Syslinux installers from the exact upstream release archives."""
from pathlib import Path
import re
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[1] if len(ROOT.parents) > 1 else ROOT.parent
BUILD = Path(os.environ.get("LILI_NATIVE_BUILD", WORKSPACE / "work/lili-mac/build"))
BIN = Path(os.environ.get("LILI_NATIVE_OUTPUT", ROOT / "NativeTools/bin"))
BIN.mkdir(parents=True, exist_ok=True)
for version in ("3.86", "4.07", "5.10", "6.03"):
    src = BUILD / ("syslinux-" + version)
    loader = src / "bios" if (src / "bios/core/ldlinux.sys").exists() else src
    entry = (src / "mtools/syslinux.c").read_text().replace("#include <mntent.h>", "/* macOS: unused Linux-only header omitted. */")
    if sys.platform == "darwin":
        # Pass the already-open descriptor to mtools; macOS has no /proc/PID/fd.
        entry = entry.replace("/proc/%lu/fd/%d", "/dev/fd/%d").replace("(unsigned long)mypid,", "")
    (src / "mtools/syslinux-mac.c").write_text(entry)
    blobs = [("bootsect", loader / "core/ldlinux.bss"), ("ldlinux", loader / "core/ldlinux.sys")]
    if int(version[0]) >= 5: blobs.append(("ldlinuxc32", loader / "com32/elflink/ldlinux/ldlinux.c32"))
    data = "#include <stdint.h>\n"
    for name, path in blobs:
        content = path.read_bytes()
        data += "unsigned char syslinux_" + name + "[]={" + ",".join(str(x) for x in content) + "};\n"
        data += "const unsigned int syslinux_" + name + "_len=" + str(len(content)) + ";\nconst int syslinux_" + name + "_mtime=0;\n"
    (src / "mtools/blobs-mac.c").write_text(data)
    makefile = (src / "mtools/Makefile").read_text()
    includes = [p for p in re.findall(r"\.\./libinstaller/([\w]+\.c)", makefile) if not p.endswith("_bin.c")]
    files = [src / "mtools/syslinux-mac.c", src / "mtools/blobs-mac.c"] + [src / "libinstaller" / p for p in includes] + list((src / "libfat").glob("*.c"))
    command = [os.environ.get("CC", "/usr/bin/clang"), "-Os", "-include", "sys/types.h", "-Wno-address-of-packed-member", "-D_FILE_OFFSET_BITS=64"]
    command += ["-I" + str(p) for p in (src, loader, src / "libfat", src / "libinstaller")]
    command += list(map(str, files)) + ["-o", str(BIN / ("syslinux" + version[0]))]
    result = subprocess.run(command, capture_output=True, text=True)
    (BUILD / ("syslinux" + version[0] + ".log")).write_text(result.stdout + result.stderr)
    print(version, result.returncode)
    if result.returncode: print(result.stderr[-2000:]);sys.exit(result.returncode)
