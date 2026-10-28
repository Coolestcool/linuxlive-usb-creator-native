#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""LiLi Mac process interface. No disk write happens during startup or discovery."""
import json
from pathlib import Path
import sys
from core import ROOT, RES, SUPPORT, settings, save_settings, catalog, translations, hashes, disks, download, url_opener, ini, run
from creation import emit, inspect_source, prepare, make_image, install, save_plan


def describe():
    from releases import current_catalog
    return dict(current_releases=current_catalog(),version="1.0.0-preview3", original_version="2.9.4", settings=settings(), catalog=catalog(), languages=["Automatic", "English"] + sorted(p.stem for p in (RES / "languages").glob("*.ini")), tools={n: (ROOT / "NativeTools/bin" / n).is_file() for n in ("7z", "mcopy", "mformat", "mke2fs", "syslinux3", "syslinux4", "syslinux5", "syslinux6")}, virtualization=__import__("virtualization").qemu_path() is not None)


def updates():
    from releases import refresh
    return refresh(emit)


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "describe"
    if command == "describe": return describe()
    if command == "release-catalog-refresh":
        from releases import refresh
        return refresh(emit)
    if command == "disks": return disks()
    if command == "translate": return translations(sys.argv[2])
    if command == "inspect": return inspect_source(sys.argv[2], settings(), emit)
    if command == "hash": return hashes(sys.argv[2], emit)
    if command == "save-settings":
        save_settings(json.loads(Path(sys.argv[2]).read_text()));return {"saved": True}
    if command == "download":
        urls=json.loads(sys.argv[2]) if sys.argv[2].startswith("[") else [sys.argv[2]]
        if not isinstance(urls,list) or not urls or len(urls)>64:raise ValueError("Invalid mirror list")
        failures=[]
        for number,url in enumerate(urls):
            try:return {"path":download(url,sys.argv[3],emit,expected_sha256=sys.argv[4] if len(sys.argv)>4 else None),"mirror":number+1}
            except Exception as error:failures.append(str(error))
        raise ValueError("All selected mirrors failed. Last error: "+failures[-1])
    if command == "test-proxy":
        config = json.loads(Path(sys.argv[2]).read_text())
        with url_opener(config).open("https://releases.ubuntu.com", timeout=15) as response:
            return {"status": response.status}
    if command == "updates": return updates()
    if command in ("prepare", "make-image", "install"):
        plan = json.loads(Path(sys.argv[2]).read_text())
        if command == "prepare": return prepare(plan)
        if command == "make-image": return make_image(plan)
        return install(plan)
    if command == "virtualize":
        from virtualization import virtualize_image
        return virtualize_image(sys.argv[2])
    if command == "volume":
        from virtualization import volume_device
        return volume_device(sys.argv[2])
    if command == "virtualize-usb":
        from virtualization import virtualize_usb
        return virtualize_usb(json.loads(Path(sys.argv[2]).read_text()))
    raise ValueError("Unknown operation")


if __name__ == "__main__":
    try:
        result = main()
        print(json.dumps({"event": "result", "value": result}, ensure_ascii=False), flush=True)
    except Exception as error:
        print(json.dumps({"event": "error", "message": str(error)}, ensure_ascii=False), flush=True)
        sys.exit(1)
